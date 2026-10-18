"""Live local-model agent runs; public questions, private trajectories, no seeded tool calls."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys

from travel_agent.agent import run_agent
from travel_agent.llm_config import generation_options
from travel_agent.memory import MemoryStore
from travel_agent.trace import read_trace


def summarize_trace(trace):
    starts = {event['span']:event for event in trace if event['kind']=='tool_start'}
    calls = []
    for event in trace:
        if event['kind'] not in {'tool_end','tool_error'}:
            continue
        start=starts.get(event['span'],{})
        calls.append({'span':event['span'],'name':event['name'],
                      'tool_call_id':start.get('tool_call_id'),
                      'arguments':start.get('arguments'),
                      'started_at':start.get('timestamp'), 'finished_at':event.get('timestamp'),
                      'elapsed_seconds':event.get('elapsed_seconds_call'),
                      'result':event['result']})
    return calls


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',required=True,help='Unique run label; existing reports are never overwritten')
    parser.add_argument('--case',help='Case ID; omit for all three existing travel questions')
    parser.add_argument('--max-steps',type=int,default=6)
    parser.add_argument('--max-tool-calls',type=int,default=8)
    parser.add_argument('--timeout',type=float,default=180)
    args=parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{1,50}',args.phase):
        parser.error('phase must be lowercase letters, numbers or hyphens')
    cases=json.loads(Path('examples/travel-search-cases.json').read_text(encoding='utf-8'))['cases']
    if args.case:
        cases=[case for case in cases if case['id']==args.case]
        if not cases:
            parser.error('Unknown case ID')
    output=Path('data/private/agent-brave-evaluation')/args.phase
    output.mkdir(parents=True,exist_ok=True)
    report_path=output/'report.json'
    if report_path.exists():
        parser.error('Report already exists; choose a new phase')
    report={'started_at':datetime.now(timezone.utc).isoformat(),'phase':args.phase,
            'synthetic_public_questions':True,
            'model':os.environ.get('OLLAMA_MODEL','qwen3.5:4b-q4_K_M'),
            'options':generation_options(),'provider':os.environ.get('WEB_SEARCH_PROVIDER','brave'),
            'max_steps':args.max_steps,'max_tool_calls':args.max_tool_calls,'timeout':args.timeout,'cases':[]}
    def save():
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    for case in cases:
        print('\n질문: '+case['question'],flush=True)
        with MemoryStore(output/'memory.sqlite3') as store:
            result=run_agent(store,'public-eval',case['id'],case['question'],mode='bm25',
                             max_steps=args.max_steps,max_tool_calls=args.max_tool_calls,timeout=args.timeout,
                             trace_dir=output/'traces')
        trace=read_trace(output/'traces',result['request_id'])
        calls=summarize_trace(trace)
        checks={'loop_completed':result['status']=='completed','citation_ids_valid':result['citation_ids_valid'],
                'search_performed':result['web_search_performed'],
                'page_read_count':sum(bool(s.get('page_fetched')) for s in result['web_sources']),
                'tool_errors':sum('error' in call['result'] for call in calls),
                'parallel_batch_requested':any(e['kind']=='tool_batch_start' and e['count']>1 for e in trace),
                'manual_fact_review':'pending; IDs and loop completion do not establish factual support'}
        checks['mechanical_gate']=all(checks[k] for k in ('loop_completed','citation_ids_valid','search_performed')) and checks['page_read_count']>0
        report['cases'].append({'case':case,'result':result,'calls':calls,'checks':checks})
        save()
        print('상태: '+result['status'],flush=True)
        print('답변:\n'+(result.get('answer') or result.get('partial_answer') or '[최종 답변 없음]'),flush=True)
        print('검사: '+json.dumps(checks,ensure_ascii=False),flush=True)
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    save()
    return 0 if all(entry['checks']['mechanical_gate'] for entry in report['cases']) else 1


if __name__=='__main__':
    raise SystemExit(main())
