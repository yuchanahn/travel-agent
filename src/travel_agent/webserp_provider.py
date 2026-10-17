"""Google adapter using the reviewed webserp request builder and parser.

Each invocation owns its HTTP session, including when agent tools run in threads.
This does not import browser credentials or persist cookies between invocations.
"""

from .web import WebSearchError


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
