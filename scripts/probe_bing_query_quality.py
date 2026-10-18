"""Small direct-HTTP matrix: request options versus explicit query variants.

An observed target URL is a diagnostic, not an overall search quality score.
This research script does not change production defaults or invoke an agent.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from curl_cffi.requests import Session
from travel_agent.web import _parse_search_html, MAX_RESPONSE_BYTES

CASES=[
    ('museum','국립춘천박물관 관람시간 휴관일 교통','"국립춘천박물관" 관람시간 휴관일 교통','국립춘천박물관','chuncheon.museum.go.kr'),
    ('technical','Python asyncio TaskGroup cancellation official documentation','Python asyncio "TaskGroup" cancellation official documentation','TaskGroup cancellation Python asyncio','docs.python.org/3/library/asyncio-task.html'),
]


def main():
    directory=Path('data/private/search-pipeline/035-probe')/uuid4().hex
    directory.mkdir(parents=True)
    jobs=[]
    for name,query,quoted,focused,target in CASES:
        for variant,actual,options in [('baseline',query,{}),('market',query,{'mkt':'ko-KR' if name=='museum' else 'en-US'}),
                                       ('form',query,{'qs':'n','form':'QBRE'}),('count',query,{'count':'50'}),
                                       ('quoted',quoted,{}),('focused',focused,{})]:
            jobs.append((name,variant,actual,options,target))
    def request(job):
        name,variant,query,options,target=job
        event={'id':uuid4().hex,'case':name,'variant':variant,'tool':'bing_http_query_probe',
               'arguments':{'q':query,**options},'started_at':datetime.now(timezone.utc).isoformat()}
        try:
            with Session(impersonate='edge101') as session:
                response=session.get('https://www.bing.com/search',params={'q':query,**options},timeout=12,allow_redirects=False)
            event.update(http_status=response.status_code,response_bytes=len(response.content))
            if response.status_code!=200 or len(response.content)>MAX_RESPONSE_BYTES:
                event['error']='http_status_or_size'
            else:
                text=response.content.decode('utf-8',errors='replace')
                (directory/(event['id']+'.html')).write_text(text,encoding='utf-8')
                rows=_parse_search_html(text,'bing')
                event.update(rows.details,rows=list(rows),target_found=any(target in r['href'] for r in rows))
        except Exception as exc:
            event['error']=type(exc).__name__
        event['finished_at']=datetime.now(timezone.utc).isoformat()
        return event
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(request,jobs))
    (directory/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in results:
        print(json.dumps({k:v for k,v in r.items() if k!='rows'},ensure_ascii=True))
    print('private_report='+str(directory/'report.json'))


if __name__=='__main__':
    main()
