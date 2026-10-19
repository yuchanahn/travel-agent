"""Live journey recorder. Mechanical checks are not factual quality judgments."""
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen


class WebClient:
    def __init__(self, base_url):
        self.base_url=base_url.rstrip('/')

    def __call__(self,path,method='GET',payload=None):
        request=Request(self.base_url+path,method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Content-Type':'application/json'})
        with urlopen(request,timeout=10) as response:return json.load(response)


def tool_calls(events):
    starts={e['span']:e for e in events if e['kind']=='tool_start'}
    calls=[]
    for event in events:
        if event['kind'] not in {'tool_end','tool_error'}:continue
        start=starts.get(event['span'],{})
        args=start.get('arguments',{})
        if isinstance(args,str):
            try:args=json.loads(args)
            except ValueError:pass
        calls.append({'span':event['span'],'name':event.get('name'),
            'tool_call_id':start.get('tool_call_id'),'arguments':args,
            'started_at':start.get('timestamp'),'finished_at':event.get('timestamp'),
            'result':event.get('result')})
    return calls


def mechanical_checks(turn,job,root):
    result=job.get('result') or {}
    calls=tool_calls(job.get('events',[]))
    searches=[c for c in calls if c['name'].endswith('_airbnb_search')]
    dates=turn.get('dates')
    mismatches=[]
    for call in searches:
        args=call['arguments']
        if not isinstance(args,dict) or (dates and (args.get('checkin'),args.get('checkout'))!=tuple(dates)):
            mismatches.append(call['span'])
    return {'completed':result.get('status')=='completed',
        'same_conversation':bool(job.get('conversation')) and job['conversation'][0]['id']==root,
        'answer_present':bool(result.get('answer') or result.get('partial_answer')),
        'lodging_search_without_dates':bool(searches) and not dates,
        'lodging_date_mismatch_spans':mismatches,
        'tool_errors':sum('error' in (c['result'] or {}) for c in calls),
        'manual_fact_review':'pending'}


def assessment(report):
    turns=report.get('turns',[])
    mechanical=bool(turns) and len(turns)==len(report['case']['turns']) and all(
        t['checks']['completed'] and t['checks']['same_conversation'] and t['checks']['answer_present']
        and not t['checks']['lodging_search_without_dates'] and not t['checks']['lodging_date_mismatch_spans']
        for t in turns) and bool(report.get('cleanup')) and not report['cleanup'].get('error')
    quality=report.get('manual_review',{}).get('verdict','pending')
    return {'mechanical_gate':mechanical,'quality_verdict':quality,
            'release_gate':mechanical and quality=='pass','cleanup':report.get('cleanup')}


def run_journey(api,case,output,*,data_dir=None,wait=time.sleep,timeout=210):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    report={'case':case,'turns':[],'manual_review':{'verdict':'pending'},'cleanup':None}
    root=parent=None
    def save():
        (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        for turn in case['turns']:
            created=api('/api/runs','POST',{'query':turn['query'],'enable_web':turn.get('enable_web',True),'parent_id':parent})
            parent=created['id'];root=root or parent
            deadline=time.monotonic()+timeout
            while True:
                job=api('/api/runs/'+parent)
                if job['state'] not in {'queued','running'}:break
                if time.monotonic()>=deadline:raise TimeoutError('Journey run is still active')
                wait(.5)
            entry={'turn':turn,'job':job,'calls':tool_calls(job.get('events',[])),
                   'checks':mechanical_checks(turn,job,root)}
            report['turns'].append(entry)
            if data_dir:
                # Capture only this freshly created test's private trace before deleting its session.
                source=Path(data_dir).resolve()/parent/'traces'
                if source.resolve().parent.parent!=Path(data_dir).resolve():raise ValueError('Unsafe test trace path')
                traces=[]
                for path in source.glob('*.jsonl'):
                    traces.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines())
                (output/(turn['id']+'-trace.json')).write_text(json.dumps(traces,ensure_ascii=False),encoding='utf-8')
            save()
            print(json.dumps({'turn':turn['id'],'query':turn['query'],
                'answer':(job.get('result') or {}).get('answer') or (job.get('result') or {}).get('partial_answer'),
                'checks':entry['checks']},ensure_ascii=True),flush=True)
            if not job.get('can_continue'):break
    except Exception as exc:
        report['execution_error']=type(exc).__name__+': '+str(exc)
        raise
    finally:
        if root:
            try:report['cleanup']=api('/api/conversations/'+root,'DELETE')
            except Exception as exc:report['cleanup']={'error':type(exc).__name__+': '+str(exc)}
        save()
    return report
