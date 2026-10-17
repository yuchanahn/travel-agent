"""Small synthetic recall experiment; not a production benchmark.

Run from repo root after importing/indexing examples/memory-history.jsonl.
No private chat data is collected; outputs go to gitignored artifacts/.
"""

import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

from travel_agent.memory import MemoryStore, search
from travel_agent.memory_cli import recall_answer


CASES = [
    ("강릉을 후보에서 제외한 이유가 뭐였지?", "e02"),
    ("현재 우리가 정한 총예산은 얼마야?", "e05"),
    ("처음 정한 여행 예산은 얼마였어?", "e01"),
    ("테스트용 숙소 A의 당시 표시 가격과 출처는?", "e04"),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    report = {"synthetic": True, "labeling": "Four hand-written queries, one gold event per query; overlapping chunks count once per query.", "retrieval": []}
    summary = Path("examples/compressed-summary.txt").read_text(encoding="utf-8")
    with MemoryStore("data/private/memory.sqlite3") as store:
        for mode in ("bm25", "dense", "hybrid"):
            for query, gold in CASES:
                started = time.perf_counter()
                result = search(store, "demo", "trip", query, mode=mode, top_k=3)
                ranks = [rank for rank, hit in enumerate(result["hits"], 1) if gold in {event["event_id"] for event in hit["events"]}]
                report["retrieval"].append({"mode": mode, "query": query, "gold_event": gold,
                    "found_at_3": bool(ranks), "reciprocal_rank_at_3": 1 / min(ranks) if ranks else 0,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "hit_events": [[event["event_id"] for event in hit["events"]] for hit in result["hits"]]})
        query = CASES[0][0]
        base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        # Equal source reliability rules; baseline receives only the lossy summary, no original events.
        body = {"model": os.environ.get("OLLAMA_MODEL", "qwen3.5:4b-q4_K_M"), "stream": False, "think": False,
                "messages": [{"role": "system", "content": "한국어로 답하세요. 제공된 과거 기록만 근거로 사용하고, 이유를 알 수 없으면 모른다고 하세요. 웹검색을 했다고 말하지 마세요."},
                             {"role": "user", "content": f"현재 요약:\n{summary}\n질문: {query}"}],
                "options": {"num_ctx": 4096, "num_predict": 256, "temperature": 0}}
        request = Request(base + "/api/chat", data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=180) as response:
            baseline = json.load(response)
        report["summary_only"] = baseline["message"]["content"]
        report["comparison_limit"] = "Exploratory single-case comparison. Prompts differ in evidence packaging; no broad quality claim. Cold/warm timings are mixed in retrieval loop."
        hits = search(store, "demo", "trip", query)["hits"]
        report["summary_plus_retrieval"] = recall_answer(query, hits, summary)
        budget_query = CASES[1][0]
        report["latest_budget"] = recall_answer(budget_query, search(store, "demo", "trip", budget_query)["hits"], summary)
        price_query = "숙소 A는 지금도 8만 원에 예약할 수 있어?"
        report["freshness"] = recall_answer(price_query, search(store, "demo", "trip", price_query)["hits"], summary)
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/memory-eval.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
