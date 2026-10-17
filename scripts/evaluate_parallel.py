"""Same public query with serial and parallel execution; live results may differ."""

import json
import argparse
import os
import sys
from pathlib import Path

from travel_agent.agent import run_agent
from travel_agent.memory import MemoryStore
from travel_agent.trace import read_trace


QUERY = ('춘천 삼악산 호수케이블카와 국립춘천박물관의 공식 홈페이지 주소를 각각 찾아줘. '
         '서로 독립적인 두 웹검색을 한 응답의 도구 요청 묶음으로 보내고, 각 검색은 top_k=1로 해줘. '
         '반환된 주소와 출처를 간결하게 알려줘. 본문을 읽었다고 말하지 마.')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', nargs='+', type=int, choices=range(1, 5), default=[1, 3])
    parser.add_argument('--backend', help='Provider override for this process only')
    parser.add_argument('--output', type=Path, default=Path('artifacts/parallel-eval.json'))
    args = parser.parse_args()
    if args.backend:
        os.environ['WEB_SEARCH_BACKEND'] = args.backend
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'query': QUERY, 'backend': os.environ.get('WEB_SEARCH_BACKEND', 'duckduckgo,bing'),
              'runs': [], 'limits': 'Small development experiment, different live results/cache state. Not a quality or speed benchmark.'}
    with MemoryStore('data/private/parallel-eval.sqlite3') as store:
        for workers in args.workers:
            result = run_agent(store, 'demo', 'parallel', QUERY, tool_workers=workers)
            records = read_trace('data/private/traces', result['request_id'])
            starts = {r['span']: r for r in records if r['kind'] == 'tool_start'}
            spans = [{ 'span': r['span'], 'name': r['name'], 'start': starts[r['span']]['elapsed_seconds'],
                       'end': r['elapsed_seconds'], 'outcome': r['kind']}
                     for r in records if r['kind'] in {'tool_end', 'tool_error'}]
            overlap = any(a['name'] == b['name'] == 'web_search' and a['start'] < b['end'] and b['start'] < a['end']
                          for i, a in enumerate(spans) for b in spans[i + 1:])
            entry = {'workers': workers, 'result': result, 'spans': spans, 'web_overlap_observed': overlap,
                     'batch_sizes': [r['count'] for r in records if r['kind'] == 'tool_batch_start']}
            report['runs'].append(entry)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(entry, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
