"""Check actual Ollama request bodies, trace settings and independent byte guards."""

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from travel_agent.agent import chat, run_agent
from travel_agent.memory import MemoryStore
from travel_agent.memory_cli import recall_answer
from travel_agent.trace import read_trace


def response():
    return io.BytesIO(json.dumps({"message": {"content": "테스트 응답 [m-abcdef]"}}).encode())


class ContextTests(unittest.TestCase):
    def test_output_budget_is_explicit_and_context_stays_64k(self):
        with patch.dict(os.environ, {'AGENT_MAX_OUTPUT_TOKENS':'1536'}), patch('travel_agent.agent.urlopen',return_value=response()) as http:
            chat([],model='test',base_url='http://localhost',timeout=1)
        options=json.loads(http.call_args.args[0].data)['options']
        self.assertEqual(options['num_predict'],1536)
        self.assertEqual(options['num_ctx'],65536)

    def test_agent_request_uses_64k_by_default(self):
        with patch.dict(os.environ, {}, clear=True), patch("travel_agent.agent.urlopen", return_value=response()) as http:
            chat([{"role": "user", "content": "안녕"}], model="test", base_url="http://localhost", timeout=1)
        body = json.loads(http.call_args.args[0].data)
        self.assertEqual(body["options"]["num_ctx"], 65536)
        self.assertEqual(body["options"]["num_predict"], 4096)

    def test_recall_uses_same_config_and_accepts_summary_larger_than_old_budget(self):
        hit = {"chunk_id": "m-abcdef", "timestamp": "2026-10-18T00:00:00+09:00", "text": "합성 근거", "events": []}
        with patch.dict(os.environ, {"AGENT_CONTEXT_TOKENS": "65536", "AGENT_MAX_INPUT_BYTES": "196608"}), \
                patch("travel_agent.memory_cli.urlopen", return_value=response()) as http:
            recall_answer("질문", [hit], summary="가" * 5000)
        body = json.loads(http.call_args.args[0].data)
        self.assertEqual(body["options"]["num_ctx"], 65536)
        self.assertIn("가" * 5000, body["messages"][1]["content"])

    def test_override_reaches_model_request(self):
        with patch.dict(os.environ, {"AGENT_CONTEXT_TOKENS": "32768"}), \
                patch("travel_agent.agent.urlopen", return_value=response()) as http:
            chat([], model="test", base_url="http://localhost", timeout=1)
        self.assertEqual(json.loads(http.call_args.args[0].data)["options"]["num_ctx"], 32768)

    def test_invalid_token_setting_is_rejected_before_network(self):
        with patch.dict(os.environ, {"AGENT_CONTEXT_TOKENS": "invalid"}), patch("travel_agent.agent.urlopen") as http:
            with self.assertRaises(ValueError):
                chat([], model="test", base_url="http://localhost", timeout=1)
        http.assert_not_called()

    def test_agent_trace_matches_context_and_old_byte_ceiling_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp, MemoryStore(Path(tmp)/"memory.sqlite3") as store, \
                patch.dict(os.environ, {}, clear=True), \
                patch("travel_agent.agent.chat", return_value={"message": {"role": "assistant", "content": "안녕"}}):
            result = run_agent(store, "demo", "test", "질문", summary="가" * 5000, trace_dir=Path(tmp)/"traces", completion_protocol="legacy")
            start = read_trace(Path(tmp)/"traces", result["request_id"])[0]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(start["options"]["num_ctx"], 65536)
        self.assertEqual(start["limits"]["max_input_bytes"], 196608)
        self.assertEqual(start['web_provider'],'brave')
        self.assertEqual(start['web_backend'],'brave')


if __name__ == "__main__":
    unittest.main()
