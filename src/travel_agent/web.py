"""Key-free web search snippets. Does not fetch the linked pages."""

import json
import os
import re
import time
import base64
import binascii
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlencode
from lxml import html
import primp
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from urllib.parse import parse_qs, urlsplit, urlunsplit

from .memory import canonical


BACKENDS = {"duckduckgo", "bing", "google", "yahoo"}


class WebSearchError(RuntimeError):
    """The search provider failed; this is not proof that no information exists."""

    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.details = details or {}


class _EngineRows(list):
    def __init__(self, rows, details):
        super().__init__(rows)
        self.details = details


SEARCH_URLS = {"duckduckgo": "https://html.duckduckgo.com/html/", "bing": "https://www.bing.com/search"}
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _request_html(engine, query, timeout):
    """One anonymous HTTPS request to a fixed search endpoint; no browser or retry."""
    params = {"q": query}
    request = Request(SEARCH_URLS[engine] + "?" + urlencode(params),
                      headers={"Accept-Language": "en-US,en;q=0.9"})
    info = {"method": "GET"}
    try:
        if engine == "duckduckgo":
            # An HTTP client, not the DDGS search implementation or a browser.
            # Preserve the request shape of the earlier working DDG path.
            client = primp.Client(timeout=timeout, impersonate="random", impersonate_os="random")
            response = client.get(SEARCH_URLS[engine], params={"q": query, "b": "", "l": "kr-kr"})
            info["http_status"] = response.status_code
            if response.status_code != 200:
                raise WebSearchError("Search engine HTTP failure", details={"reason": "http_error", **info})
            if len(response.content) > MAX_RESPONSE_BYTES:
                raise WebSearchError("Search response too large", details={"reason": "response_too_large", **info})
            return response.content.decode("utf-8", errors="replace"), info
        try:
            incoming = build_opener(_NoRedirect()).open(request, timeout=timeout)
        except HTTPError as exc:
            incoming = exc
        with incoming:
            info["http_status"] = incoming.status
            if incoming.status != 200:
                raise WebSearchError("Search engine HTTP failure", details={"reason": "http_error", **info})
            body = incoming.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise WebSearchError("Search response too large", details={"reason": "response_too_large", **info})
            return body.decode("utf-8", errors="replace"), info
    except WebSearchError:
        raise
    except Exception as exc:
        raise WebSearchError("Search engine request failed", details={"reason": "request_failed", "error_type": type(exc).__name__, **info}) from exc


def _unwrap_search_url(raw, engine):
    if raw.startswith("//"):
        raw = "https:" + raw
    try:
        parsed = urlsplit(raw)
        if engine == "duckduckgo" and parsed.hostname in {"duckduckgo.com", "www.duckduckgo.com"} and parsed.path == "/l/":
            raw = parse_qs(parsed.query).get("uddg", [""])[0]
        elif engine == "bing" and parsed.hostname in {"bing.com", "www.bing.com"} and parsed.path == "/ck/a":
            value = parse_qs(parsed.query).get("u", [""])[0]
            if not value.startswith("a1"):
                return None
            encoded = value[2:]
            raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
        clean = _clean_url(raw)
        if not clean:
            return None
        host = urlsplit(clean).hostname
        if host in {"bing.com", "www.bing.com", "duckduckgo.com", "www.duckduckgo.com"}:
            return None
        return clean
    except (ValueError, UnicodeError, binascii.Error):
        return None


def _class_xpath(tag, name):
    return f'//{tag}[contains(concat(" ", normalize-space(@class), " "), " {name} ")]'


def _parse_search_html(text, engine):
    """Extract organic titles, target URLs and snippets, including linkless Bing h2."""
    tree = html.fromstring(text)
    selector = _class_xpath("div", "result__body") if engine == "duckduckgo" else _class_xpath("li", "b_algo")
    rows = []
    for card in tree.xpath(selector):
        headings = card.xpath('.//h2')
        if not headings:
            continue
        title = " ".join(headings[0].text_content().split())
        anchors = headings[0].xpath('.//a[@href]') or card.xpath('.//a[@href]')
        target = next((url for anchor in anchors if (url := _unwrap_search_url(anchor.get('href'), engine))), None)
        snippets = card.xpath('.//a[contains(concat(" ", normalize-space(@class), " "), " result__snippet ")]') if engine == "duckduckgo" else card.xpath('.//p')
        snippet = " ".join(" ".join(node.text_content().split()) for node in snippets)
        if title and target:
            rows.append({"title": title, "href": target, "body": snippet})
    return rows


def _direct_search(query, top_k, timeout, engine):
    text, info = _request_html(engine, query, timeout)
    lowered = text.lower()
    if any(marker in lowered for marker in ("anomaly-modal", "anomaly.js", 'id="b_captcha"', "verify you are human")):
        raise WebSearchError("Search engine access challenge", details={"reason": "access_challenge", **info})
    try:
        rows = _parse_search_html(text, engine)
    except (ValueError, html.etree.ParserError) as exc:
        raise WebSearchError("Search response could not be parsed", details={"reason": "empty_or_unparsed", **info}) from exc
    if not rows:
        raise WebSearchError("Search returned no parsed results", details={"reason": "empty_or_unparsed", **info})
    return _EngineRows(rows[:top_k], info)


def _duckduckgo_search(query, top_k, timeout):
    return _direct_search(query, top_k, timeout, "duckduckgo")


def _provider_search(query, top_k, timeout, backend):
    if backend not in SEARCH_URLS:
        raise ValueError("HTTP search supports duckduckgo and bing only")
    return _direct_search(query, top_k, timeout, backend)


def _clean_url(value):
    if not isinstance(value, str) or any(char.isspace() or ord(char) < 32 for char in value):
        return None
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return None
        url = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))
        return url if len(url) <= 2048 else None
    except ValueError:
        return None


def _combined_search(query, top_k, timeout, engines):
    """Call each explicit engine once, then fuse URL ranks without another LLM."""
    started = time.perf_counter()
    def run(engine):
        offset = round((time.perf_counter() - started) * 1000)
        tick = time.perf_counter()
        try:
            rows = _provider_search(query, top_k, timeout, engine)
            if not isinstance(rows, list):
                raise WebSearchError("Malformed engine results", details={"reason": "malformed_results"})
            clean = []
            for row in rows:
                if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in ("href", "title", "body")):
                    continue
                url = _clean_url(row["href"])
                if url and row["title"].strip():
                    clean.append({**row, "href": url})
            if rows and not clean:
                raise WebSearchError("No usable engine results", details={"reason": "no_usable_results"})
            return clean, {"status": "ok" if clean else "no_results", "hits": len(clean), **getattr(rows, "details", {}),
                           "start_ms": offset, "elapsed_ms": round((time.perf_counter() - tick) * 1000)}
        except WebSearchError as exc:
            return [], {"status": "error", "reason": exc.details.get("reason", "provider_failed"),
                        **{key: exc.details[key] for key in ("http_status", "method") if key in exc.details},
                        "start_ms": offset, "elapsed_ms": round((time.perf_counter() - tick) * 1000)}
        except Exception as exc:
            # Isolate an unexpected engine/library failure from its sibling.
            return [], {"status": "error", "reason": "engine_exception", "error_type": type(exc).__name__,
                        "start_ms": offset, "elapsed_ms": round((time.perf_counter() - tick) * 1000)}

    with ThreadPoolExecutor(max_workers=min(2, len(engines)), thread_name_prefix="web-engine") as executor:
        futures = {engine: executor.submit(run, engine) for engine in engines}
        outcomes = {engine: future.result() for engine, future in futures.items()}
    events = {engine: event for engine, (_, event) in outcomes.items()}
    metadata = {"engine_status": events,
                "engines_returned": [engine for engine, (rows, _) in outcomes.items() if rows],
                "search_complete": all(event["status"] != "error" for event in events.values()),
                "fusion": {"method": "rrf", "k": 60}}
    if not any(rows for rows, _ in outcomes.values()) and not metadata["search_complete"]:
        raise WebSearchError("No search engine returned usable results", details={"provider": "http", **metadata})
    merged = {}
    for engine, (rows, _) in outcomes.items():
        seen = set()
        for rank, row in enumerate(rows, 1):
            url = row["href"]
            if url in seen:
                continue
            seen.add(url)
            item = merged.setdefault(url, {**row, "engine_ranks": {}, "_score": 0.0})
            item["engine_ranks"][engine] = rank
            item["_score"] += 1 / (60 + rank)
    ordered = sorted(merged.values(), key=lambda row: -row["_score"])
    return [{key: value for key, value in row.items() if key != "_score"} for row in ordered], metadata


def web_search(query, *, top_k=3, timeout=15, max_bytes=3500, backend=None, provider=None):
    if not isinstance(query, str) or not 0 < len(query.strip()) <= 500:
        raise ValueError("Web query must contain 1..500 characters")
    if type(top_k) is not int or not 1 <= top_k <= 5:
        raise ValueError("top_k must be an integer 1..5")
    if not 0 < timeout <= 30 or not 1000 <= max_bytes <= 10000:
        raise ValueError("Web timeout must be 0..30 seconds and output budget 1000..10000 bytes")
    provider = provider if provider is not None else os.environ.get("WEB_SEARCH_PROVIDER", "http")
    if provider not in {"http", "webserp"}:
        raise ValueError("WEB_SEARCH_PROVIDER must be http or webserp; ddgs was replaced by http")
    default_backend = "google" if provider == "webserp" else "duckduckgo,bing"
    backend = backend if backend is not None else os.environ.get("WEB_SEARCH_BACKEND", default_backend)
    engines = list(dict.fromkeys(item.strip().lower() for item in backend.split(",")))
    if not engines or any(item not in BACKENDS for item in engines):
        raise ValueError("Unsupported WEB_SEARCH_BACKEND; choose explicit supported engines")
    if provider == "http" and any(engine not in SEARCH_URLS for engine in engines):
        raise ValueError("HTTP search supports duckduckgo and bing only")
    backend = ",".join(engines)
    metadata = {}
    if provider == "webserp":
        if backend == "google":
            from .webserp_provider import search_google
            rows, metadata = search_google(query.strip(), top_k, timeout)
        elif all(engine in {"duckduckgo", "yahoo"} for engine in engines):
            from .webserp_provider import search_html
            rows, metadata = search_html(query.strip(), top_k, timeout, engines)
        else:
            raise ValueError("webserp supports google alone, or duckduckgo and/or yahoo; no implicit Google fallback")
    else:
        rows, metadata = _combined_search(query.strip(), top_k, timeout, engines)
    if not isinstance(rows, list):
        raise WebSearchError("Web search provider returned malformed results")
    result = {"provider": provider, "backend_requested": backend, **metadata,
              "searched_at": datetime.now(timezone.utc).isoformat(),
              "content_kind": "search_snippet", "page_fetched": False,
              "web_search_performed": True, "status": "no_usable_results", "omitted_results": 0, "hits": []}
    if len(canonical(result).encode("utf-8")) > max_bytes:
        raise WebSearchError("Search metadata exceeds output budget", details={"reason": "output_budget_too_small"})
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not all(isinstance(row.get(key), str) for key in ("href", "title", "body")):
            continue
        url = _clean_url(row["href"])
        if not url or url in seen:
            continue
        seen.add(url)
        title = re.sub(r"\s+", " ", unescape(row["title"])).strip()
        snippet = re.sub(r"\s+", " ", unescape(row["body"])).strip()
        if not title:
            continue
        hit = {"id": "web:" + sha256(url.encode("utf-8")).hexdigest()[:16],
               "title": title[:200], "url": url, "snippet": snippet[:600],
               "snippet_truncated": len(snippet) > 600}
        if provider == "webserp" and isinstance(row.get("engine"), str) and row["engine"] in engines:
            hit["engine"] = row["engine"]
        if provider == "http" and isinstance(row.get("engine_ranks"), dict):
            hit["engines"] = list(row["engine_ranks"])
            hit["engine_ranks"] = row["engine_ranks"]
        trial = {**result, "status": "ok", "omitted_results": len(rows), "hits": [*result["hits"], hit]}
        if len(canonical(trial).encode("utf-8")) <= max_bytes and len(result["hits"]) < top_k:
            result["hits"].append(hit)
    result["omitted_results"] = len(rows) - len(result["hits"])
    result["status"] = "ok" if result["hits"] else "no_usable_results" if rows else "no_results"
    return result


def add_parser(subparsers):
    parser = subparsers.add_parser("web", help="Inspect live search snippets without an LLM")
    actions = parser.add_subparsers(dest="web_action", required=True)
    search = actions.add_parser("search")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=3)
    search.add_argument("--timeout", type=float, default=15)
    search.add_argument("--backend", help="Override WEB_SEARCH_BACKEND for this invocation")
    search.add_argument("--provider", choices=["http", "webserp"], help="Override WEB_SEARCH_PROVIDER")


def run(args):
    try:
        result = web_search(args.query, top_k=args.top_k, timeout=args.timeout, backend=args.backend,
                            provider=args.provider)
    except WebSearchError as exc:
        print(json.dumps({"error": str(exc), "error_type": type(exc).__name__,
                          "web_search_performed": False, **exc.details}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
