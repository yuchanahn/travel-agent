"""Standalone Google browser experiment, independent of search libraries.

python -m travel_agent.google_browser search "Python official website"
python -m travel_agent.google_browser open
The dedicated profile persists on disk. No personal Chrome profile is imported.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit


PROFILE = Path(__file__).resolve().parents[2] / "data/private/google-browser"

# Associate a heading with its own link, never the first link in a result block.
# Snippet selectors are deliberately narrow; an absent snippet stays empty.
EXTRACT = """() => [...document.querySelectorAll('#search h3')].filter(h =>
    h.getClientRects().length).map(h => {
    const a = h.closest('a[href]');
    const block = h.closest('.MjjYud, .g');
    const snippet = block?.querySelector('.VwiC3b, [data-sncf]');
    return {title: h.innerText, href: a?.href || '', body: snippet?.innerText || ''};
})"""


def clean_hits(rows, top_k=5):
    hits, seen = [], set()
    for row in rows:
        try:
            raw = row.get("href", "")
            u = urlsplit(raw)
            if u.hostname in {"www.google.com", "google.com"} and u.path == "/url":
                raw = parse_qs(u.query).get("q", parse_qs(u.query).get("url", [""]))[0]
                u = urlsplit(raw)
            if (u.scheme not in {"http", "https"} or not u.hostname or u.username or u.password
                    or u.hostname == "google.com" or u.hostname.endswith(".google.com")
                    or len(raw) > 2048 or any(c.isspace() or ord(c) < 32 for c in raw)):
                continue
            url = urlunsplit((u.scheme, u.netloc, u.path or "/", u.query, ""))
            title = " ".join(row.get("title", "").split())
            if not title or url in seen:
                continue
            seen.add(url)
            hits.append({"title": title[:200], "url": url, "snippet": " ".join(row.get("body", "").split())[:600]})
            if len(hits) >= top_k:
                break
        except (ValueError, TypeError):
            continue
    return hits


def inspect_page(page):
    """An access page is a failure even if it happens to contain headings."""
    u = urlsplit(page.url)
    if u.path.startswith("/sorry") or page.locator('#captcha-form, iframe[src*="recaptcha"]').count():
        return "access_interstitial", []
    if u.hostname == "consent.google.com":
        return "consent_required", []
    hits = clean_hits(page.evaluate(EXTRACT))
    return ("ok" if hits else "no_search_markup"), hits


def run(action, query=None, *, profile=PROFILE, timeout=15):
    from playwright.sync_api import Error, TimeoutError as BrowserTimeout, sync_playwright

    if action not in {"open", "search"}:
        raise ValueError("action must be open or search")
    if action == "search" and (not isinstance(query, str) or not 0 < len(query.strip()) <= 500):
        raise ValueError("query must contain 1..500 characters")
    if not 1 <= timeout <= 30:
        raise ValueError("timeout must be 1..30 seconds per browser operation")
    profile = Path(profile).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    report = {"query": query, "provider": "google-browser", "web_search_performed": False,
              "started_at": datetime.now(timezone.utc).isoformat(), "navigation": [], "hits": []}
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(str(profile), channel="chrome", headless=False,
                                                          timeout=timeout * 1000)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(timeout * 1000)

                def observed(response):
                    if response.request.is_navigation_request() and response.request.frame == page.main_frame:
                        u = urlsplit(response.url)
                        report["navigation"].append({"host": u.hostname, "path": u.path,
                            "http_status": response.status, "elapsed_ms": round((time.perf_counter()-started)*1000)})

                page.on("response", observed)
                page.goto("https://www.google.com/?hl=en", wait_until="domcontentloaded")
                if action == "open":
                    print("전용 Google 프로필입니다. 필요한 확인을 마친 뒤 이 터미널에서 Enter를 누르세요.", file=sys.stderr)
                    input()
                    report["status"] = "profile_saved"
                else:
                    box = page.locator('textarea[name="q"], input[name="q"]').first
                    box.fill(query.strip())
                    box.press("Enter")
                    try:
                        page.wait_for_function("""() => location.pathname.startsWith('/sorry') ||
                            location.hostname === 'consent.google.com' ||
                            [...document.querySelectorAll('#search h3')].some(h => h.getClientRects().length)""")
                    except BrowserTimeout:
                        pass
                    report["status"], report["hits"] = inspect_page(page)
                    report["web_search_performed"] = report["status"] == "ok"
                u = urlsplit(page.url)
                report.update(final_host=u.hostname, final_path=u.path)
            finally:
                context.close()  # Chrome writes this dedicated profile back to disk.
        except (Error, EOFError) as exc:
            # Playwright exception strings may contain full URLs or local paths.
            report.update(status="browser_error", error_type=type(exc).__name__)
    report["elapsed_ms"] = round((time.perf_counter()-started)*1000)
    return report


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["open", "search"])
    parser.add_argument("query", nargs="?")
    parser.add_argument("--timeout", type=float, default=15, help="Per-operation seconds, not total deadline")
    args = parser.parse_args()
    try:
        report = run(args.action, args.query, timeout=args.timeout)
    except (ImportError, ValueError, OSError) as exc:
        report = {"status": "setup_error", "error_type": type(exc).__name__, "web_search_performed": False}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"ok", "profile_saved"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
