"""Search parsing and agent contracts; fixtures never masquerade as live search."""

import tempfile
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from travel_agent.agent import run_agent, validate_call
from travel_agent.memory import MemoryStore, canonical
from travel_agent.trace import read_trace
from travel_agent.web import WebSearchError, web_search


def row(url="https://example.invalid/official", title="Official test page", body="Synthetic search snippet"):
    return {"href": url, "title": title, "body": body}


def model_reply(content="", calls=None):
    message = {"role": "assistant", "content": content}
    if calls is not None:
        message["tool_calls"] = calls
    return {"message": message, "done_reason": "stop"}


def web_call(query="public travel information"):
    return {"function": {"name": "web_search", "arguments": {"query": query, "top_k": 1}}}


class WebTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {'WEB_SEARCH_PROVIDER':'http','WEB_SEARCH_BACKEND':'bing'}).start()

    def test_normalizes_url_deduplicates_and_marks_snippet_scope(self):
        rows = [row("https://EXAMPLE.invalid/page#one", title="A &amp; B"), row("https://example.invalid/page#two"),
                row("javascript:alert(1)"), row("https://user:password@example.invalid/"), row("https://example.invalid/a b")]
        with patch("travel_agent.web._provider_search", return_value=rows) as provider:
            result = web_search("query", top_k=5, backend="bing")
        provider.assert_called_once_with("query", 5, 15, "bing")
        self.assertEqual(len(result["hits"]), 1)
        hit = result["hits"][0]
        self.assertEqual(hit["url"], "https://example.invalid/page")
        self.assertEqual(hit["title"], "A & B")
        self.assertEqual(result["content_kind"], "search_snippet")
        self.assertFalse(result["page_fetched"])

    def test_truncation_is_explicit_and_output_is_bounded(self):
        with patch("travel_agent.web._provider_search", return_value=[row(body="가" * 2000)]):
            result = web_search("q", max_bytes=2500)
        self.assertTrue(result["hits"][0]["snippet_truncated"])
        self.assertEqual(len(result["hits"][0]["snippet"]), 600)
        self.assertLessEqual(len(canonical(result).encode("utf-8")), 2500)

    def test_cannot_fit_hit_is_omitted_instead_of_breaking_url(self):
        with patch("travel_agent.web._provider_search", return_value=[row("https://example.invalid/" + "x" * 1800)]):
            result = web_search("q", max_bytes=1000)
        self.assertEqual(result["status"], "no_usable_results")
        self.assertEqual(result["omitted_results"], 1)

    def test_empty_results_are_not_a_provider_failure(self):
        with patch("travel_agent.web._provider_search", return_value=[]):
            result = web_search("q")
        self.assertEqual(result["status"], "no_results")
        self.assertTrue(result["web_search_performed"])

    def test_provider_failure_and_malformed_results_are_not_success(self):
        with patch("travel_agent.web._provider_search", side_effect=WebSearchError("unavailable")), self.assertRaises(WebSearchError):
            web_search("q")
        with patch("travel_agent.web._provider_search", return_value={}), self.assertRaises(WebSearchError):
            web_search("q")

    def test_invalid_input_rejected_before_network(self):
        with patch("travel_agent.web._provider_search") as provider:
            for options in [{"query": ""}, {"query": "x" * 501}, {"query": "q", "top_k": True},
                            {"query": "q", "top_k": 6}, {"query": "q", "backend": "auto"},
                            {"query": "q", "timeout": 0}]:
                with self.subTest(options=options), self.assertRaises(ValueError):
                    web_search(**options)
        provider.assert_not_called()

    def test_web_call_rejects_model_chosen_backend(self):
        self.assertEqual(validate_call(web_call())[0], "web_search")
        proposed = web_call()
        proposed["function"]["arguments"]["backend"] = "other"
        with self.assertRaises(ValueError):
            validate_call(proposed)


class AgentWebTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {'WEB_SEARCH_PROVIDER':'http','WEB_SEARCH_BACKEND':'bing'}).start()
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp.name) / "memory.sqlite3")
        self.trace_dir = Path(self.temp.name) / "traces"

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def run_agent(self, **kwargs):
        return run_agent(self.store, "demo", "test", "Find official travel information", trace_dir=self.trace_dir, **kwargs)

    def test_live_flag_sources_and_citation_come_from_executed_tool(self):
        with patch("travel_agent.web._provider_search", return_value=[row()]):
            evidence = web_search("q", top_k=1)
        source_id = evidence["hits"][0]["id"]
        replies = [model_reply(calls=[web_call()]), model_reply(f"검색 요약입니다. [{source_id}]")]
        with patch("travel_agent.agent.chat", side_effect=replies), patch("travel_agent.agent.web_search", return_value=evidence):
            result = self.run_agent()
        self.assertTrue(result["web_search_attempted"])
        self.assertTrue(result["web_search_performed"])
        self.assertTrue(result["citation_ids_valid"])
        self.assertEqual(result["web_sources"][0]["url"], "https://example.invalid/official")
        self.assertTrue(result["web_sources"][0]["cited"])
        self.assertEqual(result["web_sources"][0]["engines"], evidence["hits"][0]["engines"])
        records = read_trace(self.trace_dir, result["request_id"])
        tool_end = next(record for record in records if record["kind"] == "tool_end")
        self.assertFalse(tool_end["result"]["page_fetched"])

    def test_failed_network_attempt_is_distinct_from_completed_search(self):
        replies = [model_reply(calls=[web_call()]), model_reply("검색에 실패해 확인하지 못했습니다.")]
        with patch("travel_agent.agent.chat", side_effect=replies), patch("travel_agent.agent.web_search", side_effect=WebSearchError("timeout")):
            result = self.run_agent()
        self.assertTrue(result["web_search_attempted"])
        self.assertFalse(result["web_search_performed"])
        self.assertEqual(result["web_sources"], [])
        self.assertIn("tool_error", [r["kind"] for r in read_trace(self.trace_dir, result["request_id"])])

    def test_no_web_removes_schema_and_blocks_proposed_call(self):
        replies = [model_reply(calls=[web_call()]), model_reply("웹검색이 비활성화되어 있습니다.")]
        with patch("travel_agent.agent.chat", side_effect=replies) as model, patch("travel_agent.agent.web_search") as search:
            result = self.run_agent(enable_web=False)
        names = [tool["function"]["name"] for tool in model.call_args.kwargs["tools"]]
        self.assertNotIn("web_search", names)
        search.assert_not_called()
        self.assertFalse(result["web_search_attempted"])

    def test_greeting_does_not_claim_web_search_or_add_sources(self):
        with patch("travel_agent.agent.chat", return_value=model_reply("안녕하세요.")):
            result = self.run_agent()
        self.assertFalse(result["web_search_performed"])
        self.assertEqual(result["web_sources"], [])


if __name__ == "__main__":
    unittest.main()
