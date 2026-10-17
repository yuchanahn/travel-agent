"""Concurrency contracts with synchronization, independent of network timing."""

import copy
import threading
import unittest
import time
from unittest.mock import patch

import test_agent as fixtures
from test_agent import call, reply
from travel_agent.trace import read_trace
from travel_agent.trace import Trace
from travel_agent.agent import execute_batch


class ParallelToolTests(unittest.TestCase):
    setUp = fixtures.AgentTests.setUp
    tearDown = fixtures.AgentTests.tearDown
    run_agent = fixtures.AgentTests.run_agent
    def test_parallel_web_results_keep_request_order_and_call_ids(self):
        barrier = threading.Barrier(2)
        second_done = threading.Event()
        calls = [call('web_search', query='first'), call('web_search', query='second')]
        calls[0]['id'], calls[1]['id'] = 'first-id', 'second-id'
        inputs = []

        def execute(store, user, session, name, args, **kwargs):
            self.assertIsNone(store)
            barrier.wait(timeout=3)
            if args['query'] == 'first':
                self.assertTrue(second_done.wait(3))
                raise RuntimeError('Controlled first search failure')
            second_done.set()
            return {'hits': [], 'web_search_performed': True}

        def model(messages, **kwargs):
            inputs.append(copy.deepcopy(messages))
            return reply(calls=calls) if len(inputs) == 1 else reply('한 검색은 실패했고 다른 검색 결과는 비었습니다.')

        with patch('travel_agent.agent.chat', side_effect=model), patch('travel_agent.agent.execute_tool', side_effect=execute):
            result = self.run_agent(tool_workers=2)
        self.assertEqual(result['status'], 'completed')
        outputs = [m for m in inputs[1] if m['role'] == 'tool']
        self.assertEqual([m['tool_call_id'] for m in outputs], ['first-id', 'second-id'])
        self.assertIn('Controlled first search failure', outputs[0]['content'])
        self.assertNotIn('error', outputs[1]['content'])
        records = read_trace(self.traces, result['request_id'])
        starts = [r for r in records if r['kind'] == 'tool_start']
        ends = [r for r in records if r['kind'] in {'tool_end', 'tool_error'}]
        self.assertLess(max(r['sequence'] for r in starts), min(r['sequence'] for r in ends))
        self.assertEqual([r['sequence'] for r in records], list(range(1, len(records) + 1)))

    def test_workers_bound_concurrency_and_serial_mode(self):
        for workers in (1, 2):
            active = peak = 0
            lock = threading.Lock()
            barrier = threading.Barrier(workers)

            def execute(*args, **kwargs):
                nonlocal active, peak
                with lock:
                    active += 1
                    peak = max(peak, active)
                barrier.wait(timeout=3)
                with lock:
                    active -= 1
                return {'hits': []}

            calls = [call('web_search', query=str(i)) for i in range(4)]
            with patch('travel_agent.agent.chat', side_effect=[reply(calls=calls), reply('완료')]), patch('travel_agent.agent.execute_tool', side_effect=execute):
                self.run_agent(tool_workers=workers)
            self.assertEqual(peak, workers)

    def test_mixed_batch_keeps_memory_on_owner_thread(self):
        owner = threading.get_ident()
        web_ready = threading.Event()
        memory_done = threading.Event()

        def execute(store, user, session, name, args, **kwargs):
            if name == 'web_search':
                self.assertNotEqual(threading.get_ident(), owner)
                web_ready.set()
                self.assertTrue(memory_done.wait(3))
            else:
                self.assertEqual(threading.get_ident(), owner)
                self.assertTrue(web_ready.wait(3))
                store.db.execute('SELECT 1').fetchone()
                memory_done.set()
            return {'hits': []}

        calls = [call(query='memory'), call('web_search', query='web')]
        with patch('travel_agent.agent.chat', side_effect=[reply(calls=calls), reply('완료')]), patch('travel_agent.agent.execute_tool', side_effect=execute):
            result = self.run_agent()
        self.assertEqual(result['status'], 'completed')

    def test_batch_duplicate_runs_once_and_disabled_web_runs_never(self):
        for enabled, expected in ((True, 1), (False, 0)):
            calls = [call('web_search', query='same'), call('web_search', query='same')]
            with patch('travel_agent.agent.chat', side_effect=[reply(calls=calls), reply('완료')]), patch('travel_agent.agent.execute_tool', return_value={'hits': []}) as execute:
                self.run_agent(enable_web=enabled)
            self.assertEqual(execute.call_count, expected)

    def test_invalid_workers_rejected_before_model(self):
        with patch('travel_agent.agent.chat') as model:
            for workers in (0, 5, True):
                with self.assertRaises(ValueError):
                    self.run_agent(tool_workers=workers)
        model.assert_not_called()

    def test_expired_batch_does_not_start_provider(self):
        trace = Trace(self.traces)
        with patch('travel_agent.agent.execute_tool') as execute:
            results, attempted = execute_batch([call('web_search', query='q')],
                store=self.store, user='u', session='s', mode='hybrid', rerank=False,
                seen=set(), enable_web=True, deadline=time.perf_counter() - 1,
                trace=trace, step=1, workers=2)
        execute.assert_not_called()
        self.assertFalse(attempted)
        self.assertEqual(results[0][1]['error_type'], 'TimeoutError')
