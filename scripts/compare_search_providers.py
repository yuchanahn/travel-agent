"""Compare provider configurations on the same public queries; not an agent quality score."""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

from travel_agent.web import WebSearchError, web_search


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/provider-comparison.json"))
    parser.add_argument("--agent-only", action="store_true", help="Compare two real Ollama runs instead of search-only cases")
    args = parser.parse_args()
    if args.agent_only:
        return compare_agents(args.output)
    cases = json.loads(Path("examples/web-search-evaluation.json").read_text(encoding="utf-8"))["cases"]
    report = {"recorded_at": datetime.now(timezone.utc).isoformat(), "top_k": 5, "max_bytes": 10000,
              "timeout_per_call": 15, "versions": {p: version(p) for p in ("lxml", "curl_cffi")},
              "limits": "One sequential pass, different search engines, no automatic fallback or LLM. Domain hits only for two known domains; other relevance needs review.",
              "runs": []}
    for case in cases:
        for provider, backend in [("http", "bing"), ("webserp", "google")]:
            started = time.perf_counter()
            try:
                result = web_search(case["query"], top_k=5, max_bytes=10000, timeout=15,
                                    provider=provider, backend=backend)
            except WebSearchError as exc:
                result = {"provider": provider, "backend_requested": backend, "error": str(exc),
                          "web_search_performed": False, "status": "provider_error", **exc.details}
            domains = [urlsplit(hit["url"]).hostname or "" for hit in result.get("hits", [])]
            expected = case.get("known_relevant_domain")
            entry = {"case": case, "provider": provider, "backend": backend,
                     "elapsed_seconds": round(time.perf_counter() - started, 3), "result": result,
                     "known_domain_in_top5": any(d == expected or d.endswith("."+expected) for d in domains) if expected else None}
            report["runs"].append(entry)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(entry, ensure_ascii=False), flush=True)


def compare_agents(output):
    from travel_agent.agent import run_agent
    from travel_agent.memory import MemoryStore
    from travel_agent.trace import read_trace

    query = ("춘천 삼악산 호수케이블카와 국립춘천박물관의 공식 홈페이지 주소를 각각 찾아줘. "
             "서로 독립적인 두 웹검색을 한 응답의 도구 요청 묶음으로 보내고, 각 검색은 top_k=1로 해줘. "
             "반환된 주소와 출처를 간결하게 알려줘. 본문을 읽었다고 말하지 마.")
    report = {"query": query, "runs": [], "limits": "One real model run per provider, no memory fixture. Cold/warm model and live search vary; not a latency or cost superiority benchmark."}
    with MemoryStore("data/private/provider-comparison.sqlite3") as store:
        for provider, backend in [("http", "bing"), ("webserp", "google")]:
            print(json.dumps({"starting_agent_provider": provider}, ensure_ascii=False), flush=True)
            with patch.dict(os.environ, {"WEB_SEARCH_PROVIDER": provider, "WEB_SEARCH_BACKEND": backend}):
                result = run_agent(store, "demo", "provider-comparison", query, max_steps=4, max_tool_calls=4)
            trace = read_trace("data/private/traces", result["request_id"])
            entry = {"provider": provider, "backend": backend, "result": result,
                     "tool_log": [r for r in trace if r["kind"] in {"tool_start", "tool_end", "tool_error"}]}
            report["runs"].append(entry)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"provider": provider, "result": result}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
