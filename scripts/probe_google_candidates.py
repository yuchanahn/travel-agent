"""Bounded HTTP-only replay of request patterns found in public source.

These are diagnostic candidates, not production search providers.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlsplit

from travel_agent.google_http import PRIVATE, parse_page


def request_spec(case, query):
    if case == "lynx":
        return {"url": "https://www.google.com/search",
                "params": {"q": query, "num": "7", "hl": "en", "start": "0", "safe": "active"},
                "headers": {"User-Agent": "Lynx/2.8.9rel.1 libwww-FM/2.14 SSL-MM/1.4.1 OpenSSL/1.1.1g", "Accept": "*/*"},
                "cookies": {"CONSENT": "PENDING+987", "SOCS": "CAESHAgBEhIaAB"}}
    if case == "searxng-wml":
        return {"url": "https://www.google.com/wml/search",
                "params": {"q": query, "sca_esv": "1", "hl": "en", "lr": "", "cr": "", "ie": "utf8", "oe": "utf8"},
                "headers": {"User-Agent": "Nokia7610/2.0 (5.0509.0) SymbianOS/7.0s Series60/2.1 Profile/MIDP-2.0 Configuration/CLDC-1.0", "Accept": "*/*"},
                "cookies": {"CONSENT": "YES+"}, "impersonate": "chrome99_android"}
    raise ValueError("Unknown candidate")


def main():
    from curl_cffi.requests import Session
    from curl_cffi.requests.exceptions import RequestException
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=["lynx", "searxng-wml"])
    parser.add_argument("--query", default="Python official website")
    args = parser.parse_args()
    if not 0 < len(args.query.strip()) <= 500:
        parser.error("query must contain 1..500 characters")
    run_id = uuid4().hex
    folder = PRIVATE / "candidate-probes" / run_id
    folder.mkdir(parents=True)
    spec = request_spec(args.case, args.query.strip())
    report = {"run_id": run_id, "case": args.case, "query": args.query.strip(),
              "started_at": datetime.now(timezone.utc).isoformat(), "params": spec["params"],
              "user_agent": spec["headers"]["User-Agent"], "cookie_names": sorted(spec["cookies"]),
              "transport_profile": spec.get("impersonate"), "web_search_performed": False}
    try:
        with Session() as session:
            response = session.get(**spec, timeout=15, allow_redirects=False)
            (folder / "response.body").write_bytes(response.content)
            report.update(http_status=response.status_code, response_bytes=len(response.content), path=urlsplit(response.url).path)
            report["status"], report["hits"] = parse_page(response.content, response.url, response.status_code)
            if response.status_code in {301, 302, 303, 307, 308}:
                report["redirect_path"] = urlsplit(response.headers.get("location", "")).path
            report["web_search_performed"] = bool(report["hits"])
    except RequestException as exc:
        report.update(status="transport_error", error_type=type(exc).__name__)
    (folder / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["web_search_performed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
