"""Bounded Bing request comparisons; does not enable Bing in the application.

Variants are protocol hypotheses from DDGS, SearXNG and a public plain-HTTP
scraper. Domain checks are labelled test expectations, not a general relevance
classifier. HTML and session details stay private. No browser/proxy/API is used.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import HTTPError
from types import SimpleNamespace
from uuid import uuid4

from lxml import html

from travel_agent.web import _clean_url


def parse_results(text):
    from travel_agent.web import _unwrap_search_url
    root = html.fromstring(text)
    results = []
    for item in root.xpath('//li[contains(concat(" ", normalize-space(@class), " "), " b_algo ")]'):
        headings = item.xpath('.//h2')
        if not headings:
            continue
        title = ' '.join(headings[0].text_content().split())
        anchors = headings[0].xpath('.//a[@href]') or item.xpath('.//a[@href]')
        target = None
        for anchor in anchors:
            candidate = anchor.get('href')
            if candidate.startswith('https://www.bing.com/ck/a?'):
                try:
                    candidate = _unwrap_search_url(candidate, "bing")
                except (ValueError, UnicodeError):
                    continue
            clean = _clean_url(candidate) if candidate else None
            if clean and urlsplit(clean).hostname not in {'bing.com', 'www.bing.com'}:
                target = clean
                break
        if title and target:
            results.append({'title':title, 'url':target})
    return root.xpath('string(//title)'), results


def run(query, domain, locale, variant, folder):
    event = {'id':uuid4().hex,'query':query,'expected_domain':domain,'variant':variant,
             'started_at':datetime.now(timezone.utc).isoformat()}
    started = time.perf_counter()
    language, country = locale.split('-')
    params = {'q':query}
    if variant in {'legacy', 'ddgs'}:
        params.update(pq=query,cc='kr')
    elif variant == 'locale':
        params.update(setlang=language,cc=country,adlt='moderate')
    elif variant == 'market':
        params.update(setlang=language,mkt=locale,adlt='moderate')
    event['params'] = params
    try:
        if variant == 'ddgs':
            from ddgs.engines.bing import Bing
            # Direct engine diagnostics only: do not change the registry/disabled flag.
            engine = Bing(timeout=12)
            params = engine.build_payload(query, 'kr-kr', 'moderate', None)
            event['params'] = params
            event['client'] = 'DDGS Bing HttpClient/primp, random impersonation, region kr-kr'
            response = engine.http_client.request('GET', engine.search_url, params=params)
            if response.status_code == 200:
                original = engine.post_extract_results(engine.extract_results(response.text))
                event['ddgs_hits'] = [{'title':x.title, 'url':x.href} for x in original[:5]]
        elif variant == 'plain':
            class NoRedirect(HTTPRedirectHandler):
                def redirect_request(self,*args,**kwargs):
                    return None
            opener = build_opener(ProxyHandler({}),NoRedirect())
            request = Request('https://www.bing.com/search?'+urlencode(params),
                              headers={'Accept-Language':'en-US,en;q=0.9'})
            event['client'] = 'stdlib urllib, default Python UA; not the repository requests client'
            try:
                incoming = opener.open(request,timeout=12)
            except HTTPError as error:
                incoming = error
            with incoming:
                response = SimpleNamespace(status_code=incoming.status,content=incoming.read(),headers=incoming.headers)
        else:
            from curl_cffi.requests import Session
            with Session(impersonate='edge101') as session:
                if variant == 'legacy':
                    session.cookies.set('_EDGE_CD','m=kr-kr&u=kr-kr',domain='www.bing.com')
                    session.cookies.set('_EDGE_S','mkt=kr-kr&ui=kr-kr',domain='www.bing.com')
                response = session.get('https://www.bing.com/search',params=params,timeout=12,allow_redirects=False)
        (folder/(event['id']+'.body')).write_bytes(response.content)
        headers = getattr(response, 'headers', {})  # DDGS wrapper does not expose headers.
        event.update(http_status=response.status_code,bytes=len(response.content),
                     content_type=headers.get('content-type'),redirect_path=urlsplit(headers.get('location','')).path)
        if response.status_code == 200:
            title, hits = parse_results(response.content.decode('utf-8',errors='replace'))
            event.update(page_title=title,hits=hits[:5],parsed_count=len(hits),
                         expected_domain_found=any(urlsplit(x['url']).hostname==domain or urlsplit(x['url']).hostname.endswith('.'+domain) for x in hits[:5]))
    except Exception as exc:
        event['error_type'] = type(exc).__name__
    event.update(finished_at=datetime.now(timezone.utc).isoformat(),elapsed_ms=round((time.perf_counter()-started)*1000))
    return event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',action='append',choices=['legacy','locale','market','plain','ddgs'])
    parser.add_argument('--repeat',type=int,choices=range(1,4),default=1)
    parser.add_argument('--include-travel',action='store_true')
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    folder = Path('data/private/bing-research')/uuid4().hex
    folder.mkdir(parents=True)
    records = []
    cases = [('Python official website','python.org','en-gb'),
             ('국립춘천박물관 공식 홈페이지','chuncheon.museum.go.kr','ko-kr')]
    if args.include_travel:
        cases.append(('춘천 삼악산 호수케이블카 공식 홈페이지','samaksancablecar.com','ko-kr'))
    for repeat in range(1,args.repeat+1):
        for query,domain,locale in cases:
            for variant in args.variant or ['legacy','locale','market','plain']:
                event = run(query,domain,locale,variant,folder)
                event['repeat'] = repeat
                records.append(event)
                target = args.output or folder/'report.json'
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps(event,ensure_ascii=True),flush=True)
    return 0 if all(x.get('expected_domain_found') for x in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())
