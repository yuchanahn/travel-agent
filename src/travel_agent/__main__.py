"""Travel agent diagnostics and scoped conversation memory RAG."""

import argparse
import json
import os
import sys
import sqlite3
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Read-only Ollama connectivity check")
    from .memory_cli import add_parser, run
    add_parser(commands)
    args = parser.parse_args()
    if args.command == "memory":
        try:
            return run(args)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, sqlite3.Error, ImportError) as exc:
            print(f"Memory operation failed: {exc}", file=sys.stderr)
            return 1
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b-q4_K_M")
    try:
        def read(endpoint: str) -> dict:
            with urlopen(f"{base_url}/api/{endpoint}", timeout=5) as response:
                return json.load(response)

        version = read("version")
        installed = read("tags").get("models", [])
        loaded = read("ps").get("models", [])
        report = {
            "server_version": version.get("version"),
            "configured_model": model,
            "model_installed": any(item.get("name") == model for item in installed),
            "installed_models": [item.get("name") for item in installed],
            "loaded_models": [item.get("name") for item in loaded],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["model_installed"] else 1
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"Ollama status check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
