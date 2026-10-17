"""Provider routing, honest failure semantics, and source contract fixtures."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from travel_agent.agent import run_agent
from travel_agent.memory import MemoryStore
from travel_agent.trace import read_trace
from travel_agent.web import WebSearchError, web_search
from travel_agent.webserp_provider import search_google, search_html


class RoutingTests(unittest.TestCase):
    def test_webserp_shares_url_sanitizing_ids_and_output_budget(self):
        rows = [{"href": "https://EXAMPLE.invalid/page#fragment", "title": "Example", "body": "snippet"},
                {"href": "javascript:bad()", "title": "Bad", "body": "bad"}]
        with patch.dict(os.environ, {}, clear=True), \
                patch("travel_agent.webserp_provider.search_google", return_value=(rows, {"http_status": 200})) as provider:
            result = web_search("q", provider="webserp", top_k=1)
        provider.assert_called_once_with("q", 1, 15)
        self.assertEqual(result["provider"], "webserp")
        self.assertEqual(result["backend_requested"], "google")
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["hits"][0]["url"], "https://example.invalid/page")
        self.assertFalse(result["page_fetched"])

    def test_environment_selects_provider_for_agent_calls(self):
        with patch.dict(os.environ, {"WEB_SEARCH_PROVIDER": "webserp", "WEB_SEARCH_BACKEND": "google"}), \
                patch("travel_agent.webserp_provider.search_google", return_value=([], {})) as provider:
            result = web_search("q")
        provider.assert_called_once()
        self.assertEqual(result["provider"], "webserp")

    def test_unsupported_provider_or_engine_is_rejected_before_network(self):
        for kwargs in ({"provider": "unknown"}, {"provider": "webserp", "backend": "bing"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                web_search("q", **kwargs)

    def test_agent_failure_retains_provider_diagnostics_without_claiming_search(self):
        call = {"id": "search-1", "function": {"name": "web_search", "arguments": {"query": "public query"}}}
        replies = [{"message": {"role": "assistant", "content": "", "tool_calls": [call]}},
                   {"message": {"role": "assistant", "content": "검색에 실패해서 확인하지 못했습니다."}}]
        failure = WebSearchError("Google response could not be parsed", details={"provider": "webserp",
                                  "status": "unparsed_response", "http_status": 200})
        with tempfile.TemporaryDirectory() as tmp, MemoryStore(Path(tmp)/"memory.sqlite3") as store, \
                patch.dict(os.environ, {"WEB_SEARCH_PROVIDER": "webserp", "WEB_SEARCH_BACKEND": "google"}), \
                patch("travel_agent.agent.chat", side_effect=replies), \
                patch("travel_agent.webserp_provider.search_google", side_effect=failure):
            result = run_agent(store, "demo", "test", "Find public information", trace_dir=Path(tmp)/"traces")
            errors = [r for r in read_trace(Path(tmp)/"traces", result["request_id"]) if r["kind"] == "tool_error"]
        self.assertTrue(result["web_search_attempted"])
        self.assertFalse(result["web_search_performed"])
        self.assertEqual(errors[0]["result"]["http_status"], 200)
        self.assertEqual(errors[0]["result"]["provider"], "webserp")


@unittest.skipUnless(importlib.util.find_spec("webserp") and importlib.util.find_spec("curl_cffi"),
                     "Install the optional webserp extra to exercise the upstream parser")
class AdapterTests(unittest.TestCase):
    def search(self, text, status=200):
        response = SimpleNamespace(text=text, content=text.encode(), status_code=status)
        with patch("curl_cffi.requests.Session") as session:
            session.return_value.__enter__.return_value.request.return_value = response
            return search_google("q", 3, 15)

    def test_upstream_parser_result_is_converted_to_existing_row_contract(self):
        rows, metadata = self.search('<html><body><div class="MjjYud"><a href="https://example.invalid/">'
                                     '<h3>Official fixture</h3></a><div class="VwiC3b">Snippet</div></div></body></html>')
        self.assertEqual(rows, [{"href": "https://example.invalid/", "title": "Official fixture", "body": "Snippet"}])
        self.assertEqual(metadata["http_status"], 200)

    def test_200_async_empty_or_js_page_is_not_success(self):
        for text, expected in [("<html>unrecognized page</html>", "unparsed_response"),
                               (")]}'\nconfiguration", "unparsed_response"),
                               ('<a href="/httpservice/retry/enablejs">Enable JS</a>', "access_interstitial")]:
            with self.subTest(text=text), self.assertRaises(WebSearchError) as context:
                self.search(text)
            self.assertEqual(context.exception.details["status"], expected)

    def test_explicit_no_results_is_distinct_from_failure(self):
        rows, _ = self.search('<html>Your search did not match any documents.</html>')
        self.assertEqual(rows, [])

    def test_http_error_metadata_is_retained(self):
        with self.assertRaises(WebSearchError) as context:
            self.search("blocked", 403)
        self.assertEqual(context.exception.details["http_status"], 403)

    def test_transport_exception_does_not_leak_internals(self):
        from curl_cffi.requests.exceptions import RequestException
        with patch("curl_cffi.requests.Session") as session, self.assertRaises(WebSearchError) as context:
            session.return_value.__enter__.return_value.request.side_effect = RequestException("secret transport data")
            search_google("q", 3, 15)
        self.assertNotIn("secret", str(context.exception))
        self.assertEqual(context.exception.details["status"], "transport_error")

    def test_html_empty_engine_is_visible_when_another_engine_returns_hits(self):
        from webserp.engines.base import Result

        async def fetch(engine, *args):
            if engine.name == "duckduckgo":
                return engine.name, [], None
            return engine.name, [Result("Fixture", "https://example.invalid/A", "text", engine.name)], None

        with patch("webserp.search._fetch_engine", side_effect=fetch):
            rows, metadata = search_html("q", 3, 15, ["duckduckgo", "yahoo"])
        self.assertEqual(rows[0]["engine"], "yahoo")
        self.assertEqual(metadata["empty_or_unparsed_engines"], ["duckduckgo"])

    def test_html_zero_results_is_not_silent_success(self):
        async def fetch(engine, *args):
            return engine.name, [], None

        with patch("webserp.search._fetch_engine", side_effect=fetch), self.assertRaises(WebSearchError) as context:
            search_html("q", 3, 15, ["yahoo"])
        self.assertEqual(context.exception.details["status"], "no_usable_evidence")

    def test_html_upstream_error_text_is_sanitized(self):
        async def fetch(engine, *args):
            return engine.name, [], "HTTP Error 429: sensitive transport context"

        with patch("webserp.search._fetch_engine", side_effect=fetch), self.assertRaises(WebSearchError) as context:
            search_html("q", 3, 15, ["yahoo"])
        self.assertNotIn("sensitive", str(context.exception.details))
        self.assertEqual(context.exception.details["engine_errors"][0]["http_status"], 429)

    def test_shared_url_packing_preserves_case_and_engine_provenance(self):
        from webserp.engines.base import Result

        async def fetch(engine, *args):
            return engine.name, [Result("Upper", "https://example.invalid/A", "one", engine.name),
                                 Result("Lower", "https://example.invalid/a", "two", engine.name)], None

        with patch("webserp.search._fetch_engine", side_effect=fetch):
            result = web_search("q", provider="webserp", backend="yahoo", top_k=3)
        self.assertEqual([x["url"] for x in result["hits"]], ["https://example.invalid/A", "https://example.invalid/a"])
        self.assertEqual(result["hits"][0]["engine"], "yahoo")


if __name__ == "__main__":
    unittest.main()
