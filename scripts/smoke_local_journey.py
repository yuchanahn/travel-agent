"""Three synthetic turns through the web RunManager, with MCP disabled and private test storage."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
QUERIES=[
    '공개 합성 기능 시험이다. 여행 인원은 성인 두 명이고 날짜는 미정이야. 검색하지 말고 조건만 확인해줘.',
    '날짜는 2026년 11월 14일 체크인, 15일 체크아웃으로 정했어. 이천에서 자가용으로 출발하고 숙박비는 두 사람 1박 합계 40만 원 이하야. 검색하지 말고 지금까지 조건만 정리해줘.',
    '숙박비 상한만 두 사람 1박 합계 30만 원으로 바꿀게. 나머지는 그대로야. 날짜, 인원, 출발지, 이동 수단, 최신 숙박비 상한을 간결히 정리해줘. 검색하거나 숙소를 추천하지 마.'
]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to((ROOT/'data/private').resolve()):parser.error('Use private test storage')
    os.environ['MCP_CONFIG_FILE']=str(ROOT/'examples/mcp-servers.example.json')
    os.environ.setdefault('LLM_CONFIG_FILE',str(ROOT/'data/private/llm-config.json'))
    from travel_agent.llm_client import settings
    from travel_agent.web_app import RunManager
    config=settings()
    if config['provider']!='ollama' or config['model']!='qwen3.5:4b-q4_K_M' or urlsplit(config['base_url']).hostname not in ('127.0.0.1','localhost','::1'):
        parser.error('Use existing local Qwen')
    output.mkdir(parents=True,exist_ok=False)
    manager=RunManager(output/'sessions');root=parent=None;report={'queries':QUERIES,'turns':[]}
    def save(): (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    try:
        for query in QUERIES:
            parent=manager.submit(query,False,parent);root=root or parent;deadline=time.monotonic()+400
            while True:
                job=manager.snapshot(parent)
                if job['state'] not in ('queued','running'):break
                if time.monotonic()>deadline:raise TimeoutError('Test did not finish')
                time.sleep(.2)
            trace=[]
            for path in (output/'sessions'/parent/'traces').glob('*.jsonl'):
                trace.extend(json.loads(s) for s in path.read_text(encoding='utf-8').splitlines())
            report['turns'].append({'query':query,'job':job,'trace':trace});save()
            print(json.dumps({'query':query,'answer':job.get('result',{}).get('answer'),
                'status':job.get('result',{}).get('status')},ensure_ascii=False),flush=True)
            if job.get('result',{}).get('status')!='completed':raise RuntimeError('Incomplete synthetic turn')
        report['machine_checks']={'conversation_turns':len(job['conversation']),
            'individual_executions':len(manager.executions()),'root_matches':job['conversation'][0]['id']==root,
            'parent_chain':all(t['job'].get('parent_id')==report['turns'][i-1]['job']['id'] for i,t in enumerate(report['turns']) if i),
            'manual_facts':'pending'}
    finally:
        manager.pool.shutdown(wait=True)
        if root:
            report['cleanup']=manager.delete_conversation(root)
            report['remaining_test_runs']=len(manager.executions())
        save()
        print(json.dumps({'checks':report.get('machine_checks'),'cleanup':report.get('cleanup'),
            'remaining_test_runs':report.get('remaining_test_runs')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
