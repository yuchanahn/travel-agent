"""Key-free web search snippets. Does not fetch the linked pages."""

import json
import os
import re
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from urllib.parse import urlsplit, urlunsplit

from .memory import canonical


BACKENDS = {"duckduckgo", "bing", "brave", "google", "yahoo", "mojeek", "startpage", "yandex"}


class WebSearchError(RuntimeError):
    """The search provider failed; this is not proof that no information exists."""

    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.details = details or {}


def _provider_search(query, top_k, timeout, backend):
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException

    try:
        with DDGS(timeout=timeout, verify=True) as client:
            return client.text(query, region="kr-kr", safesearch="moderate", max_results=top_k, backend=backend)
    except DDGSException as exc:
        raise WebSearchError(f"Web search provider failed: {exc}") from exc


def web_search(query, *, top_k=3, timeout=15, max_bytes=3500, backend=None, provider=None):
    if not isinstance(query, str) or not 0 < len(query.strip()) <= 500:
        raise ValueError("Web query must contain 1..500 characters")
    if type(top_k) is not int or not 1 <= top_k <= 5:
        raise ValueError("top_k must be an integer 1..5")
    if not 0 < timeout <= 30 or not 1000 <= max_bytes <= 10000:
        raise ValueError("Web timeout must be 0..30 seconds and output budget 1000..10000 bytes")
    provider = provider if provider is not None else os.environ.get("WEB_SEARCH_PROVIDER", "ddgs")
    if provider not in {"ddgs", "webserp"}:
        raise ValueError("WEB_SEARCH_PROVIDER must be ddgs or webserp")
    default_backend = "google" if provider == "webserp" else "duckduckgo,bing"
    backend = backend if backend is not None else os.environ.get("WEB_SEARCH_BACKEND", default_backend)
    engines = [item.strip().lower() for item in backend.split(",")]
    if not engines or any(item not in BACKENDS for item in engines):
        raise ValueError("Unsupported WEB_SEARCH_BACKEND; choose explicit supported engines")
    backend = ",".join(engines)
    metadata = {}
    if provider == "webserp":
        if backend != "google":
            raise ValueError("The webserp adapter currently supports only backend=google")
        from .webserp_provider import search_google
        rows, metadata = search_google(query.strip(), top_k, timeout)
    else:
        rows = _provider_search(query.strip(), top_k, timeout, backend)
    if not isinstance(rows, list):
        raise WebSearchError("Web search provider returned malformed results")
    result = {"provider": provider, "backend_requested": backend, **metadata,
              "searched_at": datetime.now(timezone.utc).isoformat(),
              "content_kind": "search_snippet", "page_fetched": False,
              "web_search_performed": True, "status": "no_results", "omitted_results": 0, "hits": []}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not all(isinstance(row.get(key), str) for key in ("href", "title", "body")):
            continue
        try:
            parsed = urlsplit(row["href"].strip())
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                continue
            if any(char.isspace() or ord(char) < 32 for char in row["href"]):
                continue
            url = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))
        except ValueError:
            continue
        if url in seen or len(url) > 2048:
            continue
        seen.add(url)
        title = re.sub(r"\s+", " ", unescape(row["title"])).strip()
        snippet = re.sub(r"\s+", " ", unescape(row["body"])).strip()
        if not title:
            continue
        hit = {"id": "web:" + sha256(url.encode("utf-8")).hexdigest()[:16],
               "title": title[:200], "url": url, "snippet": snippet[:600],
               "snippet_truncated": len(snippet) > 600}
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
    search.add_argument("--provider", choices=["ddgs", "webserp"], help="Override WEB_SEARCH_PROVIDER")


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
