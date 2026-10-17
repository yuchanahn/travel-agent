"""Live search integration checks with one explicitly controlled failure case."""

import argparse
import json
import sys
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from travel_agent.agent import run_agent
from travel_agent.memory import MemoryStore
from travel_agent.trace import read_trace
from travel_agent.web import WebSearchError


OFFICIAL_QUERY = "춘천 삼악산 호수케이블카 공식 홈페이지를 웹에서 찾아 주소와 검색 요약에 보이는 이용 주의사항 하나를 알려줘. 페이지 본문이나 실시간 운영 여부를 확인했다고 말하지 마."
CASES = [
    {"id": "without_web", "query": OFFICIAL_QUERY, "enable_web": False},
    {"id": "official", "query": OFFICIAL_QUERY},
    {"id": "greeting", "query": "안녕!", "expect_no_tools": True},
    {"id": "memory", "query": "강릉을 후보에서 제외한 이유가 뭐였지?", "expect_memory": True},
    {"id": "combined", "query": "강릉을 제외했던 이유를 먼저 기억에서 찾아줘. 그리고 춘천 삼악산 호수케이블카 공식 홈페이지를 웹에서 찾아 주소를 알려줘.", "expect_memory": True},
    {"id": "provider_failure", "query": OFFICIAL_QUERY, "controlled_failure": True},
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[case["id"] for case in CASES])
    parser.add_argument("--output", type=Path, default=Path("artifacts/web-eval.json"))
    args = parser.parse_args()
    summary = Path("examples/compressed-summary.txt").read_text(encoding="utf-8")
    fixture = [json.loads(line) for line in Path("examples/memory-history.jsonl").read_text(encoding="utf-8").splitlines()]
    report = {"live_results_are_time_dependent": True, "cases": [],
              "limits": "Six hand-written development cases; one simulated provider error. Citation membership is not factual verification. No broad quality or cost claim."}
    with MemoryStore("data/private/memory.sqlite3") as store:
        if store.events("demo", "trip") != fixture:
            raise ValueError("Expected public synthetic demo/trip fixture; import/index examples first")
        for case in CASES:
            if args.case and case["id"] != args.case:
                continue
            failure = patch("travel_agent.web._provider_search", side_effect=WebSearchError("Controlled provider timeout for evaluation")) if case.get("controlled_failure") else nullcontext()
            with failure:
                result = run_agent(store, "demo", "trip", case["query"], summary=summary, enable_web=case.get("enable_web", True))
            trace = read_trace("data/private/traces", result["request_id"])
            calls = [record["name"] for record in trace if record["kind"] == "tool_start"]
            entry = {"case": case, "network_mode": "controlled_failure" if case.get("controlled_failure") else "live_allowed" if case.get("enable_web", True) else "disabled",
                     "result": result, "tool_sequence": calls,
                     "checks": {"completed": result["status"] == "completed",
                                "memory_used": any(name in {"memory_search", "memory_show"} for name in calls),
                                "web_attempted": result["web_search_attempted"],
                                "web_completed": result["web_search_performed"],
                                "tool_error_observed": any(record["kind"] == "tool_error" for record in trace)},
                     "manual_review": "Read the answer and recorded snippets; runtime completion alone is not quality success."}
            report["cases"].append(entry)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(entry, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
