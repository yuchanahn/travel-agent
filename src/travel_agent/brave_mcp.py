"""Keep complete Brave search records and extra snippets from the official MCP."""
import hashlib
import json
from .memory import canonical
from .web import _clean_url
from .search_selection import select

GUIDANCE = ('일반 여행·펜션 후보 탐색은 이 웹검색을 우선한다. 한국 지명은 사용자의 한국어 표기를 유지한다. '
            '숙소 비교의 첫 검색은 count=20으로 넓게 수집하고, 부족하면 다른 검색어나 offset으로 추가 탐색한다. '
            '검색 결과 수는 숙소 수가 아니다. 같은 숙소의 여러 링크를 묶고, 처음 보인 3곳에 바로 고정하지 않는다. '
            '후보 이름으로 주소·시설·공식 안내를 추가 검색하며 예약 사이트와 공식 사이트를 함께 활용한다. '
            '한국 여행 검색은 country=KR, search_lang=ko, ui_lang=ko-KR를 명시한다. '
            'document_catalog는 자동 수집한 주변 문서 목록이다. 제목·anchors·description·parents·status로 읽을 문서를 선택한다. '
            'ready 문서의 web: ID를 web_read로 요청하면 저장된 본문을 읽는다. 목록 수신은 본문을 읽은 것이 아니다. '
            '필요한 근거가 없으면 후보 이름으로 추가 검색할 수 있다. 검색 발췌는 본문 확인이 아니다.')


def pack_result(result, max_bytes=24000):
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
    available=len(hits)
    hits,selection=select(hits,result.get('search_query',''),30)
    if 'selected_hits' in result:hits=result['selected_hits']
    allowed=result.get('selected_source_ids')
    if allowed is not None:hits=[h for h in hits if h['id'] in allowed]
    packet = {'id': result['id'], 'content_kind': 'search_snippet', 'provider': 'brave_mcp',
        'page_fetched': False, 'verified_current': False,
        'web_search_performed': not result.get('is_error', False),
        'hits': [], 'available_results': available, 'returned_results': 0, 'omitted_results': available,
        'selection':selection,
        'truncated': bool(hits), 'error': result.get('error')}
    if packet['error'] is None:
        packet.pop('error')
    if not available and not result.get('is_error'):
        packet['error'] = 'MCP returned no usable web result records'
    if len(canonical(packet).encode('utf-8')) > max_bytes:
        return canonical({'error': 'Search metadata exceeds packet budget', 'hits': [], 'truncated': True})
    # Never leave a broken sentence/JSON object. Skip a whole oversized record.
    for hit in hits:
        trial = {**packet, 'hits': [*packet['hits'], hit]}
        if len(canonical(trial).encode('utf-8')) <= max_bytes-64:
            packet['hits'].append(hit)
    packet['omitted_results'] = available-len(packet['hits'])
    packet['returned_results'] = len(packet['hits'])
    packet['truncated'] = bool(packet['omitted_results'])
    if 'document_collection' in result:
        collection = result['document_collection']
        metadata = {k:v for k,v in collection.items() if k != 'documents'}
        trial = {**packet, 'document_collection': metadata, 'document_catalog': [], 'document_catalog_omitted': len(collection['documents'])}
        if len(canonical(trial).encode()) <= max_bytes:
            packet = trial
            for doc in collection['documents']:
                if 'selected_catalog_ids' in result and doc['id'] not in result['selected_catalog_ids']:continue
                compact=dict(doc)
                description=compact.get('description','')
                if len(description)>240:
                    compact['description']=description[:240]
                    compact['description_truncated']=True
                trial = {**packet, 'document_catalog': [*packet['document_catalog'], compact]}
                if len(canonical(trial).encode()) <= max_bytes-64:
                    packet['document_catalog'].append(compact)
            packet['document_catalog_omitted'] = len(collection['documents'])-len(packet['document_catalog'])
        else:
            # Search hits retain precedence, but omission must remain visible.
            packet['document_catalog_omitted'] = len(collection['documents'])
    return canonical(packet)


def select_batch(results,query):
    """Bound a parallel Brave batch to30 unique URLs across search responses."""
    pool={};packet_duplicates=0
    batch_count=sum(r.get('model_adapter')=='brave_search' for _,r in results)
    for _,result in results:
        if result.get('model_adapter')!='brave_search':continue
        packet=json.loads(pack_result(result,max_bytes=96000))
        packet_duplicates+=packet.get('selection',{}).get('exact_sentences_removed',0)
        for hit in packet.get('hits',[]):
            if hit['id'] in pool:
                pool[hit['id']]['extra_snippets'].extend([hit.get('snippet',''),*hit.get('extra_snippets',[])])
            else:pool[hit['id']]=hit
    search_ids=set(pool)
    for _,result in results:
        if result.get('model_adapter')!='brave_search':continue
        for doc in result.get('document_collection',{}).get('documents',[]):
            if doc.get('id') not in pool:
                pool[doc['id']]={'id':doc['id'],'title':doc.get('title',''),'url':doc.get('url',''),
                                 'snippet':doc.get('description',''),'catalog_only':True}
    combined_query=query+' '+' '.join(r.get('search_query','') for _,r in results)
    ranked,stats=select(list(pool.values()),combined_query,30)
    allowed={h['id'] for h in ranked};delivered=set()
    for _,result in results:
        if result.get('model_adapter')!='brave_search':continue
        packet=json.loads(pack_result(result,max_bytes=96000))
        own=({h['id'] for h in packet.get('hits',[])}&allowed)-delivered
        result['selected_source_ids']=sorted(own)
        result['selected_hits']=[h for h in ranked if h['id'] in own and h['id'] in search_ids]
        result['packet_byte_budget']=min(24000,30000//max(1,batch_count))
        delivered.update(own)
    for _,result in results:
        if result.get('model_adapter')!='brave_search':continue
        own=({d['id'] for d in result.get('document_collection',{}).get('documents',[])}&allowed)-delivered
        result['selected_catalog_ids']=sorted(own);delivered.update(own)
    stats['exact_sentences_removed']+=packet_duplicates
    return {'unique_candidates':len(pool),'selected_candidates':len(allowed),'batch_byte_budget':30000,**stats}
