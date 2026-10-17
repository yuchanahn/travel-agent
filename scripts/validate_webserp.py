"""Run the cloned webserp Google CLI with response diagnostics, without an LLM.

Run in a separate venv with the reviewed clone installed. No cookie values,
headers, raw HTML or account data are written. Hooks are process-local.
"""

import argparse
import io
import json
import os
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit


def document_signals(text):
    """Record evidence, not a guarantee of a page's intent."""
    from lxml import html

    tree = html.fromstring(text or "<html></html>")
    lower = text.lower()
    return {
        "async_framed": text.lstrip().startswith(")]}'"),
        "captcha": bool(tree.xpath('//form[contains(@action,"/sorry/")] | '
                                   '//iframe[contains(@src,"recaptcha")] | //*[@id="captcha-form"]')),
        "unusual_traffic": "unusual traffic from your computer network" in lower,
        "enable_js": "/httpservice/retry/enablejs" in lower,
        "consent": "before you continue to google" in lower,
        "explicit_no_results": "did not match any documents" in lower,
        "result_containers": len(tree.xpath('//div[contains(@class,"MjjYud")]')),
        "h3_count": len(tree.xpath('//h3')),
    }


def classify_result(result, events):
    signals = [event.get("signals", {}) for event in events]
    if result["unresponsive_engines"]:
        return "provider_error"
    if any(s.get(k) for s in signals for k in ("captcha", "unusual_traffic", "consent")):
        return "access_interstitial"
    if result["results"]:
        return "results_returned_requires_review"
    if any(s.get("enable_js") for s in signals):
        return "access_interstitial"
    if any(s.get("async_framed") for s in signals):
        return "unparsed_async_response"
    if any(s.get("explicit_no_results") for s in signals):
        return "explicit_no_results"
    return "empty_unclassified"


def run_case(query, *, top_k=5, timeout=15, language=None, request_mode="upstream"):
    from curl_cffi.requests import AsyncSession
    from webserp.cli import main as upstream_main
    from webserp.engines.google import Google

    events = []
    request = AsyncSession.request
    build = Google.build_request

    def build_request(engine, *args, **kwargs):
        spec = build(engine, *args, **kwargs)
        if request_mode == "standard":
            spec.params.pop("asearch", None)
            spec.params.pop("async", None)
        if language:
            spec.params["hl"] = language
            spec.headers["Accept-Language"] = language
        return spec

    async def observed_request(session, method, url, **kwargs):
        started = time.perf_counter()
        parsed = urlsplit(url)
        event = {"method": method, "endpoint": f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
                 "params": kwargs.get("params"), "impersonate": kwargs.get("impersonate")}
        events.append(event)
        try:
            response = await request(session, method, url, **kwargs)
            final = urlsplit(str(response.url))
            event.update(http_status=response.status_code, response_bytes=len(response.content),
                         final_host=final.hostname, final_path=final.path,
                         signals=document_signals(response.text))
            return response
        except Exception as exc:
            event["exception_type"] = type(exc).__name__
            raise
        finally:
            event["elapsed_seconds"] = round(time.perf_counter() - started, 3)

    stdout, stderr = io.StringIO(), io.StringIO()
    argv = [query, "--engines", "google", "--max-results", str(top_k),
            "--timeout", str(timeout), "--verbose"]
    started = time.perf_counter()
    with patch.object(AsyncSession, "request", observed_request), \
            patch.object(Google, "build_request", build_request), \
            redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = upstream_main(argv)
    result = json.loads(stdout.getvalue())
    status = classify_result(result, events)
    return {"query": query, "language_override": language, "request_mode": request_mode, "argv": argv,
            "upstream_exit_code": exit_code, "status": status,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "http": events, "upstream_stdout": stdout.getvalue(), "upstream_stderr": stderr.getvalue()}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--language", choices=["ko", "en"], help="Controlled override; default is unchanged upstream")
    parser.add_argument("--request-mode", choices=["upstream", "standard"], default="upstream",
                        help="Diagnostic-only override: standard removes arc/async parameters")
    parser.add_argument("--output", type=Path, default=Path("artifacts/webserp-validation.json"))
    args = parser.parse_args()
    if not 0 < len(args.query.strip()) <= 500:
        parser.error("query must contain 1..500 characters")
    report = {"recorded_at": datetime.now(timezone.utc).isoformat(),
              "versions": {p: version(p) for p in ("webserp", "curl_cffi", "lxml", "certifi")},
              "proxy_environment_keys": [k for k in os.environ if k.upper() in
                                         {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}],
              "run": run_case(args.query, language=args.language, request_mode=args.request_mode)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["run"]["status"] == "results_returned_requires_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
