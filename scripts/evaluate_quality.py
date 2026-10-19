"""Compare pinned full source snapshots with frozen evidence and actual model calls.

All reports/snapshots stay under data/private. No web conversations are created.
Rubrics are manually reviewed afterward; completed is not a factual pass.
"""
import argparse
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def snapshot(ref, folder):
    commit = subprocess.check_output(['git', 'rev-parse', ref + '^{commit}'], cwd=ROOT, text=True).strip()
    archive = subprocess.check_output(['git', 'archive', '--format=zip', commit, 'src/travel_agent'], cwd=ROOT)
    folder.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(BytesIO(archive)) as package:
        for item in package.infolist():
            target = (folder / item.filename).resolve()
            if not target.is_relative_to(folder.resolve()):
                raise ValueError('Snapshot entry outside destination')
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(package.read(item))
    return commit


def worker(args):
    # Each child imports one complete snapshot in a fresh interpreter.
    sys.path.insert(0, str(Path(args.source).resolve() / 'src'))
    from unittest.mock import patch
    from travel_agent.agent import run_agent
    from travel_agent.memory import MemoryStore, build_bm25_index
    from travel_agent.llm_client import settings
    import travel_agent.llm_client as llm_client
    case = json.loads(Path(args.case).read_text(encoding='utf-8'))
    folder = Path(args.worker_output).resolve()
    private_root = (ROOT / 'data/private').resolve()
    if not folder.is_relative_to(private_root):
        raise ValueError('Worker evidence must remain private')
    folder.mkdir(parents=True, exist_ok=False)
    fixture = case.get('page')
    requests = []
    http_calls = []
    original_urlopen = llm_client.urlopen
    def observed_open(request, **kwargs):
        def capture(status, headers):
            http_calls.append({'status':status,'headers':{k.lower():v for k,v in headers.items()
                if k.lower().startswith(('x-routed','x-fallback','x-cache','retry-after','x-ratelimit'))}})
        try:
            response=original_urlopen(request,**kwargs)
            capture(response.status,response.headers)
            return response
        except HTTPError as exc:
            capture(exc.code,exc.headers)
            raise
    def fetch(url, timeout=12):
        requests.append(url)
        if not fixture or url != fixture['source']['url']:
            raise ValueError('URL not present in frozen evidence')
        return fixture['html'].encode(), {'method':'GET', 'http_status':200, 'fixture':True}
    def search(*a, **kw):
        if not fixture:
            raise ValueError('No frozen web search evidence')
        return {'status':'ok','hits':[{**fixture['source'],'snippet':'합성 숙소의 객실별 정책 원문'}],
            'searched_at':'2026-10-19T00:00:00+00:00','content_kind':'search_snippet',
            'page_fetched':False,'search_complete':True,'engines_returned':['fixture']}
    class NoMCP:
        routes = {}
        tools = []
        status = []
        adapters = {}
    config = settings()
    started = datetime.now(timezone.utc).isoformat()
    # tempfile cleans only this explicitly bounded private scratch directory.
    with tempfile.TemporaryDirectory(prefix='memory-', dir=folder) as scratch:
        with MemoryStore(Path(scratch)/'memory.sqlite3') as store:
            if case.get('events'):
                store.add('synthetic','quality',case['events'])
                build_bm25_index(store,'synthetic','quality')
            with patch('travel_agent.web_read.fetch_public_page',side_effect=fetch), patch('travel_agent.agent.web_search',side_effect=search), patch('travel_agent.llm_client.urlopen',side_effect=observed_open):
                result=run_agent(store,'synthetic','quality',case['query'],
                    summary=case.get('summary',''), history=case.get('history',[]),
                    prior_sources=[fixture['source']] if fixture else [],
                    prior_mcp_sources=case.get('mcp_sources',[]), mode='bm25',
                    enable_web=bool(fixture), max_steps=8, max_tool_calls=8,
                    timeout=120, trace_dir=folder/'traces', mcp_registry=NoMCP())
    dump(folder/'result.json', {'started_at':started, 'result':result,
        'provider':{k:config[k] for k in ('provider','model')}, 'fixture_fetches':requests,
        'http_calls':http_calls, 'scratch_memory_deleted':not Path(scratch).exists()})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--cases',type=Path,default=ROOT/'examples/quality-cases.json')
    parser.add_argument('--baseline',default='5e9c79c')
    parser.add_argument('--current',default='8945ebf')
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--resume',action='store_true',help='Continue unexecuted slots; never retry an executed slot')
    parser.add_argument('--continue-after-provider-errors',action='store_true')
    parser.add_argument('--interval',type=float,default=0,help='Seconds between independent workers, outside model timeout')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--source',help=argparse.SUPPRESS)
    parser.add_argument('--case',help=argparse.SUPPRESS)
    parser.add_argument('--worker-output',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:
        worker(args)
        return
    if not args.output or not args.output.resolve().is_relative_to((ROOT/'data/private').resolve()):
        parser.error('--output must be a new directory under data/private')
    if not 1 <= args.repeats <= 10:
        parser.error('--repeats must be 1..10')
    if not 0 <= args.interval <= 60:
        parser.error('--interval must be 0..60 seconds')
    folder=args.output.resolve()
    cases=json.loads(args.cases.read_text(encoding='utf-8'))
    if args.resume:
        report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
        if report['cases']!=cases or report['repeats']!=args.repeats:
            raise ValueError('Resume must preserve frozen cases and repeat count')
        for version,ref in [('baseline',args.baseline),('current',args.current)]:
            commit=subprocess.check_output(['git','rev-parse',ref+'^{commit}'],cwd=ROOT,text=True).strip()
            if report['snapshots'][version]!=commit:
                raise ValueError('Resume must preserve source snapshots')
        if report.get('stopped_reason'):
            report.setdefault('stop_history',[]).append(report.pop('stopped_reason'))
        report.setdefault('protocol_amendments',[]).append({'at':datetime.now(timezone.utc).isoformat(),
            'continue_unexecuted_slots_after_provider_errors':args.continue_after_provider_errors,
            'interval':args.interval,'note':'Executed errors are retained, never retried. Same questions/evidence/commits/rubric. Capture routing headers on subsequent calls.'})
        dump(folder/'report.json',report)
    else:
        folder.mkdir(parents=True,exist_ok=False)
        snapshots={v:snapshot(ref,folder/'snapshots'/v) for v,ref in [('baseline',args.baseline),('current',args.current)]}
        report=None
    schedule=[]
    for repeat in range(args.repeats):
        for index,case in enumerate(cases):
            order=('baseline','current') if (index+repeat)%2==0 else ('current','baseline')
            schedule.extend({'case_id':case['id'],'repeat':repeat,'version':v} for v in order)
    if report is None:
        report={'snapshots':snapshots,'repeats':args.repeats,'cases':cases,'schedule':schedule,'runs':[],
        'limits':{'model_calls':8,'tool_calls':8,'timeout':120,'temperature':0,'output_tokens':4096},
        'grading':'predeclared binary rubric; manual, not blinded; provider failures excluded from paired factual scores'}
        dump(folder/'report.json',report)  # Freeze protocol and expected facts before any live model call.
        dump(folder/'protocol.json',report)
    env=os.environ.copy()
    if 'LLM_CONFIG_FILE' not in env:
        env['LLM_CONFIG_FILE']=str(ROOT/'data/private/llm-config.json')
    env['AGENT_MAX_OUTPUT_TOKENS']='4096'
    for item in schedule:
        if any(all(run[k]==item[k] for k in ('case_id','repeat','version')) for run in report['runs']):
            continue
        if args.interval:
            time.sleep(args.interval)
        case=next(c for c in cases if c['id']==item['case_id'])
        case_path=folder/(case['id']+'.json')
        dump(case_path,case)
        run_folder=folder/(str(item['repeat']+1)+'-'+case['id']+'-'+item['version'])
        command=[sys.executable,str(Path(__file__).resolve()),'--worker','--source',str(folder/'snapshots'/item['version']),
            '--case',str(case_path),'--worker-output',str(run_folder)]
        process=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=150)
        if process.returncode:
            dump(run_folder/'worker-error.json',{'stdout':process.stdout,'stderr':process.stderr})
            report['worker_error']={**item,'returncode':process.returncode}
            dump(folder/'report.json',report)
            raise RuntimeError('Worker failed; inspect private diagnostics')
        run={**item,**json.loads((run_folder/'result.json').read_text(encoding='utf-8')),'review':{}}
        report['runs'].append(run)
        dump(folder/'report.json',report)
        print(json.dumps({**item,'status':run['result']['status'],'model_calls':run['result']['model_calls'],
            'tool_calls':run['result']['tool_calls'],'answer':run['result']['answer']},ensure_ascii=True),flush=True)
        if '429' in run['result'].get('error','') and not args.continue_after_provider_errors:
            report['stopped_reason']='provider_429; no automatic retry or provider fallback'
            dump(folder/'report.json',report)
            break


if __name__=='__main__':
    main()
