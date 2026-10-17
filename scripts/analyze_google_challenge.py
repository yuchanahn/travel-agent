"""Offline Google challenge analysis using a pinned, separately cloned toolkit.

Requires Node 24+, toolkit part-2 dependencies, and an existing private capture.
No Google request is made. Analysis output is not proof of a valid Google session.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from travel_agent.google_http import PRIVATE

ROOT = Path(__file__).resolve().parents[1]
TOOLKIT_COMMIT = "c617f4406ce1c373d5e071ae0f969de101ec4505"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--node", required=True, type=Path)
    parser.add_argument("--toolkit", type=Path, default=ROOT / "artifacts/vendor/google-search-guard-vm-reversing")
    args = parser.parse_args()
    toolkit, capture = args.toolkit.resolve(), args.capture.resolve()
    commit = subprocess.check_output(["git", "-C", str(toolkit), "rev-parse", "HEAD"], text=True).strip()
    if commit != TOOLKIT_COMMIT:
        parser.error("Toolkit checkout differs from the reviewed commit")
    version = subprocess.check_output([str(args.node), "--version"], text=True).strip()
    if int(version.lstrip("v").split(".")[0]) < 24:
        parser.error("This adapter requires Node 24+")
    if not capture.is_file() or capture.stat().st_size > 1_000_000:
        parser.error("Expected a capture file no larger than 1MB")
    folder = PRIVATE / "offline-analysis" / uuid4().hex
    folder.mkdir(parents=True)
    helper = ROOT / "scripts/analyze_google_challenge.cjs"
    command = [str(args.node), "--permission", "--allow-fs-read=" + str(toolkit),
               "--allow-fs-read=" + str(capture), "--allow-fs-read=" + str(helper),
               "--allow-fs-write=" + str(folder), str(helper), str(toolkit), str(capture), str(folder / "details.json")]
    environment = dict(os.environ)
    environment["NODE_PATH"] = str(toolkit / "part-2-reverse-vm/node_modules")
    try:
        result = subprocess.run(command, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=45)
        (folder / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        summary = json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        summary = {"status": "analysis_timeout", "server_acceptance_tested": False}
    except (OSError, json.JSONDecodeError) as exc:
        summary = {"status": "analysis_error", "error_type": type(exc).__name__, "server_acceptance_tested": False}
    summary["toolkit_commit"] = commit
    (folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("record_instrumentation_equal") and summary.get("access_instrumentation_equal") else 1


if __name__ == "__main__":
    raise SystemExit(main())
