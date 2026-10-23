"""Replay saved 079 final model inputs; never execute requested tools or contact search APIs."""
import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

from travel_agent.agent import SYSTEM
from travel_agent.llm_client import settings, chat
from travel_agent.llm_config import generation_options

ROOT=Path(__file__).resolve().parents[1]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to((ROOT/'data/private').resolve()):parser.error('Use a private evidence directory')
    os.environ.setdefault('LLM_CONFIG_FILE',str(ROOT/'data/private/llm-config.json'))
    config=settings()
    options=generation_options()
    if config['provider']!='ollama' or config['model']!='qwen3.5:4b-q4_K_M' or urlsplit(config['base_url']).hostname not in ('127.0.0.1','localhost','::1'):
        parser.error('Only the existing local Qwen is allowed')
    if options!={'num_ctx':65536,'num_predict':4096,'temperature':0}:parser.error('Keep the frozen generation settings')
    with urlopen(config['base_url']+'/api/tags',timeout=5) as response:installed=json.load(response)
    if not any(m.get('name')==config['model'] for m in installed.get('models',[])):parser.error('Model must already be installed')
    old_source=subprocess.check_output(['git','show','14bf358:src/travel_agent/agent.py'],cwd=ROOT).decode('utf-8')
    old=next(ast.literal_eval(n.value) for n in ast.parse(old_source).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SYSTEM' for t in n.targets))
    assert SYSTEM.startswith(old) and SYSTEM!=old
    cases=json.loads((ROOT/'examples/live-harness-cases.json').read_text(encoding='utf-8'))
    # Load and validate every fixture before starting any inference.
    fixtures=[]
    for case in cases:
        data=json.loads((ROOT/'data/private/fixed-eval-079'/case['id']/'model-inputs.json').read_text(encoding='utf-8'))[-1]
        assert data['messages'][0]['role']=='system' and data['messages'][0]['content'].startswith(old)
        assert data['messages'][1]['content']=='현재 요약:\n\n질문:\n'+case['query']
        fixtures.append((case,data))
    output.mkdir(parents=True,exist_ok=False)
    def save(name,value):
        p=output/name;tmp=p.with_suffix('.tmp')
        tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)
    save('protocol.json',{'scope':'saved final-input replay, not an agent rerun','cases':cases,
        'baseline_commit':'14bf358','model':config['model'],'options':options,'old_system':old,'new_system':SYSTEM,
        'external_calls':0,'tool_execution':False,'manual_review':'pending'})
    rows=[]
    for case,fixture in fixtures:
        for condition in ('before','after'):
            messages=deepcopy(fixture['messages'])
            if condition=='after':messages[0]['content']=SYSTEM+messages[0]['content'][len(old):]
            row={'case':case['id'],'query':case['query'],'condition':condition,'messages':messages,'tools':fixture['tools'],
                'started_at':datetime.now(timezone.utc).isoformat(),'status':'running'}
            rows.append(row);save('report.json',rows);start=time.perf_counter()
            try:
                reply=chat(messages,model=config['model'],base_url=config['base_url'],timeout=120,tools=fixture['tools'])
                calls=reply['message'].get('tool_calls') or []
                row.update(reply=reply,answer=reply['message']['content'],requested_tools=calls,
                    status='needs_tools' if calls else 'completed')
            except Exception as exc:row.update(status='error',error=str(exc),error_type=type(exc).__name__)
            row['elapsed_seconds']=round(time.perf_counter()-start,3);save('report.json',rows)
            print(json.dumps({k:row.get(k) for k in ('case','condition','status','answer','requested_tools','elapsed_seconds')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
