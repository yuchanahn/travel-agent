"""Project OpenBnB results into complete, bounded records for the model."""
import json
from datetime import date
from .memory import canonical
from .lodging_evidence import listing_key


GUIDANCE = ('OpenBnB는 Airbnb 공개 페이지의 숙소 후보 검색·상세 조회다. 국내 지역은 가능하면 '
            '공식 영문 행정구역명과 도·South Korea를 함께 사용하고 모르는 지명은 지어내지 않는다. '
            '좌표 검색은 주변 지역도 포함하므로 행정구역 내부라고 단정하지 않는다. '
            '가격 accessibilityLabel을 통화·total 표기까지 따옴표로 그대로 복사하고 단위를 바꾸지 않는다. '
            '결제 총액·예약 재고·계절 시설 운영은 미확인이다. '
            '사용자가 날짜를 미정이라고 하면 날짜를 만들어 호출하지 않는다. '
            '요청 날짜·인원은 request_context일 뿐 반환 가격의 적용 조건이 검증됐다는 뜻은 아니다. '
            '상세의 missing_sections는 조회하지 못한 정보이며 시설 Not included는 제공되지 않는 항목이다. '
            '전달된 후보는 서버 순서이며 omitted_count만큼 모델에 전달되지 않은 후보가 있다.')


def pack_result(result, max_bytes):
    outer = {k:v for k,v in result.items() if k not in {'raw_result','text'}}
    outer['citation']='['+str(result.get('id',''))+']'
    try:
        payload = json.loads(result.get('text',''))
        if not isinstance(payload,dict): raise ValueError()
    except (TypeError, ValueError):
        return canonical({**outer,'error':'OpenBnB returned invalid JSON','truncated':True})
    data = {'source':'Airbnb public page','price_status':'page_display_only',
            'location_status':'geocoded_area_not_verified_administrative_boundary'}
    outer.update(data=data,truncated=False)
    context=result.get('request_context') or {}
    dates_known=False
    nights=None
    try:
        nights=(date.fromisoformat(context['checkout'])-date.fromisoformat(context['checkin'])).days
        dates_known=nights>0 and type(context.get('adults')) is int and context['adults']>0
    except (KeyError,TypeError,ValueError):pass
    data.update(requested_nights=nights if dates_known else None,
                price_conditions_verified=False,
                price_withheld_reason=None if dates_known else 'missing_valid_dates_or_adults')
    fits = lambda: len(canonical(outer).encode('utf-8')) <= max_bytes
    if payload.get('error'):
        data['error']=payload['error']
    elif result.get('remote_tool')=='airbnb_search':
        rows=payload.get('searchResults',[])
        if not isinstance(rows,list):rows=[]
        cursors=payload.get('paginationInfo',{}).get('pageCursors',[])
        data.update(search_url=payload.get('searchUrl'),results=[],total_returned=len(rows),
                    omitted_count=len(rows),page_cursors=cursors)
        for row in rows:
            listing=row.get('demandStayListing',{})
            item={'id':row.get('id'),'url':row.get('url'),'listing_key':listing_key(row.get('url')),
                  'name':listing.get('description',{}).get('name',{}).get('localizedStringWithTranslationPreference'),
                  'coordinates':listing.get('location',{}).get('coordinate'),
                  'price':row.get('structuredDisplayPrice') if dates_known else None, 'rating':row.get('avgRatingA11yLabel'),
                  'room':row.get('structuredContent',{}).get('primaryLine'), 'badges':row.get('badges')}
            data['results'].append(item);data['omitted_count']-=1
            if not fits():
                data['results'].pop();data['omitted_count']+=1
                break
        outer['truncated']=bool(data['omitted_count'])
    else:
        sections=payload.get('details',[])
        expected={'LOCATION_DEFAULT','POLICIES_DEFAULT','HIGHLIGHTS_DEFAULT','DESCRIPTION_DEFAULT','AMENITIES_DEFAULT'}
        missing={s.get('id') for s in sections if not any(v for k,v in s.items() if k!='id')}
        missing.update(expected-{s.get('id') for s in sections})
        data.update(listing_url=payload.get('listingUrl'),listing_key=listing_key(payload.get('listingUrl')),sections=[],
                    missing_sections=sorted(missing),
                    omitted_sections=[])
        for section in sections:
            if section.get('id') in data['missing_sections']:continue
            data['sections'].append(section)
            if not fits():
                data['sections'].pop();data['omitted_sections'].append(section.get('id'))
        outer['truncated']=bool(data['omitted_sections'])
    if not fits():
        return canonical({'id':result.get('id'),'error':'OpenBnB metadata exceeds packet limit','truncated':True})
    return canonical(outer)
