"""Brave Web Search API; credentials never enter returned data or diagnostics."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from .web import MAX_RESPONSE_BYTES, WebSearchError, _NoRedirect, _EngineRows, _clean_url


def api_key():
    value = os.environ.get('BRAVE_API_KEY', '').strip()
    if not value:
        path = Path(os.environ.get('BRAVE_API_KEY_FILE', 'data/private/brave-api-key'))
        try:
            value = path.read_text(encoding='utf-8').strip()
        except OSError:
            raise WebSearchError('Set BRAVE_API_KEY or BRAVE_API_KEY_FILE',
                                 details={'reason':'missing_credentials'}) from None
    if not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise WebSearchError('Invalid Brave credential', details={'reason':'invalid_credentials'})
    return value


def request_search(query, count, timeout, *, offset=0):
    """One bounded request; no retries, redirects, or search engine fallback."""
    if not isinstance(query, str) or not 0 < len(query.strip()) <= 500:
        raise ValueError('Query must contain 1..500 characters')
    if type(count) is not int or not 1 <= count <= 20 or type(offset) is not int or not 0 <= offset <= 9:
        raise ValueError('Brave count must be 1..20 and offset 0..9')
    if not 0 < timeout <= 30:
        raise ValueError('Timeout must be 0..30 seconds')
    params = {'q':query.strip(), 'count':count, 'offset':offset,
              'country':os.environ.get('BRAVE_SEARCH_COUNTRY','KR'),
              'search_lang':os.environ.get('BRAVE_SEARCH_LANG','ko')}
    request = Request('https://api.search.brave.com/res/v1/web/search?' + urlencode(params),
                      headers={'Accept':'application/json', 'X-Subscription-Token':api_key()})
    info = {'method':'GET', 'http_transport':'urllib', 'response_format':'json',
            'request_params':params}
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            info['http_status'] = response.status
            if response.status != 200:
                raise WebSearchError('Brave API HTTP failure', details={'reason':'http_error', **info})
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise WebSearchError('Brave response too large', details={'reason':'response_too_large', **info})
        info['response_bytes'] = len(raw)
        payload = json.loads(raw)
        web = payload.get('web') if isinstance(payload,dict) else None
        # Brave may omit web entirely when there are no web results.
        if web is None and isinstance(payload,dict) and isinstance(payload.get('query'),dict):
            web = {'results':[]}
        if not isinstance(web,dict) or not isinstance(web.get('results'),list):
            raise ValueError('Malformed web results')
        results = web['results']
        rows = []
        for row in results:
            if not isinstance(row,dict):
                continue
            url = _clean_url(row.get('url'))
            title, body = row.get('title'), row.get('description','')
            if url and isinstance(title,str) and title.strip() and isinstance(body,str):
                rows.append({'title':title, 'href':url, 'body':body})
        if results and not rows:
            raise ValueError('No usable web result records')
        info.update(result_cards=len(results), parsed_results=len(rows),
                    more_results_available=payload.get('query',{}).get('more_results_available'))
        return raw.decode('utf-8'), _EngineRows(rows, info), info
    except HTTPError as exc:
        raise WebSearchError('Brave API HTTP failure',
                             details={'reason':'http_error', **info, 'http_status':exc.code}) from None
    except WebSearchError:
        raise
    except (ValueError,UnicodeError,AttributeError) as exc:
        raise WebSearchError('Brave response could not be parsed',
                             details={'reason':'malformed_results','error_type':type(exc).__name__, **info}) from None
    except Exception as exc:
        raise WebSearchError('Brave API request failed',
                             details={'reason':'request_failed','error_type':type(exc).__name__, **info}) from None


def search(query, top_k, timeout):
    _, rows, info = request_search(query, top_k, timeout)
    return rows, {'engine_status':{'brave':{'status':'ok', **info}},
                  'engines_returned':['brave'], 'search_complete':True}
