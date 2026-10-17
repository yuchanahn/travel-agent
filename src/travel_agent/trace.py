"""Private, append-only execution records; never model chain-of-thought."""

import json
import re
import time
import uuid
from threading import Lock
from datetime import datetime, timezone
from pathlib import Path


class Trace:
    def __init__(self, directory):
        self.request_id = uuid.uuid4().hex
        self.path = Path(directory) / f"{self.request_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=False)
        self.started = time.perf_counter()
        self.sequence = 0
        self.lock = Lock()

    def emit(self, kind, **fields):
        with self.lock:
            self._emit(kind, **fields)

    def _emit(self, kind, **fields):
        self.sequence += 1
        record = {"request_id": self.request_id, "sequence": self.sequence,
                  "timestamp": datetime.now(timezone.utc).isoformat(),
                  "elapsed_seconds": round(time.perf_counter() - self.started, 6),
                  "kind": kind, **fields}
        with self.path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_trace(directory, request_id):
    if not re.fullmatch(r"[a-f0-9]{32}", request_id):
        raise ValueError("request_id must be the 32-character ID returned by memory agent")
    path = Path(directory) / f"{request_id}.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(record.get("request_id") != request_id for record in records):
        raise ValueError("Trace request_id mismatch")
    return records


def add_parser(subparsers):
    parser = subparsers.add_parser("trace", help="Inspect private execution records")
    actions = parser.add_subparsers(dest="trace_action", required=True)
    show = actions.add_parser("show")
    show.add_argument("request_id")
    show.add_argument("--dir", default="data/private/traces")


def run(args):
    records = read_trace(args.dir, args.request_id)
    print(json.dumps({"request_id": args.request_id, "events": records}, ensure_ascii=False, indent=2))
    return 0
