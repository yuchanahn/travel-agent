"""Bounded search evidence pipeline, independently exercised before agent wiring.

HTML and complete extracted text live in a request-scoped temporary directory.
No model, embeddings download, query rewrite, or cross-site fact synthesis.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from difflib import SequenceMatcher
from hashlib import sha256
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from time import perf_counter
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from lxml import html
from rank_bm25 import BM25Plus

from .web import _request_html, _parse_search_html, _parse_search_rss, _bing_locale_params, _clean_url, WebSearchError
from .web_read import fetch_public_page, extract_page


def tokens(text):
    """Words plus Korean character bigrams: transparent lexical, not semantic."""
    result = []
    for word in re.findall(r'[a-z0-9]+|[가-힣]+', text.lower()):
        if re.fullmatch('[가-힣]{2,}', word):
            # A two-character word is already its complete bigram. Keeping
            # both would double-weight standalone words versus compounds.
            if len(word)>2:
                result.append(word)
            result.extend('ko:'+word[i:i+2] for i in range(len(word)-1))
        else:
            result.append(word)
    return result


def canonical_url(url):
    clean = _clean_url(url)
    if not clean:
        return None
    p = urlsplit(clean)
    query = [(k, v) for k, values in parse_qs(p.query, keep_blank_values=True).items()
             if not k.lower().startswith('utm_') and k.lower() not in {'fbclid','gclid'} for v in values]
    return urlunsplit((p.scheme, p.netloc, p.path.rstrip('/') or '/', urlencode(sorted(query)), ''))


def next_request(text, query, current):
    """Use only Bing's observed next link, never fetch an arbitrary HTML URL."""
    tree = html.fromstring(text)
    for link in tree.xpath('//a[contains(concat(" ", normalize-space(@class), " "), " sb_pagN ")]/@href'):
        p = urlsplit(link)
        if p.hostname and p.hostname not in {'bing.com','www.bing.com'}:
            continue
        params = parse_qs(p.query)
        if p.path != '/search' or params.get('q') != [query]:
            continue
        value = params.get('first', [''])[0]
        if value.isdigit() and current < int(value) <= 1000:
            return int(value), {k:params[k][0] for k in ('FORM','FPIG') if k in params and len(params[k][0])<=100}
    return None


def next_offset(text, query, current):
    next_page = next_request(text,query,current)
    return next_page[0] if next_page else None


def group_candidates(rows):
    groups = []
    by_url = {}
    for rank, row in enumerate(rows, 1):
        url = canonical_url(row['href'])
        if not url:
            continue
        text = ' '.join((row['title']+' '+row['body']).lower().split())
        group = by_url.get(url)
        if group is None:
            # Content grouping uses substantial snippets, not a shared short title.
            group = next((g for g in groups if len(text) >= 100 and len(g['_text']) >= 100
                          and SequenceMatcher(None, text, g['_text'], autojunk=False).ratio() >= .92), None)
        if group is None:
            group = {'title':row['title'], 'url':url, 'snippet':row['body'],
                     'original_rank':rank, 'duplicates':[], '_text':text}
            groups.append(group)
        group['duplicates'].append({'url':row['href'], 'page':row['page'], 'rank':row['rank']})
        by_url[url] = group
    return [{k:v for k,v in g.items() if k != '_text'} for g in groups]


def rank_candidates(query, groups):
    if not groups:
        return []
    q = list(dict.fromkeys(tokens(query)))
    corpus = [tokens(g['title'])*2+tokens(g['snippet']) for g in groups]
    scores = BM25Plus([doc or ['__empty__'] for doc in corpus]).get_scores(q)
    ranked = []
    for g, doc, score in zip(groups, corpus, scores):
        matched = sorted(set(q)&set(doc))
        ranked.append({**g, 'score':round(float(score), 6) if matched else 0,
                       'matched_terms':matched, 'query_coverage':round(len(matched)/max(1,len(q)), 3)})
    return sorted(ranked, key=lambda g:(-g['score'],g['original_rank']))


def passages(text, query, limit=1000, *, max_bytes=None):
    """Rank bounded, verbatim passage slices; no generated claims."""
    # Keep adjacent headings with their prose. Isolated short menu headings
    # otherwise outrank the actual explanation merely by repeating the query.
    blocks, current = [], ''
    chunk_size = min(600,max(20,max_bytes//4)) if max_bytes is not None else 600
    for paragraph in re.split(r'\n\s*\n',text):
        for i in range(0,len(paragraph),chunk_size):
            piece = paragraph[i:i+chunk_size].strip()
            if not piece:
                continue
            if current and len(current)+len(piece)+2 > chunk_size:
                blocks.append(current)
                current = ''
            current += ('\n\n' if current else '')+piece
            if len(current) >= min(350,chunk_size):
                blocks.append(current)
                current = ''
    if current:
        blocks.append(current)
    if not blocks:
        return '', []
    docs = [tokens(b) or ['__empty__'] for b in blocks]
    q = list(dict.fromkeys(tokens(query)))
    scores = BM25Plus(docs).get_scores(q)
    order = sorted(range(len(blocks)), key=lambda i:(-float(scores[i]),i))
    selected = []
    for i in order:
        if len(selected) == 3:
            break
        if not set(q)&set(docs[i]):
            continue
        trial = '\n\n'.join(blocks[j] for j in sorted([*selected,i]))
        if len(trial) <= limit and (max_bytes is None or len(trial.encode()) <= max_bytes):
            selected.append(i)
    return '\n\n'.join(blocks[i] for i in sorted(selected)), sorted(selected)


def pack_digest(query, sources, max_bytes, summary):
    header = ('# Web evidence\n'+json.dumps({'query':query, **summary, 'verified_current':False},ensure_ascii=False)+'\n')
    if len(header.encode()) > max_bytes:
        raise ValueError('Output budget cannot contain metadata')
    digest, included = header, []
    for source in sources:
        base = (f"\n[{source['id']}] {source['title'][:180]}\n{source['url']}\n"
                f"kind={source['content_kind']}; page_fetched={source['page_fetched']}; excerpt_only=true\n")
        fair_share = (max_bytes-len(header.encode()))//max(1,len(sources))
        available = min(max_bytes-len((digest+base).encode())-len('\n[excerpt shortened]\n'.encode()),
                        fair_share-len(base.encode())-len('\n[excerpt shortened]\n'.encode()))
        if available < 60:
            continue
        body = source['text']
        selected_blocks = None
        if source.get('_page_text'):
            text, selected_blocks = passages(source['_page_text'],query,max_bytes=available)
            if not text:
                continue
            shortened = text != source['_page_text']
        else:
            shortened = len(body.encode()) > available
            text = body.encode()[:available].decode('utf-8',errors='ignore') if shortened else body
        digest += base+text+('\n[excerpt shortened]' if shortened else '')+'\n'
        included.append({**{k:v for k,v in source.items() if k != '_page_text'},
                         'delivered_text':text, 'delivered_blocks':selected_blocks,'output_shortened':shortened})
    return digest, included


def search_evidence(query, *, pages=3, top_k=5, read_pages=5, max_bytes=6000, keep_dir=None, timeout=12,
                    min_coverage=.25,serp_format='html',locale='none'):
    if not isinstance(query,str) or not 0 < len(query.strip()) <= 500:
        raise ValueError('Query must contain 1..500 characters')
    if type(pages) is not int or not 1 <= pages <= 10 or type(top_k) is not int or not 1 <= top_k <= 10:
        raise ValueError('pages and top_k must be integers 1..10')
    if type(read_pages) is not int or not 0 <= read_pages <= 10 or not 1500 <= max_bytes <= 20000 or not 0 < timeout <= 30:
        raise ValueError('Invalid read count, output budget or timeout')
    if not 0 <= min_coverage <= 1:
        raise ValueError('min_coverage must be between 0 and 1')
    if serp_format not in {'html','rss'}:
        raise ValueError('serp_format must be html or rss')
    _bing_locale_params(locale)
    query = query.strip()
    request_id = uuid4().hex
    with TemporaryDirectory(prefix='travel-search-') as temp:
        directory = Path(keep_dir)/request_id if keep_dir else Path(temp)
        directory.mkdir(parents=True, exist_ok=True)
        started = perf_counter()
        report = {'id':request_id, 'query':query, 'started_at':datetime.now(timezone.utc).isoformat(),
                  'events':[], 'raw_rows':[], 'stop_reason':'page_limit', 'model_invoked':False}
        def save():
            (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        offset, seen, page_params = 1, set(), {}
        for page in range(1,pages+1):
            event = {'id':uuid4().hex,'tool':'bing_search_http', 'query':query,'page':page,'first':offset,
                     'response_format':serp_format,'locale':locale,
                     'started_at':datetime.now(timezone.utc).isoformat()}
            try:
                raw, info = _request_html('bing',query,timeout,search_format=serp_format,locale=locale,
                                          **({'first':offset,'page_params':page_params} if page > 1 else {}))
                event.update(info)
                event['pagination_param_names'] = sorted(page_params)
                (directory/f'serp-{page}.{ "xml" if serp_format=="rss" else "html" }').write_text(raw,encoding='utf-8')
                if any(s in raw.lower() for s in ('id="b_captcha"','verify you are human')):
                    raise WebSearchError('Access challenge',details={'reason':'access_challenge'})
                rows = _parse_search_rss(raw,'bing') if serp_format=='rss' else _parse_search_html(raw,'bing')
                event.update(rows.details)
                if not rows:
                    report['stop_reason'] = 'empty_or_unparsed'
                    break
                urls = {canonical_url(r['href']) for r in rows}
                new = urls-seen
                event['new_urls'] = len(new)
                report['raw_rows'].extend({**r,'page':page,'rank':i} for i,r in enumerate(rows,1))
                if not new:
                    report['stop_reason'] = 'repeated_page'
                    break
                seen.update(urls)
                if serp_format=='rss':
                    report['stop_reason']='feed_limit'
                    break
                next_page = next_request(raw,query,offset)
                if next_page is None:
                    report['stop_reason'] = 'no_next_link'
                    break
                offset, page_params = next_page
            except WebSearchError as exc:
                event['error'] = exc.details
                report['stop_reason'] = 'http_or_parse_error'
                break
            except (ValueError,html.etree.ParserError) as exc:
                event['error'] = {'reason':'parse_error','type':type(exc).__name__}
                report['stop_reason'] = 'http_or_parse_error'
                break
            finally:
                event['finished_at'] = datetime.now(timezone.utc).isoformat()
                report['events'].append(event)
                save()
        groups = group_candidates(report['raw_rows'])
        ranked = rank_candidates(query,groups)
        report['ranked'] = ranked
        shortlist, domains = [], {}
        for row in ranked:
            host = urlsplit(row['url']).hostname.removeprefix('www.')
            if row['score'] <= 0 or row['query_coverage'] < min_coverage or domains.get(host,0) >= 2:
                continue
            domains[host] = domains.get(host,0)+1
            shortlist.append(row)
            if len(shortlist) == top_k:
                break
        def read(item):
            ev = {'id':uuid4().hex,'tool':'page_http_extract','url':item['url'],
                  'started_at':datetime.now(timezone.utc).isoformat()}
            downloaded = False
            try:
                body,info = fetch_public_page(item['url'],timeout)
                downloaded = True
                ev.update(info,download_bytes=len(body))
                key = sha256(item['url'].encode()).hexdigest()[:16]
                (directory/f'page-{key}.html').write_bytes(body)
                text = extract_page(body,item['url'])
                (directory/f'page-{key}.md').write_text(text,encoding='utf-8')
                excerpt, selected = passages(text,query)
                ev.update(info,download_bytes=len(body),extracted_bytes=len(text.encode()),selected_blocks=selected,
                          excerpt_bytes=len(excerpt.encode()),selection_status='ok' if excerpt else 'no_matching_passage')
                return {'text':excerpt,'_page_text':text if excerpt else '',
                        'page_fetched':True,'content_kind':'page_excerpt' if excerpt else 'search_snippet'},ev
            except WebSearchError as exc:
                ev['error'] = exc.details
                return {'text':'','page_fetched':downloaded,'content_kind':'search_snippet'},ev
            except (OSError,ValueError) as exc:
                ev['error'] = {'reason':'page_processing_failed','type':type(exc).__name__}
                return {'text':'','page_fetched':downloaded,'content_kind':'search_snippet'},ev
            finally:
                ev['finished_at'] = datetime.now(timezone.utc).isoformat()
        with ThreadPoolExecutor(max_workers=3) as pool:
            reads = list(pool.map(read,shortlist[:read_pages]))
        sources = []
        for i,item in enumerate(shortlist):
            evidence = {'text':'','page_fetched':False,'content_kind':'search_snippet'}
            if i < len(reads):
                evidence,ev = reads[i]
                report['events'].append(ev)
            if not evidence['text']:
                evidence['text'] = item['snippet'][:1000]
                evidence['content_kind'] = 'search_snippet'
            sources.append({**item, **evidence, 'id':'web:'+sha256(item['url'].encode()).hexdigest()[:16]})
        summary = {'collected':len(report['raw_rows']),'groups':len(groups), 'shortlisted':len(shortlist),
                   'response_format':serp_format,'locale':locale,
                   'stop_reason':report['stop_reason'],'retrieval_complete':False,
                   'ranking':'lexical_bm25plus','min_query_coverage':min_coverage,
                   'evidence_status':'unverified_candidates' if shortlist else 'insufficient_candidates',
                   'facts_synthesized':False}
        digest, delivered = pack_digest(query,sources,max_bytes,summary)
        report.update(summary,sources=delivered,digest=digest,digest_bytes=len(digest.encode()),
                      finished_at=datetime.now(timezone.utc).isoformat(),elapsed_ms=round((perf_counter()-started)*1000))
        save()
        return report
