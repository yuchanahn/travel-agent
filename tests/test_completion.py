"""Explicit completion is a model decision; these fixtures test the protocol."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from travel_agent.agent import final_answer, run_agent
from travel_agent.memory import MemoryStore
from travel_agent.web_app import visible_event


def reply(content='',calls=None,reason='stop'):
    return {'message':{'role':'assistant','content':content,**({'tool_calls':calls} if calls else {})},'done_reason':reason}


class CompletionTests(unittest.TestCase):
    def test_default_allows_seventh_call_and_stops_at_twelve(self):
        r=self.run_fixture([reply('진행합니다.')]*6+[reply('<final>일곱 번째 호출에서 완료.</final>')])
        self.assertEqual((r['status'],r['model_calls']),('completed',7))
        self.assertFalse(r['finalization_for_budget'])
        limited=self.run_fixture(reply('진행합니다.'))
        self.assertEqual((limited['status'],limited['model_calls']),('step_limit',12))
        self.assertEqual(self.events[0]['limits']['max_steps'],12)

    def test_same_progress_text_finishes_legacy_but_not_explicit(self):
        old=self.run_fixture(reply('검색을 진행하겠습니다.'),completion_protocol='legacy')
        new=self.run_fixture([reply('검색을 진행하겠습니다.'),reply('<final>질문이 필요합니다.</final>')])
        self.assertEqual(old['model_calls'],1)
        self.assertFalse(old['completion_signal_received'])
        self.assertEqual(new['model_calls'],2)
        self.assertEqual(new['answer'],'질문이 필요합니다.')

    def run_fixture(self,replies,**kwargs):
        with TemporaryDirectory() as folder, MemoryStore(Path(folder)/'db') as store:
            self.requests=[]
            def model(messages,**options):
                self.requests.append(copy.deepcopy(messages))
                return replies[len(self.requests)-1] if isinstance(replies,list) else replies
            with patch('travel_agent.agent.chat',side_effect=model):
                result=run_agent(store,'public','fixture','public synthetic question',trace_dir=Path(folder)/'trace',**kwargs)
            self.events=[json.loads(line) for line in Path(result['trace_path']).read_text(encoding='utf-8').splitlines()]
            return result

    def test_progress_is_continued_then_explicit_final_is_unwrapped(self):
        r=self.run_fixture([reply('検索を続けます。'),reply('<final>최종 답변입니다.</final>')])
        self.assertEqual((r['status'],r['answer'],r['continuation_requests']),('completed','최종 답변입니다.',1))
        self.assertTrue(r['completion_signal_received'])
        self.assertEqual(self.requests[1][-2]['content'],'検索を続けます。')
        self.assertIn('다음 행동',self.requests[1][-1]['content'])

    def test_progress_can_be_followed_by_real_tool_call(self):
        call={'id':'fixture-call','function':{'name':'web_search','arguments':{'query':'public example','top_k':1}}}
        with patch('travel_agent.agent.execute_tool',return_value={'hits':[],'searched_at':'fixture'}) as execute:
            r=self.run_fixture([reply('확인하겠습니다.'),reply(calls=[call]),reply('<final>찾지 못했습니다.</final>')])
        self.assertEqual((r['model_calls'],r['tool_calls'],execute.call_count),(3,1,1))
        self.assertEqual(self.requests[2][-1]['role'],'tool')
        self.assertEqual(self.requests[2][-1]['tool_call_id'],'fixture-call')

    def test_model_may_finish_with_question_without_forced_search(self):
        r=self.run_fixture(reply('<final>숙박 날짜를 알려주세요.</final>'))
        self.assertEqual((r['status'],r['tool_calls'],r['continuation_requests']),('completed',0,0))

    def test_model_final_is_not_overruled_by_semantic_heuristic(self):
        source={'id':'web:1234567890abcdef','url':'https://example.org','title':'fixture','page_fetched':False}
        r=self.run_fixture(reply('<final>추가 조회 없이 마무리합니다.</final>'),prior_sources=[source])
        self.assertEqual((r['status'],r['model_calls'],r['evidence_review_attempts']),('completed',1,0))
        self.assertEqual(r['citation_status'],'missing')  # Report, do not pretend fact verification.

    def test_missing_signal_stops_at_limit_without_success(self):
        r=self.run_fixture(reply('진행 중입니다.'),max_steps=3)
        self.assertEqual((r['status'],r['model_calls'],r['completion_signal_received']),('step_limit',3,False))
        self.assertEqual(r['answer'],'')

    def test_forced_final_is_marked_as_budget_stop(self):
        r=self.run_fixture(reply('<final>현재 결과</final>'),max_steps=1)
        self.assertEqual(r['status'],'step_limit')
        self.assertTrue(r['completion_signal_received'])
        self.assertTrue(r['finalization_for_budget'])

    def test_tags_do_not_make_truncated_response_success(self):
        r=self.run_fixture(reply('<final>부분 답변</final>',reason='length'))
        self.assertEqual(r['status'],'output_limit')
        self.assertFalse(r['completion_signal_received'])

    def test_empty_nested_or_trailing_final_is_not_a_signal(self):
        for text in ['<final></final>','prefix <final>yes</final>','<final>yes</final> tail',
                     '<final>a</final><final>b</final>','<final><final>a</final></final>']:
            self.assertIsNone(final_answer(text))

    def test_continuation_and_final_events_are_visible_without_model_inputs(self):
        r=self.run_fixture([reply('진행합니다.'),reply('<final>끝.</final>')])
        views=[visible_event(e) for e in self.events if e['kind'] in ('continuation_requested','completion_signal')]
        self.assertEqual(len(views),2)
        self.assertNotIn('messages',json.dumps(views))

    def test_invalid_protocol_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_fixture(reply('unused'),completion_protocol='unknown')
