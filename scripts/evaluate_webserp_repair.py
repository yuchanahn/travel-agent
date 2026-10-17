"""Repeat verified HTML-engine searches, optionally followed by a real agent run."""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from travel_agent.web import WebSearchError, web_search


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", action="store_true")
    parser.add_argument("--agent-only", action="store_true")
    parser.add_argument("--backend", choices=["google", "duckduckgo,yahoo"], default="duckduckgo,yahoo")
    parser.add_argument("--output", type=Path, default=Path("artifacts/webserp-repair-evaluation.json"))
    args = parser.parse_args()
    cases = [("춘천 삼악산 호수케이블카 공식 홈페이지", "samaksancablecar.com"),
             ("국립춘천박물관 공식 홈페이지", "chuncheon.museum.go.kr"),
             ("Python official website", "python.org")]
    report = {"provider": "webserp", "backend": args.backend, "top_k": 5, "runs": [],
              "limits": "Three development queries, two passes on one machine; not broad relevance or availability evidence."}

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for repeat in (() if args.agent_only else (1, 2)):
        for query, domain in cases:
            started = time.perf_counter()
            try:
                result = web_search(query, provider="webserp", backend=args.backend,
                                    top_k=5, max_bytes=10000)
            except WebSearchError as exc:
                result = {"error": str(exc), "web_search_performed": False, **exc.details}
            domains = [(urlsplit(x["url"]).hostname or "") for x in result.get("hits", [])]
            row = {"repeat": repeat, "query": query, "expected_domain": domain,
                   "domain_found": any(x == domain or x.endswith("."+domain) for x in domains),
                   "elapsed_seconds": round(time.perf_counter()-started, 3), "result": result}
            report["runs"].append(row)
            save()
            print(json.dumps(row, ensure_ascii=False), flush=True)
            time.sleep(1)
    if args.agent or args.agent_only:
        from travel_agent.agent import run_agent
        from travel_agent.memory import MemoryStore
        from travel_agent.trace import read_trace

        query = ("춘천 삼악산 호수케이블카와 국립춘천박물관의 공식 홈페이지 주소를 각각 찾아줘. "
                 "서로 독립적인 두 웹검색을 한 응답의 도구 요청 묶음으로 보내고, 각 검색은 top_k=1로 해줘. "
                 "반환된 주소와 출처를 간결하게 알려줘. 본문을 읽었다고 말하지 마.")
        with MemoryStore("data/private/webserp-repair.sqlite3") as store, \
                patch.dict(os.environ, {"WEB_SEARCH_PROVIDER": "webserp", "WEB_SEARCH_BACKEND": args.backend}):
            result = run_agent(store, "demo", "repair", query, max_steps=4, max_tool_calls=4)
        records = read_trace("data/private/traces", result["request_id"])
        report["agent"] = {"query": query, "result": result,
                           "options": records[0]["options"],
                           "tool_log": [r for r in records if r["kind"] in {"tool_start", "tool_end", "tool_error"}]}
        save()
        print(json.dumps(report["agent"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
