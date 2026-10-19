"""Read selected public search sources; HTML stays outside the model context."""
import gzip
import hashlib
from threading import Lock
from http.client import HTTPConnection, HTTPSConnection, HTTPException
from datetime import datetime, timezone
from io import BytesIO
import ipaddress
import socket
import time
from urllib.parse import urlsplit

from trafilatura import extract

from .memory import canonical
from .web import WebSearchError, _clean_url
from .evidence_text import bounded_blocks, bounded_prefix, body_signal
from .structured_lodging import lodging_metadata

MAX_PAGE_BYTES = 2 * 1024 * 1024


class PageCache:
    """One agent invocation only. Parallel reads share an immutable extracted page."""
    def __init__(self, max_bytes=8 * 1024 * 1024):
        self.pages = {}
        self.max_bytes = max_bytes
        self.used_bytes = 0
        self.lock = Lock()
        self.source_locks = {}

    def load(self, source, timeout, token=None):
        with self.lock:
            source_lock = self.source_locks.setdefault(source['id'], Lock())
        with source_lock:
            cached = self.pages.get(source['id'])
            if token is not None and (cached is None or cached['document_token'] != token):
                raise ValueError('Document token is not cached in this run; first read source_id with query only')
            if cached is not None:
                return cached, True
            body, info = fetch_public_page(source['url'], timeout)
            text = extract_page(body, source['url'])
            size = len(text.encode())
            cached = {'text': text, 'info': info, 'download_bytes': len(body),
                'fetched_at': datetime.now(timezone.utc).isoformat(),
                'document_token': hashlib.sha256((source['id'] + text).encode()).hexdigest()[:16]}
            with self.lock:
                if self.used_bytes + size > self.max_bytes:
                    raise ValueError('Page cache byte budget reached; cached documents remain readable')
                self.pages[source['id']] = cached
                self.used_bytes += size
            return cached, False


def fetch_public_page(url, timeout=12):
    """Resolve once and pin the connection IP, keeping TLS hostname verification."""
    clean = _clean_url(url)
    if not clean:
        raise WebSearchError('Invalid page URL', details={'reason':'invalid_url'})
    parsed = urlsplit(clean)
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    if port not in (80, 443):
        raise WebSearchError('Unsupported page port', details={'reason':'unsafe_address'})
    info = {'method':'GET'}
    connection = None
    try:
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(item[4][0] for item in addresses))
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise WebSearchError('Page address is not public', details={'reason':'unsafe_address'})
        connection = (HTTPSConnection if parsed.scheme == 'https' else HTTPConnection)(parsed.hostname, port, timeout=timeout)
        # HTTPConnection.connect uses this socket factory; HTTPS still wraps the
        # socket using the original hostname for SNI/certificate validation.
        connection._create_connection = lambda address, timeout, source_address=None: socket.create_connection((ips[0], port), timeout, source_address)
        target = parsed.path or '/'
        if parsed.query:
            target += '?' + parsed.query
        connection.request('GET', target, headers={'User-Agent':'TravelAgentResearch/0.1', 'Accept':'text/html', 'Accept-Encoding':'identity'})
        response = connection.getresponse()
        info['http_status'] = response.status
        if response.status != 200:
            raise WebSearchError('Page HTTP failure; redirects are not followed', details={'reason':'http_error', **info})
        if response.headers.get_content_type() not in {'text/html','application/xhtml+xml'}:
            raise WebSearchError('Only HTML pages are supported', details={'reason':'unsupported_content', **info})
        body = response.read(MAX_PAGE_BYTES + 1)
        if len(body) > MAX_PAGE_BYTES:
            raise WebSearchError('Page too large', details={'reason':'response_too_large', **info})
        encoding = response.getheader('Content-Encoding', 'identity').lower()
        if encoding == 'gzip':
            body = gzip.GzipFile(fileobj=BytesIO(body)).read(MAX_PAGE_BYTES + 1)
        elif encoding != 'identity':
            raise WebSearchError('Unsupported page encoding', details={'reason':'unsupported_encoding', **info})
        if len(body) > MAX_PAGE_BYTES:
            raise WebSearchError('Expanded page too large', details={'reason':'response_too_large', **info})
        return body, info
    except WebSearchError:
        raise
    except (OSError, ValueError, HTTPException) as exc:
        raise WebSearchError('Page request failed', details={'reason':'request_failed','error_type':type(exc).__name__, **info}) from exc
    finally:
        if connection:
            connection.close()


def extract_page(body, url, output_format='markdown'):
    """Extraction, not LLM summarization or execution of website JavaScript."""
    text = extract(body, url=url, output_format=output_format, include_comments=False,
                   include_tables=True, include_links=False, include_images=False)
    metadata=lodging_metadata(body,url)
    if metadata:
        prefix='숙소 페이지 JSON-LD 주소 (페이지 제공 정보·독립 검증 아님):\n'+canonical(metadata)
        text=prefix+('\n\n'+text if text else '')
    if not text or not text.strip():
        raise WebSearchError('No readable page text', details={'reason':'empty_extraction'})
    return text.strip()


def select_excerpt(text, query, max_bytes):
    """Share research's selector; import lazily to avoid a fetcher import cycle."""
    from .web_pipeline import passages
    excerpt, selected = passages(text, query, limit=2000, max_bytes=max_bytes)
    return excerpt, selected, len(bounded_blocks(text,600,max_bytes))


def web_read(source, query, *, timeout=12, max_bytes=3500, cache=None, document_token=None, start_index=None):
    started = time.perf_counter()
    if (document_token is None) != (start_index is None):
        raise ValueError('Pagination requires both document_token and start_index')
    if document_token is not None and cache is None:
        raise ValueError('Pagination requires a run-scoped page cache')
    if cache is not None:
        page, hit = cache.load(source, timeout, document_token)
        text, info = page['text'], page['info']
    else:
        body, info = fetch_public_page(source['url'], timeout)
        text = extract_page(body, source['url'])
    result = {'id':source['id'], 'title':source['title'], 'url':source['url'],
              'content_kind':'page_excerpt', 'page_fetched':True, 'format':'markdown',
              'verified_current':False, 'selection_query':query, 'text':'',
              'body_signal':body_signal(text),
              'truncated':True, 'selected_blocks':[], 'total_blocks':0,
              'download_bytes':page['download_bytes'] if cache is not None else len(body), **info}
    result['fetched_at'] = page['fetched_at'] if cache is not None else datetime.now(timezone.utc).isoformat()
    if cache is not None:
        result.update(document_token=page['document_token'], cache_hit=hit,
            total_chars=len(text), start_index=start_index, next_start_index=None,
            reading_mode='sequential' if start_index is not None else 'query_excerpt')
    if start_index is not None and (type(start_index) is not int or not 0 <= start_index < len(text)):
        raise ValueError('start_index is outside the cached extracted document')
    available = max_bytes - len(canonical(result).encode('utf-8')) - 160
    if start_index is not None:
        # Preserve exact character offsets, including whitespace. Query selection is bypassed.
        result.update(text_is_fragment=True, boundary_split=False)
        while available > 0:
            excerpt = bounded_prefix(text[start_index:], available)
            split = not bool(excerpt)
            if split:
                # JSON-LD and long tokens may have no sentence/word boundary.
                # Explicitly label the fragment instead of dropping its contents.
                excerpt = text[start_index:].encode()[:available].decode('utf-8', errors='ignore')
            end = start_index + len(excerpt)
            result.update(text=excerpt, truncated=end < len(text),
                boundary_split=split, next_start_index=end if end < len(text) else None)
            if excerpt and len(canonical(result).encode()) <= max_bytes:
                result['elapsed_ms'] = round((time.perf_counter()-started)*1000)
                return result
            available -= 100
        raise WebSearchError('No sequential text fits output budget', details={'reason':'output_budget_too_small'})
    excerpt, selected, total = select_excerpt(text, query, max(0, available))
    result.update(text=excerpt, selected_blocks=selected, total_blocks=total,
                  truncated=excerpt!=text, elapsed_ms=round((time.perf_counter()-started)*1000))
    # JSON escaping also consumes bytes; keep whole blocks rather than silently
    # exceeding the tool budget when a page contains many quotes/backslashes.
    while len(canonical(result).encode('utf-8')) > max_bytes and result['selected_blocks']:
        available = max(0, available - 200)
        excerpt, selected, _ = select_excerpt(text, query, available)
        result.update(text=excerpt, selected_blocks=selected, truncated=True)
    if not result['text']:
        if cache is None:
            raise WebSearchError('No page excerpt fits output budget', details={'reason':'output_budget_too_small'})
        result['excerpt_unavailable_reason'] = 'No matching bounded excerpt; use document_token and start_index=0 to read extracted text'
    if cache is not None and result['truncated']:
        result['next_start_index'] = 0
    if len(canonical(result).encode()) > max_bytes:
        raise WebSearchError('Page metadata exceeds output budget', details={'reason':'output_budget_too_small'})
    return result
