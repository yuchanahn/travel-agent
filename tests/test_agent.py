"""Agent execution contracts with scripted model replies, not quality claims."""

import copy
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from travel_agent.agent import execute_tool, run_agent, validate_call
from travel_agent.memory import MemoryStore
from travel_agent.memory_cli import run
from travel_agent.trace import read_trace


def call(name="memory_search", **args):
    return {"function": {"name": name, "arguments": args}}


def reply(content="", calls=None, **extra):
    message = {"role": "assistant", "content": content, "thinking": "not persisted"}
    if calls is not None:
        message["tool_calls"] = calls
    return {"message": message, "done_reason": "stop", "prompt_eval_count": 10, "eval_count": 5, **extra}


def event(event_id="e1", content="환승 부담으로 강릉 제외"):
    return {"event_id": event_id, "turn_id": event_id, "timestamp": "2026-10-17T10:00:00+09:00", "role": "user", "content": content}


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.traces = Path(self.temp.name) / "traces"
        self.store = MemoryStore(Path(self.temp.name) / "memory.sqlite3")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def run_agent(self, **kwargs):
        return run_agent(self.store, "u", "s", "강릉 제외 이유?", trace_dir=self.traces, **kwargs)

    def test_direct_answer_has_no_retrieval_and_trace_is_readable(self):
        with patch("travel_agent.agent.chat", return_value=reply("안녕하세요.")), patch("travel_agent.agent.execute_tool") as tool:
            result = self.run_agent()
        tool.assert_not_called()
        self.assertEqual((result["status"], result["model_calls"], result["tool_calls"]), ("completed", 1, 0))
        self.assertEqual(result["citation_status"], "no_evidence")
        records = read_trace(self.traces, result["request_id"])
        self.assertEqual([r["kind"] for r in records], ["run_start", "model_start", "model_end", "run_end"])
        self.assertNotIn("not persisted", Path(result["trace_path"]).read_text(encoding="utf-8"))

    def test_search_result_is_sent_back_and_citation_checked(self):
        packed = {"hits": [{"id": "m-abcdef", "text": "환승 부담", "events": []}]}
        requests = []
        def model(messages, **kwargs):
            requests.append(copy.deepcopy(messages))
            return reply(calls=[call(query="강릉 제외")]) if len(requests) == 1 else reply("환승 때문입니다. [m-abcdef]")
        with patch("travel_agent.agent.chat", side_effect=model), patch("travel_agent.agent.execute_tool", return_value=packed):
            result = self.run_agent()
        self.assertEqual(result["tool_calls"], 1)
        self.assertTrue(result["citation_ids_valid"])
        self.assertEqual(requests[1][-1]["role"], "tool")
        self.assertIn("환승 부담", requests[1][-1]["content"])

    def test_show_is_scoped_and_raw_metadata_survives(self):
        self.store.add("other", "s", [event(content="private")])
        with self.assertRaises(ValueError):
            execute_tool(self.store, "u", "s", "memory_show", {"event_id": "e1"}, mode="hybrid", rerank=False)
        original = {**event("e2"), "source_url": "https://example.invalid/test", "synthetic": True}
        self.store.add("u", "s", [original])
        result = execute_tool(self.store, "u", "s", "memory_show", {"event_id": "e2"}, mode="hybrid", rerank=False)
        self.assertEqual(result["event"], original)

    def test_search_packs_whole_hits_and_counts_omissions(self):
        def hit(i, text):
            return {"chunk_id": i, "text": text, "timestamp": "now", "events": [], "scores": {}}
        result = {"mode": "hybrid", "reranker_revision": None, "hits": [hit("m-aa", "가" * 2000), hit("m-bb", "small")]}
        with patch("travel_agent.agent.search", return_value=result):
            packed = execute_tool(self.store, "u", "s", "memory_search", {"query": "q", "top_k": 3}, mode="hybrid", rerank=False)
        self.assertEqual([h["id"] for h in packed["hits"]], ["m-bb"])
        self.assertEqual(packed["omitted_hits"], 1)

    def test_rejects_scope_override_unknown_tool_and_invalid_types(self):
        for proposed in [call(query="q", user="other"), call("shell", command="anything"),
                         call(query="q", top_k=True), call(query=""), call("memory_show", event_id=3)]:
            with self.subTest(proposed=proposed), self.assertRaises(ValueError):
                validate_call(proposed)
        self.assertEqual(validate_call({"function": {"name": "memory_search", "arguments": '{"query":"q"}'}})[1], {"query": "q", "top_k": 3})

    def test_tool_error_is_observed_and_model_can_abstain(self):
        replies = [reply(calls=[call(query="q", user="other")]), reply("도구 오류로 확인하지 못했습니다.")]
        with patch("travel_agent.agent.chat", side_effect=replies), patch("travel_agent.agent.execute_tool") as tool:
            result = self.run_agent()
        tool.assert_not_called()
        self.assertEqual(result["status"], "completed")
        self.assertIn("tool_error", [r["kind"] for r in read_trace(self.traces, result["request_id"])])

    def test_repeat_call_does_not_reexecute_tool(self):
        responses = [reply(calls=[call(query="q")]), reply(calls=[call(query="q")]), reply("확인 불가")]
        with patch("travel_agent.agent.chat", side_effect=responses), patch("travel_agent.agent.execute_tool", return_value={"hits": []}) as tool:
            result = self.run_agent()
        self.assertEqual(tool.call_count, 1)
        self.assertEqual(result["tool_calls"], 2)

    def test_step_and_tool_limits_prevent_execution(self):
        with patch("travel_agent.agent.chat", return_value=reply(calls=[call(query="q"), call(query="other")])), patch("travel_agent.agent.execute_tool") as tool:
            self.assertEqual(self.run_agent(max_steps=1)["status"], "step_limit")
            self.assertEqual(self.run_agent(max_tool_calls=1)["status"], "tool_limit")
        tool.assert_not_called()

    def test_context_limit_prevents_model_call(self):
        with patch("travel_agent.agent.chat") as model:
            result = self.run_agent(summary="가" * 10000, max_input_bytes=10000)
        self.assertEqual(result["status"], "context_limit")
        model.assert_not_called()

    def test_deadline_after_response_stops_before_tool_execution(self):
        clock = [100.0]
        def slow_model(*args, **kwargs):
            clock[0] += 20
            return reply(calls=[call(query="q")])
        with patch("travel_agent.agent.time.perf_counter", side_effect=lambda: clock[0]), patch("travel_agent.agent.chat", side_effect=slow_model), patch("travel_agent.agent.execute_tool") as tool:
            result = self.run_agent(timeout=10)
        self.assertEqual(result["status"], "timeout")
        tool.assert_not_called()

    def test_transport_failure_and_truncation_are_not_success(self):
        with patch("travel_agent.agent.chat", side_effect=TimeoutError("unavailable")):
            self.assertEqual(self.run_agent()["status"], "model_error")
        with patch("travel_agent.agent.chat", return_value=reply("부분 답변", done_reason="length")):
            self.assertEqual(self.run_agent()["status"], "output_limit")

    def test_multiple_tools_and_show_citation(self):
        self.store.add("u", "s", [event("e1"), event("e2")])
        replies = [reply(calls=[call("memory_show", event_id="e1"), call("memory_show", event_id="e2")]), reply("환승 때문입니다. [event:e1]")]
        with patch("travel_agent.agent.chat", side_effect=replies):
            result = self.run_agent()
        self.assertEqual(result["tool_calls"], 2)
        self.assertTrue(result["citation_ids_valid"])

    def test_invalid_citation_and_malformed_protocol(self):
        with patch("travel_agent.agent.chat", return_value=reply("[m-deadbeef]")):
            result = self.run_agent()
        self.assertFalse(result["citation_ids_valid"])
        self.assertEqual(result["citation_status"], "invalid")
        with patch("travel_agent.agent.chat", return_value=reply(calls=[{}])):
            self.assertEqual(self.run_agent()["status"], "protocol_error")
        with patch("travel_agent.agent.chat", return_value=reply(calls={})):
            self.assertEqual(self.run_agent()["status"], "model_error")

    def test_trace_reader_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            read_trace(self.traces, "../private")

    def test_missing_citation_gets_one_recorded_repair_with_actual_ids(self):
        packed = {"hits": [{"id": "m-abcdef", "text": "환승 부담", "events": []}]}
        replies = [reply(calls=[call(query="q")]), reply("환승 부담입니다."), reply("환승 부담입니다. [m-abcdef]")]
        with patch("travel_agent.agent.chat", side_effect=replies), patch("travel_agent.agent.execute_tool", return_value=packed):
            result = self.run_agent()
        self.assertEqual((result["model_calls"], result["citation_repair_attempts"]), (3, 1))
        self.assertEqual(result["citation_status"], "valid")
        self.assertIn("citation_repair", [r["kind"] for r in read_trace(self.traces, result["request_id"])])

    def test_fabricated_citation_without_retrieval_can_be_removed(self):
        with patch("travel_agent.agent.chat", side_effect=[reply("두 명입니다. [m-1]"), reply("두 명입니다.")]):
            result = self.run_agent()
        self.assertEqual(result["citation_status"], "no_evidence")
        self.assertEqual(result["citation_repair_attempts"], 1)

    def test_raw_event_status_metadata_does_not_change_show_exit_code(self):
        self.store.add("u", "s", [{**event(), "status": "unverified"}])
        args = SimpleNamespace(db=self.store.path, user="u", session="s", memory_action="show", event_id="e1")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run(args), 0)


if __name__ == "__main__":
    unittest.main()
