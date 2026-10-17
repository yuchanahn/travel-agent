"""Search adapters using the reviewed webserp request builders and parsers.

Each invocation owns its HTTP session, including when agent tools run in threads.
This does not import browser credentials or persist cookies between invocations.
"""

from .web import WebSearchError


def search_html(query, top_k, timeout, engines):
    """Reuse pinned upstream fetch/parse steps, before its lossy URL deduplication.

    Only the engines exercised by this project are exposed. Empty parsing is
    reported separately, including when another engine returned useful results.
    """
    import asyncio
    import re

    if not engines or any(name not in {"duckduckgo", "yahoo"} for name in engines):
        raise ValueError("webserp HTML engines must be duckduckgo and/or yahoo")
    engines = list(dict.fromkeys(engines))
    try:
        from curl_cffi.requests import AsyncSession
        from webserp.engines import ALL_ENGINES
        from webserp.search import _fetch_engine
    except ImportError as exc:
        raise WebSearchError("webserp is not installed; install the project's [webserp] extra",
                             details={"provider": "webserp", "status": "dependency_missing"}) from exc

    async def fetch_all():
        async with AsyncSession() as session:
            return await asyncio.gather(*[
                _fetch_engine(ALL_ENGINES[name], query, top_k, timeout, None, session) for name in engines
            ])

    outcomes = asyncio.run(fetch_all())
    rows, empty, failures = [], [], []
    returned = []
    for name, hits, error in outcomes:
        if error:
            # The upstream exception text is not guaranteed to exclude secrets.
            status_match = re.search(r"HTTP Error (\d{3})", error)
            failures.append({"engine": name, "status": "upstream_error",
                             **({"http_status": int(status_match[1])} if status_match else {})})
        elif not hits:
            empty.append(name)
        else:
            returned.append(name)
            rows.extend({"href": hit.url, "title": hit.title, "body": hit.content, "engine": name} for hit in hits)
    metadata = {"request_mode": "upstream_html", "engines_requested": engines,
                "engines_returned": returned, "empty_or_unparsed_engines": empty, "engine_errors": failures}
    if not rows:
        raise WebSearchError("webserp HTML engines returned no usable evidence; empty parsing is not a proven empty search",
                             details={"provider": "webserp", "backend_requested": ",".join(engines),
                                      "status": "no_usable_evidence", **metadata})
    return rows, metadata


def response_kind(text):
    """Conservative diagnostics: ambiguous empty pages are never proven no-results."""
    from lxml import html

    lower = text.lower()
    tree = html.fromstring(text or "<html></html>")
    if tree.xpath('//form[contains(@action,"/sorry/")] | //iframe[contains(@src,"recaptcha")] '
                  '| //*[@id="captcha-form"]') or "unusual traffic from your computer network" in lower:
        return "captcha"
    if "before you continue to google" in lower:
        return "consent"
    if tree.xpath('//h3'):
        return "html_with_headings"
    if "/httpservice/retry/enablejs" in lower:
        return "javascript_required"
    if text.lstrip().startswith(")]}'"):
        return "async_framed"
    if "did not match any documents" in lower:
        return "explicit_no_results"
    return "unclassified"


def search_google(query, top_k, timeout):
    try:
        from curl_cffi.requests import Session
        from curl_cffi.requests.exceptions import RequestException
        from lxml.etree import LxmlError
        from webserp.client import random_impersonate
        from webserp.engines.google import Google
    except ImportError as exc:
        raise WebSearchError("webserp is not installed; install the project's [webserp] extra",
                             details={"provider": "webserp", "status": "dependency_missing"}) from exc

    engine = Google()
    spec = engine.build_request(query, top_k)
    profile = random_impersonate()
    metadata = {"provider": "webserp", "backend_requested": "google", "impersonate": profile,
                "request_mode": "upstream_arc", "request_language": spec.params.get("hl")}

    def fail(status, message):
        raise WebSearchError(message, details={**metadata, "status": status})

    try:
        with Session() as session:
            response = session.request(spec.method, spec.url, params=spec.params, data=spec.data or None,
                                       headers=spec.headers, cookies=spec.cookies, timeout=timeout,
                                       impersonate=profile)
            metadata["http_status"] = response.status_code
            metadata["response_bytes"] = len(response.content)
            if response.status_code != 200:
                fail("http_error", f"webserp Google returned HTTP {response.status_code}")
            try:
                kind = response_kind(response.text)
                metadata["response_kind"] = kind
                if kind in {"captcha", "consent", "javascript_required"}:
                    fail("access_interstitial", f"webserp Google returned {kind}; no search evidence")
                hits = engine.parse_response(response.text)
            except (ValueError, TypeError, LxmlError) as exc:
                fail("parse_error", f"webserp could not parse Google response ({type(exc).__name__})")
            if not hits and kind != "explicit_no_results":
                fail("unparsed_response", f"webserp Google yielded no usable results ({kind}); not a proven empty search")
            rows = [{"href": hit.url, "title": hit.title, "body": hit.content} for hit in hits[:top_k]]
            return rows, {key: value for key, value in metadata.items() if key not in {"provider", "backend_requested"}}
    except RequestException as exc:
        # Exception strings can contain URLs or transport internals; keep them out of traces.
        fail("transport_error", f"webserp transport failed ({type(exc).__name__})")
