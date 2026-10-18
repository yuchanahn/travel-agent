"""Evaluate the search tool alone, retaining raw data for repeatable reranking."""
import argparse
import json
from pathlib import Path

from travel_agent.web_pipeline import search_evidence

CASES = [
    {'id':'museum','query':'국립춘천박물관 관람시간 휴관일 교통',
     'reference_url':'https://chuncheon.museum.go.kr/kor/index.do'},
    {'id':'rainy','query':'강릉 비오는날 부모님 실내 여행 걷기 적은 곳',
     'reference_url':'https://gabolmap.com/magazine/gangneung-central-market-coffee-street-rainy-course-20260826'},
    {'id':'technical','query':'Python asyncio TaskGroup cancellation official documentation',
     'reference_url':'https://docs.python.org/3/library/asyncio-task.html'},
]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('data/private/search-pipeline/034-final'))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    summary=[]
    for case in CASES:
        result=search_evidence(case['query'],pages=3,read_pages=5,keep_dir=args.output)
        # Reference URL coverage is only a retrieval diagnostic, not a relevance label.
        reference=case['reference_url']
        entry={**case,'request_id':result['id'],
               'collected':result['collected'],'groups':result['groups'],
               'delivered':len(result['sources']),'page_excerpts':sum(s['content_kind']=='page_excerpt' for s in result['sources']),
               'stop_reason':result['stop_reason'],'elapsed_ms':result['elapsed_ms'],
               'digest_bytes':result['digest_bytes'],
               'reference_in_candidates':any(r['href'].rstrip('/')==reference.rstrip('/') for r in result['raw_rows']),
               'reference_delivered':any(s['url'].rstrip('/')==reference.rstrip('/') for s in result['sources']),
               'engine_top3':[r['href'] for r in result['raw_rows'][:3]],
               'delivered_urls':[s['url'] for s in result['sources']],
               'note':'Reference is one observed built-in search URL; absence does not prove irrelevance. No agent or answer evaluation.'}
        summary.append(entry)
        (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(entry,ensure_ascii=True),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
