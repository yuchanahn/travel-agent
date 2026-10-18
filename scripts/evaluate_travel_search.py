"""Controlled public-search breadth and representation experiments; private logs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from travel_agent.memory import canonical, MemoryStore
from travel_agent.web import web_search, WebSearchError
from travel_agent.web_context import format_web_result
from travel_agent.web_read import fetch_public_page, extract_page, web_read


def measure_tokens(content):
    """Actual Qwen raw-prompt count; not chat-template tokens or answer quality."""
    payload = {'model':os.environ.get('OLLAMA_MODEL','qwen3.5:4b-q4_K_M'),
               'prompt':'Evidence representation measurement:\n'+content, 'raw':True, 'stream':False,
               'options':{'num_ctx':65536,'num_predict':1,'temperature':0}}
    request = Request(os.environ.get('OLLAMA_BASE_URL','http://127.0.0.1:11434')+'/api/generate',
                      data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    started=time.perf_counter()
    with urlopen(request,timeout=90) as response:
        result=json.load(response)
    return {'utf8_bytes':len(content.encode()),'prompt_eval_count':result.get('prompt_eval_count'),
            'output_tokens':result.get('eval_count'),'elapsed_ms':round((time.perf_counter()-started)*1000)}


def search_one(query, top_k):
    event={'id':uuid4().hex,'tool':'web_search','arguments':{'query':query,'top_k':top_k},
           'started_at':datetime.now(timezone.utc).isoformat()}
    started=time.perf_counter()
    try:
        event['result']=web_search(query,top_k=top_k,max_bytes=10000,provider='http',backend='bing')
    except WebSearchError as exc:
        event['result']={'error':str(exc),**exc.details}
    event.update(finished_at=datetime.now(timezone.utc).isoformat(),elapsed_ms=round((time.perf_counter()-started)*1000))
    return event


def breadth(events):
    hits=[hit for event in events for hit in event['result'].get('hits',[])]
    urls=set(hit['url'] for hit in hits)
    return {'requests':len(events),'returned_rows':len(hits),'unique_urls':len(urls),
            'unique_hosts':len(set(urlsplit(url).hostname for url in urls)),
            'failures':sum('error' in event['result'] for event in events),
            'limits':'URL/host diversity is not relevance or candidate coverage.'}


def quality_gate(result):
    gate={'loop_completed':result['status']=='completed',
          'citation_ids_valid':result['citation_ids_valid'],
          'any_page_read':any(source.get('page_fetched') for source in result['web_sources']),
          'manual_fact_review_required':True,
          'note':'These necessary checks do not prove the answer meets all travel constraints.'}
    gate['automatic_pass']=all(gate[key] for key in ('loop_completed','citation_ids_valid','any_page_read'))
    return gate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case')
    parser.add_argument('--tokens',action='store_true')
    parser.add_argument('--agent',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('data/private/travel-search')/(uuid4().hex+'.json'))
    args=parser.parse_args()
    specification=json.loads(Path('examples/travel-search-cases.json').read_text(encoding='utf-8'))
    if args.case and args.case not in {case['id'] for case in specification['cases']}:
        parser.error('Unknown evaluation case')
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'specification':specification,'cases':[]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save():
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    for case in specification['cases']:
        if args.case and args.case!=case['id']:
            continue
        tick=time.perf_counter()
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(search_one,query,5 if i==0 else 3) for i,query in enumerate(case['queries'])]
            events=[future.result() for future in futures]
        entry={'case':case,'search_events':events,'parallel_wall_ms':round((time.perf_counter()-tick)*1000)}
        single3=deepcopy(events[0]); single3['result']['hits']=single3['result'].get('hits',[])[:3]
        single3['derived_view']='First3 from the same top5 response; not a new HTTP request'
        multi=[deepcopy(single3), *events[1:]]
        entry['breadth']={'single3':breadth([single3]),'single5':breadth(events[:1]),'multi3x3':breadth(multi)}
        entry['contexts']={style:'\n\n'.join('Query: '+event['arguments']['query']+'\n'+format_web_result(event['result'],style) for event in multi)
                           for style in ('full_json','compact_json','compact_md')}
        report['cases'].append(entry); save()
        print(json.dumps({'case':case['id'],'breadth':entry['breadth'],'parallel_wall_ms':entry['parallel_wall_ms']},ensure_ascii=True),flush=True)
        if args.tokens:
            entry['representation_tokens']={style:measure_tokens(content) for style,content in entry['contexts'].items()};save()
        # Prefer an actual official source from this experiment; no hard-coded URL fetch.
        hits=[hit for event in events for hit in event['result'].get('hits',[])]
        named_terms={term for q in case['queries'] for term in q.split() if len(term)>=4}
        candidates=[hit for hit in hits if (urlsplit(hit['url']).hostname or '').endswith('.go.kr')
                    and any(term in hit['title'] for term in named_terms)]
        selected=candidates[0] if candidates else None
        if selected:
            read_event={'id':uuid4().hex,'tool':'web_read','arguments':{'source_id':selected['id'],'query':'관람시간 휴관일 교통 입장료'},
                        'url':selected['url'],'started_at':datetime.now(timezone.utc).isoformat()}
            try:
                body, info=fetch_public_page(selected['url'])
                private_body=args.output.parent/(read_event['id']+'.html');private_body.write_bytes(body)
                formats={'html':body.decode('utf-8',errors='replace'),
                         'txt':extract_page(body,selected['url'],'txt'),
                         'markdown':extract_page(body,selected['url'],'markdown')}
                read_event.update(info,format_bytes={key:len(value.encode()) for key,value in formats.items()},
                                  extracted_text=formats['txt'],extracted_markdown=formats['markdown'])
                # Reuse exactly the same response for the focused reader: one HTTP download.
                from unittest.mock import patch
                with patch('travel_agent.web_read.fetch_public_page',return_value=(body,info)):
                    read_event['result']=web_read(selected,read_event['arguments']['query'])
                formats['focused_excerpt']=read_event['result']['text']
                if args.tokens:
                    read_event['format_tokens']={key:measure_tokens(value) if len(value.encode())<=120000 else {'skipped':'exceeds bounded token experiment input'}
                                               for key,value in formats.items()}
            except (WebSearchError,OSError,ValueError) as exc:
                read_event['error']={'type':type(exc).__name__,**getattr(exc,'details',{})}
            read_event['finished_at']=datetime.now(timezone.utc).isoformat()
            entry['read_event']=read_event;save()
        if args.agent:
            from travel_agent.agent import run_agent
            from travel_agent.trace import read_trace
            with MemoryStore(args.output.parent/'agent.sqlite3') as store:
                result=run_agent(store,'demo',case['id'],case['question'],web_tool_format='compact_md',max_steps=6,max_tool_calls=8,timeout=180)
            entry['agent']={'result':result,'trace':read_trace('data/private/traces',result['request_id'])};save()
            entry['quality_gate']=quality_gate(result)
            save()
            print(json.dumps({'case':case['id'],'agent':result},ensure_ascii=True),flush=True)
        print(json.dumps({'case':case['id'],'tokens':entry.get('representation_tokens'),'page_tokens':entry.get('read_event',{}).get('format_tokens'),
                          'read_error':entry.get('read_event',{}).get('error')},ensure_ascii=True),flush=True)
    save()
    return 1 if args.agent and any(not entry.get('quality_gate',{}).get('automatic_pass') for entry in report['cases']) else 0


if __name__=='__main__':
    raise SystemExit(main())
