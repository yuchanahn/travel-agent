"""Google HTML over HTTP, with a persistent cookie jar and no browser process."""

import argparse
import json
import os
import sys
import tempfile
import time
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie, CookieError
from datetime import datetime, timezone
from http.cookiejar import LWPCookieJar, CookieJar
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit
from uuid import uuid4
from urllib.request import Request
from .google_identity import PROFILE, HTTP_HEADERS


PRIVATE = Path(__file__).resolve().parents[2] / "data/private/google-http"
ORIGIN = "https://www.google.com"


def document_cookies(jar, url):
    """Only unexpired, URL-matching, non-HttpOnly cookies are visible to script."""
    visible = CookieJar()
    for cookie in jar:
        if not any(key.lower().replace("_", "").replace("-", "") == "httponly"
                   and (value is None or str(value).lower() not in {"false", "0", ""})
                   for key, value in cookie._rest.items()):
            visible.set_cookie(cookie)
    request = Request(url)
    visible.add_cookie_header(request)
    parsed = SimpleCookie(request.get_header("Cookie", ""))
    return {key: morsel.value for key, morsel in parsed.items()}


def load_cookies(path):
    jar = LWPCookieJar(str(path))
    if Path(path).exists():
        jar.load(ignore_discard=True, ignore_expires=False)
    return jar


def save_cookies(jar, path):
    """Atomic replacement keeps an interrupted write from corrupting the jar."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix="cookies-", suffix=".tmp")
    os.close(descriptor)
    try:
        saved = LWPCookieJar()
        for cookie in jar:
            saved.set_cookie(cookie)
        saved.save(temporary, ignore_discard=True, ignore_expires=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def result_url(raw):
    absolute = urljoin(ORIGIN, raw)
    u = urlsplit(absolute)
    if u.hostname in {"google.com", "www.google.com"} and u.path == "/url":
        params = parse_qs(u.query)
        absolute = params.get("q", params.get("url", [""]))[0]
        u = urlsplit(absolute)
    if (u.scheme not in {"https", "http"} or not u.hostname or u.username or u.password
            or u.hostname == "google.com" or u.hostname.endswith(".google.com")
            or len(absolute) > 2048 or any(c.isspace() or ord(c) < 32 for c in absolute)):
        return None
    return urlunsplit((u.scheme, u.netloc, u.path or "/", u.query, ""))


def allowed_redirect(url, hosts):
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and u.hostname in hosts and u.port in {None, 443}
                and not u.username and not u.password and len(url) <= 20_000
                and not any(c.isspace() or ord(c) < 32 for c in url))
    except ValueError:
        return False


def sanitized_wire_headers(data):
    """Read libcurl's outgoing header block without retaining cookies or query tokens."""
    lines = data.decode("utf-8", errors="replace").splitlines()
    if not lines or not lines[0].startswith("GET "):
        return None
    result = {"cookie_names": [], "sg_ss_lengths": []}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        name, value = name.lower(), value.strip()
        if name == "cookie":
            for part in value.split(";"):
                key, _, secret = part.strip().partition("=")
                result["cookie_names"].append(key)
                if key == "SG_SS":
                    result["sg_ss_lengths"].append(len(secret))
        elif name in {"user-agent", "sec-ch-ua-platform", "sec-fetch-site"}:
            result[name] = value
        elif name == "referer":
            result["referer_path"] = urlsplit(value).path
    return result


def parse_page(body, url, status_code, top_k=5):
    from lxml import html
    u = urlsplit(url)
    text = body.decode("utf-8", errors="replace")
    lower = text.lower()
    if u.path.startswith("/sorry") or u.hostname == "sorry.google.com":
        return "access_interstitial", []
    if u.hostname == "consent.google.com":
        return "consent_required", []
    if status_code != 200:
        return "http_error", []
    if body.startswith(b")]}'\n"):
        from .google_protocol import decode_prog
        try:
            body, _ = decode_prog(body)
        except ValueError:
            return "protocol_error", []
    dom = html.fromstring(body or b"<html></html>")
    if dom.xpath('//*[@id="captcha-form"] | //iframe[contains(@src,"recaptcha")]'):
        return "access_interstitial", []
    rows, seen = [], set()
    # A title and URL must belong to the same anchor, not merely the same block.
    for heading in dom.xpath('//h3'):
        anchors = heading.xpath('ancestor::a[@href][1]')
        if not anchors:
            continue
        try:
            target = result_url(anchors[0].get("href"))
        except ValueError:
            continue
        title = " ".join(heading.text_content().split())
        if not target or not title or target in seen:
            continue
        seen.add(target)
        containers = heading.xpath('ancestor::*[contains(concat(" ",normalize-space(@class)," ")," MjjYud ") '
                                   'or contains(concat(" ",normalize-space(@class)," ")," g ")][1]')
        snippets = containers[0].xpath('.//*[@data-sncf] | .//*[contains(concat(" ",normalize-space(@class)," ")," VwiC3b ")]') if containers else []
        snippet = " ".join(snippets[0].text_content().split()) if snippets else ""
        rows.append({"title": title[:200], "url": target, "snippet": snippet[:600]})
        if len(rows) >= top_k:
            break
    if rows:
        return "ok", rows
    visible_text = " ".join(dom.xpath('//body//text()[not(ancestor::script) and not(ancestor::style)]')).lower()
    if "your browser isn't supported any more" in visible_text:
        return "unsupported_client", []
    if "/httpservice/retry/enablejs" in lower:
        return "javascript_required", []
    return "no_search_markup", []


def search(query, *, cookie_file=None, timeout=15, mode="standard", capture=False, javascript=False, wire=False):
    from curl_cffi.requests import Session
    from curl_cffi.requests.exceptions import RequestException

    if not isinstance(query, str) or not 0 < len(query.strip()) <= 500:
        raise ValueError("query must contain 1..500 characters")
    if not 1 <= timeout <= 30 or mode not in {"standard", "basic"}:
        raise ValueError("timeout must be 1..30 seconds; mode must be standard or basic")
    cookie_file = Path(cookie_file) if cookie_file else PRIVATE / "cookies.txt"
    jar = load_cookies(cookie_file)
    started = time.perf_counter()
    run_id = uuid4().hex
    report = {"run_id": run_id, "provider": "google-http", "query": query.strip(), "mode": mode,
              "started_at": datetime.now(timezone.utc).isoformat(), "transport_profile": PROFILE,
              "cookies_loaded": len(jar), "requests": [], "hits": [], "web_search_performed": False}
    options = {}
    if wire:
        from curl_cffi import CurlOpt
        report["wire_requests"] = []

        def observe(kind, data):
            if kind == 2:  # libcurl HEADER_OUT
                observed = sanitized_wire_headers(data)
                if observed is not None:
                    observed["id"] = f"{run_id}:{len(report['wire_requests'])+1}"
                    report["wire_requests"].append(observed)

        options["curl_options"] = {CurlOpt.VERBOSE: 1, CurlOpt.DEBUGFUNCTION: observe}
    with Session(cookies=jar, impersonate=PROFILE, headers=HTTP_HEADERS, **options) as session:
        def fetch(url, params=None, source=None):
            for hop in range(4):
                headers = {"Referer": source, "Sec-Fetch-Site": "same-origin"} if source and urlsplit(source).netloc == urlsplit(url).netloc else {}
                r = session.get(url, params=params, headers=headers, timeout=timeout, allow_redirects=False)
                u = urlsplit(r.url)
                event = {"id": f"{run_id}:{len(report['requests'])+1}", "method": "GET",
                         "host": u.hostname, "path": u.path, "http_status": r.status_code,
                         "response_bytes": len(r.content), "elapsed_ms": round((time.perf_counter()-started)*1000)}
                report["requests"].append(event)
                if headers:
                    event["request_context"] = {"referer_path": urlsplit(source).path, "fetch_site": "same-origin"}
                if capture:
                    folder = PRIVATE / "responses" / run_id
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f"{len(report['requests']):02}.body").write_bytes(r.content)
                if r.status_code not in {301, 302, 303, 307, 308}:
                    return r
                target = urljoin(r.url, r.headers.get("location", ""))
                # Never forward the session to another domain or to HTTP.
                if not allowed_redirect(target, {"www.google.com", "consent.google.com", "sorry.google.com"}):
                    report["status"] = "unsupported_redirect"
                    return None
                if hop == 3:
                    report["status"] = "redirect_limit"
                    return None
                url, params = target, None
            return None

        try:
            home = fetch(ORIGIN + "/", {"hl": "en"})
            if home is not None:
                home_status, _ = parse_page(home.content, home.url, home.status_code)
                if home_status in {"access_interstitial", "consent_required", "http_error"}:
                    report["status"] = home_status
                else:
                    params = {"q": query.strip(), "num": "5", "hl": "en"}
                    if mode == "basic":
                        params["gbv"] = "1"
                    report["search_params"] = params
                    response = fetch(ORIGIN + "/search", params, source=home.url)
                    if response is not None:
                        report["status"], report["hits"] = parse_page(response.content, response.url, response.status_code)
                        if javascript and report["status"] == "javascript_required":
                            from .google_javascript import evaluate_challenge
                            state = evaluate_challenge(response.content, response.url,
                                initial_cookies=document_cookies(session.cookies.jar, response.url))
                            report["javascript"] = state["diagnostics"]
                            token = state["cookies"].get("SG_SS")
                            if token and len(token) < 4093:
                                session.cookies.set("SG_SS", token, domain="www.google.com", path="/")
                                expiry = int(time.time())  # Unknown expiry is not persisted as a permanent proof.
                                try:
                                    declared = SimpleCookie(state["cookie_writes"].get("SG_SS", ""))
                                    if declared.get("SG_SS") and declared["SG_SS"]["expires"]:
                                        expiry = int(parsedate_to_datetime(declared["SG_SS"]["expires"]).timestamp())
                                except (CookieError, ValueError, TypeError, OverflowError):
                                    pass
                                for cookie in session.cookies.jar:
                                    if cookie.name == "SG_SS":
                                        cookie.expires = expiry
                            if state["redirects"]:
                                target = urljoin(response.url, state["redirects"][-1])
                                dest = urlsplit(target)
                                if allowed_redirect(target, {"www.google.com"}) and dest.path == "/search":
                                    followup = fetch(target, source=response.url)
                                    if followup is not None:
                                        report["status"], report["hits"] = parse_page(followup.content, followup.url, followup.status_code)
                                else:
                                    report["status"] = "unsupported_javascript_redirect"
            report["web_search_performed"] = report.get("status") == "ok"
        except RequestException as exc:
            report.update(status="transport_error", error_type=type(exc).__name__)
        finally:
            save_cookies(session.cookies.jar, cookie_file)
            report["cookies_saved"] = len(session.cookies.jar)
    report["elapsed_ms"] = round((time.perf_counter()-started)*1000)
    return report


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--mode", choices=["standard", "basic"], default="standard")
    parser.add_argument("--timeout", type=float, default=15, help="Per-request seconds, not total deadline")
    parser.add_argument("--capture", action="store_true", help="Save private response bodies for diagnosis")
    parser.add_argument("--javascript", action="store_true", help="Experimental bounded JS runtime; no browser, not guaranteed to pass Google")
    parser.add_argument("--wire", action="store_true", help="Inspect outgoing header metadata; never print cookie values")
    args = parser.parse_args()
    try:
        report = search(args.query, mode=args.mode, timeout=args.timeout, capture=args.capture,
                        javascript=args.javascript, wire=args.wire)
    except (ImportError, OSError, ValueError) as exc:
        report = {"status": "setup_error", "error_type": type(exc).__name__, "web_search_performed": False}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["web_search_performed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
