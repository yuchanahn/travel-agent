"""Bounded production-web checks. Private evidence, unchanged fixed queries, clean test roots."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if not out.is_relative_to((ROOT/'data/private').resolve()):parser.error('Use private output')
    out.mkdir(parents=True,exist_ok=False)
    os.environ.setdefault('LLM_CONFIG_FILE',str(ROOT/'data/private/llm-config.json'))
    os.environ['MCP_CONFIG_FILE']=str(ROOT/'data/private/mcp-servers.json')
    from travel_agent.web_app import RunManager
    from travel_agent.llm_client import settings
    from travel_agent.llm_config import generation_options
    cfg=settings()
    if cfg['provider']!='ollama' or cfg['model']!='qwen3.5:4b-q4_K_M':parser.error('Use existing local Qwen')
    cases=json.loads((ROOT/'examples/live-harness-cases.json').read_text(encoding='utf-8'))
    reference=json.loads((ROOT/'docs/research/076-agent-results.json').read_text(encoding='utf-8'))
    assert all(c['query']==next(r['query'] for r in reference if r['case']==c['id']) for c in cases)
    report={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'started_at':datetime.now(timezone.utc).isoformat(),'provider':cfg['provider'],'model':cfg['model'],
            'options':generation_options(),'scope':'production web RunManager; fixed questions unchanged; no Claude rerun',
            'runs':[],'manual_review':'pending'}
    manager=RunManager(out/'sessions');roots=[]
    def save():(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    try:
        for case in cases:
            rid=manager.submit(case['query'],True);roots.append(rid)
            print('START '+case['id'],flush=True)
            deadline=time.monotonic()+410
            while manager.jobs[rid]['state'] in ('queued','running'):
                if time.monotonic()>deadline:raise TimeoutError('Case did not finish')
                time.sleep(.25)
            job=manager.snapshot(rid);plan=manager.plan(rid)
            evidence=out/'evidence'/case['id'];evidence.parent.mkdir(exist_ok=True)
            shutil.copytree(out/'sessions'/rid,evidence)
            report['runs'].append({'case':case['id'],'query':case['query'],'job':job,'plan':plan});save()
            print(json.dumps({'case':case['id'],'status':job.get('result',{}).get('status'),
                'model_calls':job.get('result',{}).get('model_calls'),'tool_calls':job.get('result',{}).get('tool_calls'),
                'plan_items':len(plan['items']),'plan_sync':job.get('result',{}).get('plan_sync')},ensure_ascii=False),flush=True)
    finally:
        manager.pool.shutdown(wait=True)
        report['cleanup']=[manager.delete_conversation(rid) for rid in roots]
        report['remaining_test_runs']=len(manager.executions());save()


if __name__=='__main__':main()
