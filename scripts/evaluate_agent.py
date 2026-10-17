"""Small synthetic routing/recall experiment. Not an agent quality benchmark."""

import argparse
import json
import sys
from pathlib import Path

from travel_agent.agent import run_agent
from travel_agent.memory import MemoryStore, search
from travel_agent.memory_cli import recall_answer
from travel_agent.trace import read_trace


CASES = [
    {"id": "greeting", "query": "안녕!", "expect_tool": False},
    {"id": "summary", "query": "이번 여행은 몇 명이고 어떤 이동수단을 쓰기로 했지?", "expect_tool": False},
    {"id": "reason", "query": "강릉을 후보에서 제외한 이유가 뭐였지?", "expect_tool": True, "gold_event": "e02", "compare_2step": True},
    {"id": "latest_budget", "query": "현재 우리가 정한 총예산은 얼마야?", "expect_tool": True, "gold_event": "e05", "compare_2step": True},
    {"id": "initial_budget", "query": "처음 정한 여행 예산은 얼마였어?", "expect_tool": True, "gold_event": "e01"},
    {"id": "unknown", "query": "내가 지난번에 말한 여권번호가 뭐였지?", "expect_tool": True},
    {"id": "freshness", "query": "지난번 숙소 A는 지금도 8만 원에 예약할 수 있어?", "expect_tool": True, "gold_event": "e04", "compare_2step": True},
    {"id": "show", "query": "과거 이벤트 e02의 원문을 확인해서 강릉 제외 이유를 알려줘.", "expect_tool": True, "gold_event": "e02", "expect_show": True},
    {"id": "missing_index", "query": "지난번에 정한 여행 예산이 얼마였지?", "session": "no-index-fixture", "expect_tool": True, "expect_error": True},
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/private/memory.sqlite3")
    parser.add_argument("--case", choices=[case["id"] for case in CASES])
    parser.add_argument("--output", type=Path, default=Path("artifacts/agent-eval.json"))
    args = parser.parse_args()
    summary = Path("examples/compressed-summary.txt").read_text(encoding="utf-8")
    fixture = [json.loads(line) for line in Path("examples/memory-history.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    report = {"synthetic": True, "cases": [], "limits": "Nine hand-written scenarios. Route checks and event-ID retrieval checks are not semantic answer verification. 2-step/agent prompts and budgets differ; timings include cold/warm effects."}
    with MemoryStore(args.db) as store:
        if store.events("demo", "trip") != fixture:
            raise ValueError("Expected only the public synthetic fixture in demo/trip; import and index it first")
        if store.events("demo", "no-index-fixture"):
            raise ValueError("The missing-index fixture namespace must be empty")
        for case in CASES:
            if args.case and case["id"] != args.case:
                continue
            result = run_agent(store, "demo", case.get("session", "trip"), case["query"], summary=summary)
            trace = read_trace("data/private/traces", result["request_id"])
            returned_events = set()
            for record in trace:
                if record["kind"] != "tool_end":
                    continue
                data = record["result"]
                if record["name"] == "memory_show":
                    returned_events.add(data["event"]["event_id"])
                else:
                    for hit in data["hits"]:
                        returned_events.update(event["event_id"] for event in hit["events"])
            entry = {"case": case, "agent": result, "checks": {
                "route_matches_expectation": bool(result["tool_calls"]) == case["expect_tool"],
                "gold_event_returned": case.get("gold_event") in returned_events if case.get("gold_event") else None,
                "show_used": any(item["kind"] == "tool_start" and item["name"] == "memory_show" for item in trace),
                "tool_error_observed": any(item["kind"] == "tool_error" for item in trace)},
                "manual_answer_review": "Pending; event-ID/citation membership does not prove factual support."}
            if case.get("compare_2step"):
                hits = search(store, "demo", "trip", case["query"])["hits"]
                entry["two_step"] = recall_answer(case["query"], hits, summary)
            report["cases"].append(entry)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(entry, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
