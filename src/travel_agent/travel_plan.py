"""Versioned trip drafts. Selection confirmation is never price verification."""
from copy import deepcopy
from datetime import date, datetime, timezone
import re
from urllib.parse import urlsplit
from uuid import uuid4

KINDS = {'activity':'일정','lodging':'숙소','cost':'비용','transport':'교통','note':'메모'}
FIELDS = {'kind','title','date','start','end','place','address','amount_won','cost_status','basis','source_url','note'}
TEXT = {'title':160,'place':200,'address':300,'basis':200,'note':1000,'source_url':2000}
PROPS = {k:{'type':'string'} for k in FIELDS-{'amount_won'}}
PROPS.update(kind={'type':'string','enum':list(KINDS)},amount_won={'type':['integer','null'],'minimum':0},
             cost_status={'type':'string','enum':['unknown','estimate','observed']})
PROPS['date'].update(description='YYYY-MM-DD 날짜. 모르면 생략한다.')
PROPS['start'].update(description='HH:MM 시작 시간. 예: 10:00. 모르면 생략한다.')
PROPS['end'].update(description='HH:MM 종료 시간. 예: 12:00. 모르면 생략한다.')
PROPS['amount_won'].update(description='이 항목에 적용되는 원화 합계. 모르면 null. 이미 숙소/교통에 기록한 금액을 별도 비용으로 중복 기록하지 않는다.')
TOOLS = [
 {'type':'function','function':{'name':'plan_read','description':'현재 대화의 여행 계획 초안과 사용자가 선택 확정한 항목을 읽는다. 웹 조회가 아니다.',
  'parameters':{'type':'object','properties':{},'additionalProperties':False}}},
 {'type':'function','function':{'name':'plan_update','description':'대화에서 정한 조건이나 조사한 후보를 계획 초안에 저장/수정한다. 날짜·시간·주소·가격을 추측하지 않는다. 기존 항목 수정은 반환된 id 사용. 선택 확정은 사용자만 한다. 금액이 있으면 원화 합계 amount_won, 적용 인원/기간 basis, estimate/observed/unknown을 명시한다. 숙소/교통에 기록한 금액을 cost 항목에 다시 넣지 않는다.',
  'parameters':{'type':'object','properties':{'items':{'type':'array','minItems':1,'maxItems':20,'items':{'type':'object',
      'properties':{**PROPS,'id':{'type':'string','description':'수정할 기존 항목의 반환된16자리 ID. 임의의 item_1 같은 값을 만들지 않는다.'}},'required':['id','kind','title'],'additionalProperties':False}}},
    'required':['items'],'additionalProperties':False}}}
]
ADD_TOOL=deepcopy(TOOLS[1])
ADD_TOOL['function'].update(name='plan_add',description='새 여행 계획 초안 항목을 추가한다. id는 서버가 자동 발급한다. id를 보내지 않는다. 날짜/시간/가격을 추측하지 않는다. 금액에는 적용 기준 basis와 예상/조회 구분을 기록한다. 같은 비용을 숙소와 별도 비용 항목에 중복 추가하지 않는다.')
ADD_TOOL['function']['parameters']['properties']['items']['items']['properties'].pop('id')
ADD_TOOL['function']['parameters']['properties']['items']['items']['required']=['kind','title']
TOOLS.insert(1,ADD_TOOL)
TOOLS[2]['function']['description']='기존 계획 항목을 수정한다. plan_read 또는 plan_add가 반환한 기존16자리 id를 반드시 사용한다. 새 항목은 plan_add로 추가한다. 수정된 항목은 다시 초안이 되며 선택 확정은 사용자만 한다.'


def blank():
    return {'version':1,'revision':0,'items':[],'updated_at':None}


def validate_item(raw, partial=False):
    if not isinstance(raw,dict) or set(raw)-FIELDS-{'id'}:
        raise ValueError('계획 항목의 필드를 확인해주세요.')
    item=deepcopy(raw)
    if not partial and (not isinstance(item.get('kind'),str) or item['kind'] not in KINDS or not isinstance(item.get('title'),str) or not item['title'].strip()):
        raise ValueError('종류와 항목 이름이 필요합니다.')
    for key,limit in TEXT.items():
        if key in item:
            if not isinstance(item[key],str) or len(item[key])>limit or any(ord(c)<32 and c not in '\n\t' for c in item[key]):
                raise ValueError('계획 항목의 글자 수/형식을 확인해주세요.')
            item[key]=item[key].strip()
    if 'id' in item and (not isinstance(item['id'],str) or not re.fullmatch('[a-f0-9]{16}',item['id'])):
        raise ValueError('저장된 항목 ID를 사용해주세요.')
    if 'date' in item:
        if not isinstance(item['date'],str) or item['date'] and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',item['date']):raise ValueError('날짜는 YYYY-MM-DD 형식입니다.')
        if item['date']:date.fromisoformat(item['date'])
    for key in ('start','end'):
        if isinstance(item.get(key),str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::00)?',item[key]):
            day,clock=item[key].split('T');date.fromisoformat(day)
            if item.get('date') and item['date']!=day:raise ValueError('날짜와 시간이 다른 날을 가리킵니다.')
            item['date']=day;item[key]=clock[:5]
        if key in item and (not isinstance(item[key],str) or item[key] and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',item[key])):
            raise ValueError('시간은 HH:MM 형식입니다.')
    if item.get('start') and item.get('end') and item['end']<item['start']:
        raise ValueError('같은 날의 종료 시간은 시작 이후여야 합니다. 다음 날 일정은 나눠주세요.')
    if 'amount_won' in item and item['amount_won'] is not None and (type(item['amount_won']) is not int or not 0<=item['amount_won']<=10**10):
        raise ValueError('비용은0 이상의 정수 원화입니다.')
    if item.get('kind')=='cost' or item.get('amount_won') is not None:
        if not isinstance(item.get('cost_status','unknown'),str) or item.get('cost_status','unknown') not in {'unknown','estimate','observed'}:raise ValueError('금액 확인 상태를 확인해주세요.')
        if not partial and item.get('amount_won') is not None and (item.get('cost_status','unknown')=='unknown' or not item.get('basis')):
            raise ValueError('금액이 있으면 예상/조회 구분과 인원·기간 등 적용 기준이 필요합니다.')
        if item.get('amount_won') is None and (not partial or 'amount_won' in item):item['cost_status']='unknown'
    url=item.get('source_url','')
    if url:
        u=urlsplit(url)
        if u.scheme not in {'http','https'} or not u.hostname or u.username or u.password or any(c.isspace() for c in url):
            raise ValueError('출처는 인증정보 없는 HTTP(S) 링크만 가능합니다.')
    return item


def validate_call(name,args):
    if not isinstance(args,dict):raise ValueError('계획 도구 인자는 객체여야 합니다.')
    if name=='plan_read':
        if args:raise ValueError('plan_read에는 인자가 없습니다.')
    elif name in {'plan_add','plan_update'}:
        if set(args)!={'items'} or not isinstance(args['items'],list) or not 1<=len(args['items'])<=20:
            raise ValueError('items에1~20개 계획 항목을 넣어주세요.')
        for item in args['items']:
            if not isinstance(item,dict) or (name=='plan_add' and 'id' in item) or (name=='plan_update' and 'id' not in item):raise ValueError('신규는 id 없는 plan_add, 수정은 기존 id가 있는 plan_update를 사용해주세요.')
            validate_item(item,partial=name=='plan_update')
    else:raise ValueError('Unknown plan tool')


def mutate(plan,action,payload,*,model=False,run_id=None):
    """Validate whole mutation before saving; model edits revoke selection confirmation."""
    out=deepcopy(plan)
    if action=='upsert':
        items=payload.get('items')
        if not isinstance(items,list) or not 1<=len(items)<=20:raise ValueError('계획 항목은1~20개씩 저장해주세요.')
        ids=[x.get('id') for x in items if isinstance(x,dict) and x.get('id')]
        if len(ids)!=len(set(ids)):raise ValueError('같은 항목을 한 번만 수정해주세요.')
        for raw in items:
            item=validate_item(raw,partial=bool(raw.get('id')) if isinstance(raw,dict) else False)
            previous=next((x for x in out['items'] if x['id']==item.get('id')),None)
            if item.get('id') and previous is None:raise ValueError('이 계획에 없는 항목입니다.')
            if previous:
                merged=validate_item({k:v for k,v in {**previous,**item}.items() if k in FIELDS|{'id'}})
                changed=any(previous.get(k)!=merged.get(k) for k in FIELDS)
                previous.update(merged)
                if changed:previous.update(confirmed=False,recorded_by='model' if model else 'user',updated_from=run_id)
            else:
                if len(out['items'])>=100:raise ValueError('계획 항목은 최대100개입니다.')
                out['items'].append({**item,'id':uuid4().hex[:16],'confirmed':False,'recorded_by':'model' if model else 'user','updated_from':run_id})
    elif action in {'confirm','delete'} and not model:
        item=next((x for x in out['items'] if x['id']==payload.get('id')),None)
        if item is None:raise ValueError('항목을 찾을 수 없습니다.')
        if action=='confirm':
            if type(payload.get('confirmed')) is not bool:raise ValueError('확정 여부는 true/false입니다.')
            item['confirmed']=payload['confirmed']
        else:out['items'].remove(item)
    else:raise ValueError('지원하지 않는 계획 변경입니다.')
    out['revision']+=1
    out['updated_at']=datetime.now(timezone.utc).isoformat()
    return out


def budget(plan,confirmed=False):
    items=[i for i in plan['items'] if (i['kind']=='cost' or i.get('amount_won') is not None) and (not confirmed or i['confirmed'])]
    return {'observed_won':sum(i['amount_won'] for i in items if i.get('amount_won') is not None and i.get('cost_status')=='observed'),
            'estimated_won':sum(i['amount_won'] for i in items if i.get('amount_won') is not None and i.get('cost_status')=='estimate'),
            'unknown_count':sum(i.get('amount_won') is None for i in items),'item_count':len(items)}


def markdown(plan,confirmed=False):
    def esc(value):
        return str(value or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\\','\\\\').replace('|','\\|').replace('\n',' / ').replace('[','\\[').replace(']','\\]')
    lines=['# 여행 계획서','', '**선택 확정 항목**' if confirmed else '**초안 + 선택 확정 항목**',
           '','선택 확정은 예약 완료나 가격 검증을 뜻하지 않습니다. 미정인 정보는 그대로 표시합니다.','']
    for kind,label in KINDS.items():
        lines+=['## '+label,'','| 항목 | 날짜·시간 | 장소·내용 | 상태 |','|---|---|---|---|']
        items=sorted((i for i in plan['items'] if i['kind']==kind and (not confirmed or i['confirmed'])),key=lambda i:(i.get('date') or '9999',i.get('start') or '99:99',i['title']))
        if not items:lines+=['| 미정 | 미정 | 미정 | 미정 |']
        for i in items:
            when=' '.join(filter(None,[i.get('date'),i.get('start'),('~ '+i['end']) if i.get('end') else None])) or '미정'
            detail=' · '.join(filter(None,[i.get('place'),i.get('address'),i.get('note')])) or '미정'
            if kind=='cost' or i.get('amount_won') is not None:detail+=' · '+(f"{i['amount_won']:,}원" if i.get('amount_won') is not None else '금액 미확인')+' · '+{'estimate':'예상','observed':'조회 금액','unknown':'미확인'}.get(i.get('cost_status'),'미확인')+' · '+i.get('basis','적용 기준 미정')
            lines+=['| '+' | '.join(map(esc,[i['title'],when,detail,'선택 확정' if i['confirmed'] else '초안']))+' |']
            if i.get('source_url'):lines+=['','출처: '+esc(i['source_url']),'']
        lines+=['']
    b=budget(plan,confirmed)
    lines+=['## 비용 요약','',f"- 조회 금액 합계: {b['observed_won']:,}원",f"- 예상 금액 합계: {b['estimated_won']:,}원",f"- 금액 미확인: {b['unknown_count']}개",'','입력된 원화 비용 항목만 합산하며 미확인 비용은0원으로 취급하지 않습니다.']
    return '\n'.join(lines)+'\n'
