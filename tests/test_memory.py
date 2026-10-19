"""Persistence and scope invariants without network, model downloads, or LLM calls."""

import tempfile
import unittest
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

from travel_agent.memory import MemoryStore, digest
from travel_agent.memory_cli import recall_answer


def event(event_id="one", content="원문: 예산은 40만 원.", timestamp="2026-10-17T10:00:00+09:00"):
    return {"event_id": event_id, "turn_id": event_id, "role": "user", "timestamp": timestamp, "content": content}


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "memory.sqlite3"
        self.store = MemoryStore(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_raw_roundtrip_and_idempotency(self):
        original = event(content="  줄바꿈\n예산: 40만 원.\n")
        self.assertEqual(self.store.add("u", "s", [original]), 1)
        self.assertEqual(self.store.add("u", "s", [original]), 0)
        self.store.close()
        self.store = MemoryStore(self.path)
        self.assertEqual(self.store.events("u", "s"), [original])

    def test_correction_is_append_only(self):
        self.store.add("u", "s", [event()])
        with self.assertRaises(ValueError):
            self.store.add("u", "s", [event(content="예산은 25만 원")])
        self.store.add("u", "s", [event("two", "예산을 25만 원으로 변경")])
        self.assertEqual(len(self.store.events("u", "s")), 2)

    def test_scope_and_chronology(self):
        self.store.add("u", "s", [event("late", timestamp="2026-10-17T03:00:00Z"), event("early", timestamp="2026-10-17T10:00:00+09:00")])
        self.store.add("other", "s", [event("secret")])
        self.store.add("u", "other", [event("secret")])
        self.assertEqual([item["event_id"] for item in self.store.events("u", "s")], ["early", "late"])

    def test_failed_import_rolls_back(self):
        with self.assertRaises(ValueError):
            self.store.add("u", "s", [event(), event("bad", timestamp="2026-10-17T10:00:00")])
        self.assertEqual(self.store.events("u", "s"), [])

    def test_stale_and_cross_scope_indexes_rejected(self):
        import numpy as np
        self.store.add("u", "s", [event()])
        self.store.save_index("u", "s", digest(self.store.events("u", "s")), {}, [{"chunk_id": "one", "text": "原文"}], np.array([[1, 0]], dtype=np.float32))
        with self.assertRaises(ValueError):
            self.store.read_index("other", "s")
        self.store.add("u", "s", [event("two")])
        with self.assertRaises(ValueError):
            self.store.read_index("u", "s")


class RecallTests(unittest.TestCase):
    def hit(self):
        return {"chunk_id": "m-abcdef", "timestamp": "2026-10-17T10:00:00+09:00",
                "text": "과거 assistant의 미검증 제안", "events": [{"event_id": "e1", "role": "assistant", "timestamp": "2026-10-17T10:00:00+09:00", "source_url": None}]}

    def test_no_evidence_does_not_call_model(self):
        with patch("travel_agent.llm_client.urlopen") as network:
            result = recall_answer("과거 이유?", [])
        network.assert_not_called()
        self.assertEqual(result["evidence_ids"], [])

    def test_oversized_summary_rejected_before_network(self):
        with patch.dict(os.environ, {"AGENT_MAX_INPUT_BYTES": "3000"}), patch("travel_agent.llm_client.urlopen") as network:
            with self.assertRaises(ValueError):
                recall_answer("질문", [self.hit()], "가" * 3000)
        network.assert_not_called()

    def test_original_roles_reach_model_and_citation_is_checked(self):
        response = io.BytesIO(json.dumps({"message": {"content": "과거 제안입니다. [m-abcdef]"}, "done_reason": "stop"}).encode())
        with patch("travel_agent.llm_client.urlopen", return_value=response) as network:
            result = recall_answer("무슨 제안이었지?", [self.hit()])
        request = json.loads(network.call_args.args[0].data)
        self.assertIn('"role":"assistant"', request["messages"][1]["content"])
        self.assertTrue(result["citation_ids_valid"])
        self.assertFalse(result["web_search_performed"])

    def test_invented_citation_is_not_marked_valid(self):
        response = io.BytesIO(json.dumps({"message": {"content": "[m-deadbeef]"}}).encode())
        with patch("travel_agent.llm_client.urlopen", return_value=response):
            result = recall_answer("질문", [self.hit()])
        self.assertFalse(result["citation_ids_valid"])


if __name__ == "__main__":
    unittest.main()
