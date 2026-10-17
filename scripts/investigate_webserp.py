"""Bounded Google protocol probes; preserve private bodies for offline analysis.

No account cookies are imported. Output must remain under ignored artifacts/.
The upstream clone is never modified. Alternate modes are explicit experiments.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from curl_cffi.requests import Session
from lxml import html
from webserp.engines.google import Google


def frame_summary(body):
    """Inspect observed hexadecimal byte-length frames without running scripts."""
    if not body.startswith(b")]}'\n"):
        raise ValueError("Not the observed framed response format")
    position, frames = 5, []
    while position < len(body):
        prefix = re.match(rb"([0-9a-fA-F]+);", body[position:])
        if not prefix:
            raise ValueError("Unknown frame prefix")
        size = int(prefix[1], 16)
        position += prefix.end()
        if position + size > len(body):
            raise ValueError("Truncated frame")
        payload = body[position:position+size]
        position += size
        entry = {"bytes": size, "kind": "control" if payload.startswith(b"[") else "end" if not payload else "markup"}
        if entry["kind"] == "markup":
            dom = html.fromstring(payload)
            entry.update(anchors=len(dom.xpath('descendant-or-self::a[@href]')),
                         headings=len(dom.xpath('descendant-or-self::h3')),
                         scripts=len(dom.xpath('descendant-or-self::script')))
        frames.append(entry)
    return frames


def request_spec(query, mode):
    spec = Google().build_request(query, 5)
    profile = "chrome133a"
    if mode in {"arc_html", "arc_pc"}:
        spec.params["async"] = "use_ac:true,_fmt:" + ("html" if mode == "arc_html" else "pc")
    if mode in {"standard", "wml"}:
        spec.params.pop("asearch", None)
        spec.params.pop("async", None)
    if mode == "wml":
        spec.url = "https://www.google.com/wml/search"
        spec.params = {"q": query, "hl": "en", "ie": "utf8", "oe": "utf8", "sca_esv": "1"}
        spec.headers = {"Accept": "*/*", "User-Agent": "Nokia6230/2.0 (05.50) Profile/MIDP-2.0 Configuration/CLDC-1.1"}
        spec.cookies = {"CONSENT": "YES+"}
        profile = "chrome99_android"
    return spec, profile


def probe(query, mode, output, index):
    spec, profile = request_spec(query, mode)
    started = time.perf_counter()
    row = {"query": query, "mode": mode, "endpoint": spec.url, "params": spec.params,
           "profile": profile, "cookie_names_sent": list(spec.cookies)}
    try:
        with Session() as session:
            r = session.request(spec.method, spec.url, params=spec.params, headers=spec.headers,
                                cookies=spec.cookies, impersonate=profile, timeout=15)
            (output/f"{index:02d}-{mode}.body").write_bytes(r.content)
            text = r.text
            dom = html.fromstring(text or "<html></html>")
            hits = Google().parse_response(text)
            final = urlsplit(str(r.url))
            row.update(http_status=r.status_code, response_bytes=len(r.content), final_path=final.path,
                       final_host=final.hostname, upstream_hits=[x.as_dict() for x in hits[:5]],
                       h3_count=len(dom.xpath('//h3')), anchor_count=len(dom.xpath('//a[@href]')),
                       wml_blocks=len(dom.xpath('//div[contains(@class,"zMzFAb")]')),
                       async_framed=text.lstrip().startswith(")]}'"),
                       js_required="/httpservice/retry/enablejs" in text,
                       received_cookie_names=sorted({c.name for c in session.cookies.jar}))
    except Exception as exc:
        row["exception_type"] = type(exc).__name__
    row["elapsed_seconds"] = round(time.perf_counter()-started, 3)
    return row


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modes", nargs="+", choices=["upstream", "arc_html", "arc_pc", "standard", "wml"],
                        default=["upstream", "arc_html", "arc_pc", "wml"])
    parser.add_argument("--query", action="append")
    parser.add_argument("--output", type=Path, default=Path("artifacts/webserp-protocol-probes"))
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(Path("artifacts").resolve()):
        parser.error("output must be under private artifacts/")
    output.mkdir(parents=True, exist_ok=True)
    report = {"recorded_at": datetime.now(timezone.utc).isoformat(), "runs": []}
    queries = args.query or ["국립춘천박물관 공식 홈페이지", "Python official website"]
    for query in queries:
        for mode in args.modes:
            row = probe(query, mode, output, len(report["runs"])+1)
            report["runs"].append(row)
            (output/"report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(row, ensure_ascii=False), flush=True)
            time.sleep(1)


if __name__ == "__main__":
    main()
