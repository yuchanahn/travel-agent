"""Live-model greeting, public memory, no-web and simulated-search-outage controls."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch

from travel_agent.agent import run_agent
from travel_agent.memory import MemoryStore, digest
from travel_agent.trace import read_trace
from travel_agent.web import WebSearchError
from evaluate_brave_agent import summarize_trace


def seed_public_index(destination):
    """Copy only a verified public fixture's index, never other users' history."""
    fixture=[json.loads(line) for line in Path('examples/memory-history.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    path=Path('data/private/memory.sqlite3').resolve()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as source:
        events=[json.loads(row[0]) for row in source.execute('SELECT payload FROM events WHERE user_id=? AND session_id=? ORDER BY timestamp,event_id',('demo','trip'))]
        if events!=fixture:
            raise ValueError('Source scope must match the public fixture exactly')
        index=source.execute('SELECT snapshot,config FROM indexes WHERE user_id=? AND session_id=?',('demo','trip')).fetchone()
        if not index or index[0]!=digest(fixture):
            raise ValueError('A current public fixture index is required; no automatic download')
        chunks=source.execute('SELECT chunk_id,payload,vector,dimensions FROM chunks WHERE user_id=? AND session_id=?',('demo','trip')).fetchall()
    destination.add('demo','trip',fixture)
    with destination.db:
        destination.db.execute('INSERT INTO indexes VALUES (?,?,?,?)',('demo','trip',*index))
        destination.db.executemany('INSERT INTO chunks VALUES (?,?,?,?,?,?)',[('demo','trip',*row) for row in chunks])


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('data/private/agent-brave-evaluation/controls'))
    output=parser.parse_args().output
    output.mkdir(parents=True,exist_ok=True)
    path=output/'report.json'
    if path.exists():
        raise FileExistsError('Controls report already exists; preserve it and choose a new --output')
    cases=[('greeting','안녕!',True,False,'empty'),
           ('memory','현재 우리가 정한 총예산은 얼마고 강릉을 후보에서 제외한 이유는 뭐였지?',True,False,'trip'),
           ('outage','국립춘천박물관 관람시간과 휴관일을 찾아서 알려줘.',True,True,'empty'),
           ('no_web','국립춘천박물관의 오늘 운영시간과 입장료를 확인해줘.',False,False,'empty')]
    report={'cases':[],'memory_mode':'bm25','fixture':'public examples/memory-history.jsonl',
            'outage_control':'Only web_search is simulated as HTTP429; model and loop are real'}
    with MemoryStore(output/'memory.sqlite3') as store:
        seed_public_index(store)
        for name,query,enable_web,outage,session in cases:
            print('\n질문: '+query,flush=True)
            kwargs=dict(mode='bm25',enable_web=enable_web,trace_dir=output/'traces',timeout=180)
            if outage:
                with patch('travel_agent.agent.web_search',side_effect=WebSearchError('Simulated search service HTTP429',details={'reason':'http_error','http_status':429,'simulated':True})):
                    result=run_agent(store,'demo',session,query,**kwargs)
            else:
                result=run_agent(store,'demo',session,query,**kwargs)
            trace=read_trace(output/'traces',result['request_id'])
            entry={'case':name,'query':query,'enable_web':enable_web,'simulated_outage':outage,
                   'result':result,'calls':summarize_trace(trace),'manual_review':'pending'}
            report['cases'].append(entry)
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print('상태: '+result['status']+'\n답변:\n'+(result.get('answer') or result.get('partial_answer') or '[최종 답변 없음]'),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
