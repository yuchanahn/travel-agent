"""Bounded one-hop page collection, private documents and model-facing catalogues."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from threading import RLock
import time
from urllib.parse import urljoin, urlsplit

from lxml import html
from lxml.etree import ParserError, XMLSyntaxError

from .lexical import tokens
from .memory import canonical
from .web import _clean_url, WebSearchError
from .web_read import extract_page, fetch_public_page


def source_id(url):
    return 'web:' + hashlib.sha256(url.encode()).hexdigest()[:16]


def page_links(body, url):
    """Read HTML metadata/anchors; no JS execution or inference of link meaning."""
    tree = html.fromstring(body, parser=html.HTMLParser(no_network=True))
    title = ' '.join(tree.xpath('string(//title)').split())
    descriptions = tree.xpath('//meta[translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="description"]/@content')
    description = ' '.join(descriptions[0].split()) if descriptions else ''
    links, seen = [], set()
    for anchor in tree.xpath('//a[@href]'):
        href = anchor.get('href', '').strip()
        if not href or href.startswith('#'):
            continue
        target = _clean_url(urljoin(url, href))
        if not target or target == url or target in seen:
            continue
        if re.search(r'\.(?:jpg|jpeg|gif|png|webp|svg|css|js|zip|pdf|mp4|ico)$', urlsplit(target).path, re.I):
            continue
        seen.add(target)
        links.append({'url': target, 'anchor': ' '.join(anchor.text_content().split())})
        if len(links) >= 128:
            break
    return title, description, links


class DocumentCollection:
    """One run's durable sources. Catalogue is metadata; read() is explicit body delivery."""
    def __init__(self, directory, *, roots=3, neighbors=3, max_documents=16,
                 max_bytes=32*1024*1024, workers=3, timeout=30, fetcher=None):
        if not (1 <= roots <= 10 and 0 <= neighbors <= 10 and 1 <= max_documents <= 64
                and 1024 <= max_bytes <= 128*1024*1024 and 1 <= workers <= 3 and 0 < timeout <= 90):
            raise ValueError('Invalid document collection limits')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.directory.is_symlink() or self.directory.is_junction():
            raise ValueError('Document directory cannot be a link')
        self.roots, self.neighbors, self.max_documents = roots, neighbors, max_documents
        self.max_bytes, self.workers, self.timeout = max_bytes, workers, timeout
        self.fetcher = fetcher or fetch_public_page
        self.lock = RLock()
        path = self.directory/'manifest.json'
        self.documents = json.loads(path.read_text(encoding='utf-8'))['documents'] if path.exists() else {}
        self.used_bytes = sum(d.get('stored_bytes', 0) for d in self.documents.values())
        self.events = []

    def _save(self):
        temp = self.directory/'manifest.tmp'
        temp.write_text(canonical({'version': 1, 'documents': self.documents}), encoding='utf-8')
        temp.replace(self.directory/'manifest.json')

    def _add(self, url, *, title='', parent=None, anchor=''):
        url = _clean_url(url)
        if not url:
            return None
        sid = source_id(url)
        if sid not in self.documents:
            if len(self.documents) >= self.max_documents:
                return None
            self.documents[sid] = {'id': sid, 'url': url, 'title': title or anchor,
                'description': '', 'parents': [], 'anchors': [], 'status': 'pending',
                'page_fetched': False, 'verified_current': False, 'links': []}
        d = self.documents[sid]
        if parent and parent not in d['parents']:
            d['parents'].append(parent)
        if anchor and anchor not in d['anchors']:
            d['anchors'].append(anchor)
        return sid

    def _fetch(self, sid, deadline):
        d = self.documents[sid]
        started = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        def finished(result, body=None, text=None):
            return sid, {**result, 'started_at': started_at,
                         'elapsed_ms': round((time.monotonic()-started)*1000)}, body, text
        body, info = None, {}
        try:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                return finished({'status': 'not_fetched', 'error': 'collection_deadline'})
            body, info = self.fetcher(d['url'], timeout=min(8, remaining))
            title, description, links = page_links(body, d['url'])
            text, error = '', None
            try:
                text = extract_page(body, d['url'])
            except WebSearchError as exc:
                error = str(exc)
            return finished({'status': 'ready' if text else 'empty', 'title': title or d['title'],
                'description': description, 'links': links, 'page_fetched': True,
                'fetched_at': datetime.now(timezone.utc).isoformat(), **info,
                **({'error': error} if error else {})}, body, text)
        except (OSError, ValueError, WebSearchError, ParserError, XMLSyntaxError) as exc:
            return finished({'status': 'failed', 'error': str(exc),
                'page_fetched':body is not None, **info,
                **(exc.details if isinstance(exc, WebSearchError) else {})}, body, '')

    def _batch(self, ids, deadline):
        pending = [sid for sid in dict.fromkeys(ids) if self.documents[sid]['status'] == 'pending']
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for sid, result, body, text in pool.map(lambda sid: self._fetch(sid, deadline), pending):
                d = self.documents[sid]
                size = len(body or b'') + len((text or '').encode())
                if self.used_bytes + size > self.max_bytes:
                    result = {**result, 'status': 'failed', 'error': 'storage_budget', 'links':[]}
                    body = text = None
                d.update(result)
                if body is not None:
                    stem = sid.removeprefix('web:')
                    (self.directory/(stem+'.html')).write_bytes(body)
                    if text:
                        digest = hashlib.sha256(text.encode()).hexdigest()
                        duplicate = next((x for x in self.documents.values() if x.get('text_digest') == digest and x['id'] != sid), None)
                        text_file = duplicate['text_file'] if duplicate else stem+'.md'
                        if not duplicate:
                            (self.directory/text_file).write_text(text, encoding='utf-8')
                        d.update(text_file=text_file, text_digest=digest, total_chars=len(text),
                                 document_token=hashlib.sha256((sid+text).encode()).hexdigest()[:16])
                        if duplicate:
                            d['same_content_as'] = duplicate['id']
                            size -= len(text.encode())
                    d['stored_bytes'] = size
                    self.used_bytes += size
                self.events.append({'id': sid, 'url': d['url'], 'status': d['status'],
                    'error': d.get('error'), 'started_at': d.get('started_at'),
                    'elapsed_ms':d.get('elapsed_ms'), 'fetched_at': d.get('fetched_at')})
        self._save()

    def collect(self, hits, *, query='', timeout=None):
        deadline = time.monotonic()+min(self.timeout, timeout if timeout is not None else self.timeout)
        with self.lock:
            roots, skipped = [], 0
            for hit in hits[:self.roots]:
                sid = self._add(hit['url'], title=hit.get('title', ''))
                if sid:
                    roots.append(sid)
                else:
                    skipped += 1
            self._batch(roots, deadline)
            children, outside, omitted = [], 0, 0
            for sid in roots:
                d = self.documents[sid]
                local = []
                for link in d['links']:
                    if urlsplit(link['url']).hostname != urlsplit(d['url']).hostname:
                        outside += 1
                        continue
                    local.append(link)
                # Budget selection only; not a semantic recommendation or model decision.
                q = set(tokens(query))
                local.sort(key=lambda link: -len(q & set(tokens(link['anchor']+' '+urlsplit(link['url']).path))))
                for link in local[:self.neighbors]:
                    child = self._add(link['url'], parent=sid, anchor=link['anchor'])
                    if child:
                        children.append(child)
                    else:
                        skipped += 1
                omitted += max(0, len(local)-self.neighbors)
            self._batch(children, deadline)  # One hop only; never recurse into child links.
            self._save()
            return {'scope': 'same_host_one_hop', 'root_limit': self.roots,
                'neighbor_limit': self.neighbors, 'documents': self.catalog(),
                'link_scan_limit_per_page':128, 'link_scan_may_be_limited':any(len(self.documents[sid]['links'])>=128 for sid in roots),
                'outside_host_links': outside, 'omitted_neighbor_links': omitted,
                'skipped_document_budget': skipped, 'uncollected_search_results': max(0, len(hits)-len(roots))}

    def catalog(self):
        fields = ('id', 'url', 'title', 'description', 'parents', 'anchors', 'status',
                  'error', 'http_status', 'page_fetched', 'fetched_at', 'verified_current', 'total_chars', 'same_content_as')
        return [{k: d[k] for k in fields if k in d} for d in self.documents.values()]

    def read(self, sid, *, start_index=0, document_token=None, max_bytes=12000):
        with self.lock:
            if sid not in self.documents:
                raise ValueError('Unknown run-scoped document ID')
            d = self.documents[sid]
            if d['status'] != 'ready':
                return {**{k:d[k] for k in ('id','url','status')},
                    'error': d.get('error') or 'Document has no extracted body', 'is_error': True, 'page_fetched': d['page_fetched']}
            if document_token is not None and document_token != d['document_token']:
                raise ValueError('Document token does not match')
            if not re.fullmatch(r'[a-f0-9]{16}\.md', d['text_file']):
                raise ValueError('Invalid stored document path')
            path = self.directory/d['text_file']
            if path.is_symlink() or path.is_junction():
                raise ValueError('Stored document cannot be a link')
            text = path.read_text(encoding='utf-8')
            if type(start_index) is not int or not 0 <= start_index < len(text) or max_bytes < 1000:
                raise ValueError('Invalid document offset or byte budget')
            out = {k:d[k] for k in ('id','url','title','document_token','total_chars','fetched_at')}
            out.update(content_kind='page_excerpt', page_fetched=True, verified_current=False,
                       cache_hit=True, from_document_store=True, reading_mode='sequential',
                       start_index=start_index, next_start_index=None, truncated=True, text='')
            available = max_bytes-len(canonical(out).encode())-128
            while available > 0:
                fragment = text[start_index:].encode()[:available].decode('utf-8', errors='ignore')
                end = start_index+len(fragment)
                out.update(text=fragment, truncated=end < len(text), next_start_index=end if end < len(text) else None,
                           text_is_fragment=start_index > 0 or end < len(text))
                if fragment and len(canonical(out).encode()) <= max_bytes:
                    return out
                available -= 100
            raise ValueError('Document does not fit read budget')


def main():
    """Independent MCP collection/inspection; does not invoke a language model."""
    import argparse
    import sys
    from uuid import uuid4
    from .mcp_client import MCPRegistry, model_result
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', nargs='?')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--read', help='Read a saved web: document ID without network')
    parser.add_argument('--start-index', type=int, default=0)
    args = parser.parse_args()
    private = (Path.cwd()/'data/private').resolve()
    directory = (args.output or private/'web-documents'/uuid4().hex).resolve()
    if not directory.is_relative_to(private):
        parser.error('Documents must stay inside data/private')
    if args.read:
        if not args.output or not (directory/'manifest.json').is_file():
            parser.error('--read needs an existing --output collection')
        print(canonical(DocumentCollection(directory).read(args.read, start_index=args.start_index)))
        return
    if not args.query:
        parser.error('Provide a query or --read')
    collection = DocumentCollection(directory)
    with MCPRegistry() as registry:
        name = next((name for name, adapter in registry.adapters.items() if adapter == 'brave_search'), None)
        if not name:
            parser.error('Official Brave MCP is not connected')
        arguments = {'query': args.query, 'count': 20, 'country': 'KR', 'search_lang': 'ko', 'ui_lang': 'ko-KR'}
        result = registry.call(name, arguments, timeout=20)
    (directory/'search.json').write_text(canonical({'tool': name, 'arguments': arguments, 'result': result}), encoding='utf-8')
    packet = json.loads(model_result(result))
    catalogue = collection.collect(packet.get('hits', []), query=args.query)
    (directory/'catalog.json').write_text(canonical(catalogue), encoding='utf-8')
    (directory/'collection-events.json').write_text(canonical(collection.events), encoding='utf-8')
    print(canonical(catalogue))


if __name__ == '__main__':
    main()
