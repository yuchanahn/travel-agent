"""Keep complete Brave search records and extra snippets from the official MCP."""
import hashlib
import json
from .memory import canonical
from .web import _clean_url

GUIDANCE = ('일반 여행·펜션 후보 탐색은 이 웹검색을 우선한다. 한국 지명은 사용자의 한국어 표기를 유지한다. '
            '처음에는 후보를 넓게 찾고, 이후 후보 이름으로 필요한 주소·시설·공식 안내를 확인한다. '
            '한국 여행 검색은 country=KR, search_lang=ko, ui_lang=ko-KR를 명시한다. '
            '반환 hits의 web: ID로 web_read를 사용할 수 있다. 검색 발췌는 본문 확인이 아니다.')


def pack_result(result, max_bytes=48000):
    if max_bytes < 256:
        raise ValueError('Search packet budget must be at least 256 bytes')
    wire = result.get('raw_result', {})
    hits, seen = [], set()
    for block in wire.get('content', []):
        if block.get('type') != 'text':
            continue
        try:
            item = json.loads(block.get('text', ''))
        except (ValueError, TypeError):
            continue
        if not isinstance(item, dict):
            continue
        url = _clean_url(item.get('url'))
        if not url or url in seen or not isinstance(item.get('title'), str):
            continue
        seen.add(url)
        extras = item.get('extra_snippets')
        hits.append({'id': 'web:'+hashlib.sha256(url.encode()).hexdigest()[:16],
            'title': item['title'], 'url': url,
            'snippet': item.get('description', '') if isinstance(item.get('description'), str) else '',
            'extra_snippets': [text for text in extras if isinstance(text, str)] if isinstance(extras, list) else []})
    packet = {'id': result['id'], 'content_kind': 'search_snippet', 'provider': 'brave_mcp',
        'page_fetched': False, 'verified_current': False,
        'web_search_performed': not result.get('is_error', False),
        'hits': [], 'available_results': len(hits), 'returned_results': 0, 'omitted_results': len(hits),
        'truncated': bool(hits), 'error': result.get('error')}
    if packet['error'] is None:
        packet.pop('error')
    if not hits and not result.get('is_error'):
        packet['error'] = 'MCP returned no usable web result records'
    if len(canonical(packet).encode('utf-8')) > max_bytes:
        return canonical({'error': 'Search metadata exceeds packet budget', 'hits': [], 'truncated': True})
    # Never leave a broken sentence/JSON object. Skip a whole oversized record.
    for hit in hits:
        trial = {**packet, 'hits': [*packet['hits'], hit]}
        if len(canonical(trial).encode('utf-8')) <= max_bytes-64:
            packet['hits'].append(hit)
    packet['omitted_results'] = len(hits)-len(packet['hits'])
    packet['returned_results'] = len(packet['hits'])
    packet['truncated'] = bool(packet['omitted_results'])
    return canonical(packet)
