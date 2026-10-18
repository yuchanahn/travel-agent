"""Read selected public search sources; HTML stays outside the model context."""
import gzip
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
from .evidence_text import bounded_blocks, body_signal

MAX_PAGE_BYTES = 2 * 1024 * 1024


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
    if not text or not text.strip():
        raise WebSearchError('No readable page text', details={'reason':'empty_extraction'})
    return text.strip()


def select_excerpt(text, query, max_bytes):
    """Share research's selector; import lazily to avoid a fetcher import cycle."""
    from .web_pipeline import passages
    excerpt, selected = passages(text, query, limit=2000, max_bytes=max_bytes)
    return excerpt, selected, len(bounded_blocks(text,600,max_bytes))


def web_read(source, query, *, timeout=12, max_bytes=3500):
    started = time.perf_counter()
    body, info = fetch_public_page(source['url'], timeout)
    text = extract_page(body, source['url'])
    result = {'id':source['id'], 'title':source['title'], 'url':source['url'],
              'content_kind':'page_excerpt', 'page_fetched':True, 'format':'markdown',
              'verified_current':False, 'selection_query':query, 'text':'',
              'body_signal':body_signal(text),
              'truncated':True, 'selected_blocks':[], 'total_blocks':0,
              'download_bytes':len(body), **info}
    result['fetched_at'] = datetime.now(timezone.utc).isoformat()
    available = max_bytes - len(canonical(result).encode('utf-8')) - 160
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
        raise WebSearchError('No page excerpt fits output budget', details={'reason':'output_budget_too_small'})
    return result
