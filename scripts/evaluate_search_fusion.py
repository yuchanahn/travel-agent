"""Run public queries through the configured Bing search tool, without an LLM."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from travel_agent.web import WebSearchError, web_search


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', action='append')
    parser.add_argument('--output', type=Path, default=Path('data/private/search-fusion')/(uuid4().hex+'.json'))
    args = parser.parse_args()
    records = []
    for query in args.query or ['Python official website','국립춘천박물관 공식 홈페이지','춘천 삼악산 호수케이블카 공식 홈페이지']:
        record = {'id':uuid4().hex,'tool':'web_search','arguments':{'query':query,'top_k':3},
                  'backend':'bing','started_at':datetime.now(timezone.utc).isoformat()}
        try:
            record['result'] = web_search(query, top_k=3, timeout=10, provider='http', backend='bing')
        except WebSearchError as exc:
            record['result'] = {'error':str(exc),'web_search_performed':False,**exc.details}
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        records.append(record)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(record,ensure_ascii=True),flush=True)
    return 0 if all(r['result'].get('search_complete') and r['result'].get('hits') for r in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())
