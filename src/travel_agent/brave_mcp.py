"""Keep complete Brave search records and extra snippets from the official MCP."""
import hashlib
import json
from .memory import canonical
from .web import _clean_url

GUIDANCE = ('일반 여행·펜션 후보 탐색은 이 웹검색을 우선한다. 한국 지명은 사용자의 한국어 표기를 유지한다. '
            '숙소 비교의 첫 검색은 count=20으로 넓게 수집하고, 부족하면 다른 검색어나 offset으로 추가 탐색한다. '
            '검색 결과 수는 숙소 수가 아니다. 같은 숙소의 여러 링크를 묶고, 처음 보인 3곳에 바로 고정하지 않는다. '
            '후보 이름으로 주소·시설·공식 안내를 추가 검색하며 예약 사이트와 공식 사이트를 함께 활용한다. '
            '한국 여행 검색은 country=KR, search_lang=ko, ui_lang=ko-KR를 명시한다. '
            'document_catalog는 자동 수집한 주변 문서 목록이다. 제목·anchors·description·parents·status로 읽을 문서를 선택한다. '
            'ready 문서의 web: ID를 web_read로 요청하면 저장된 본문을 읽는다. 목록 수신은 본문을 읽은 것이 아니다. '
            '필요한 근거가 없으면 후보 이름으로 추가 검색할 수 있다. 검색 발췌는 본문 확인이 아니다.')


def pack_result(result, max_bytes=96000):
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
    if 'document_collection' in result:
        collection = result['document_collection']
        metadata = {k:v for k,v in collection.items() if k != 'documents'}
        trial = {**packet, 'document_collection': metadata, 'document_catalog': [], 'document_catalog_omitted': len(collection['documents'])}
        if len(canonical(trial).encode()) <= max_bytes:
            packet = trial
            for doc in collection['documents']:
                trial = {**packet, 'document_catalog': [*packet['document_catalog'], doc]}
                if len(canonical(trial).encode()) <= max_bytes-64:
                    packet['document_catalog'].append(doc)
            packet['document_catalog_omitted'] = len(collection['documents'])-len(packet['document_catalog'])
        else:
            # Search hits retain precedence, but omission must remain visible.
            packet['document_catalog_omitted'] = len(collection['documents'])
    return canonical(packet)
