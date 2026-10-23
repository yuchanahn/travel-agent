import copy
from unittest import TestCase
from unittest.mock import patch
import test_agent as fixtures
from test_agent import call,reply
from travel_agent.travel_plan import blank,mutate


class PlanAgentTests(TestCase):
    setUp=fixtures.AgentTests.setUp
    tearDown=fixtures.AgentTests.tearDown
    run_agent=fixtures.AgentTests.run_agent

    def test_plan_tools_complete_without_becoming_web_evidence_and_read_new_revision(self):
        plan=blank();inputs=[]
        def handler(name,args):
            nonlocal plan
            if name in {'plan_add','plan_update'}:plan=mutate(plan,'upsert',args,model=True)
            return copy.deepcopy(plan)
        calls=[call('plan_read'),call('plan_add',items=[{'kind':'note','title':'성인2명'}]),call('plan_read')]
        def model(messages,**kwargs):
            inputs.append(copy.deepcopy(messages))
            return reply(calls=[calls[len(inputs)-1]]) if len(inputs)<=len(calls) else reply('초안에 기록했습니다.')
        with patch('travel_agent.agent.chat',side_effect=model):result=self.run_agent(plan_handler=handler,enable_web=False)
        self.assertEqual(result['status'],'completed')
        self.assertFalse(result['web_search_performed'])
        self.assertEqual(result['web_sources'],[])
        self.assertEqual(result['evidence_ids'],[])
        self.assertEqual(len(plan['items']),1)
        self.assertIn('성인2명',inputs[-1][-1]['content'])

    def test_unconfigured_plan_tool_cannot_mutate(self):
        with patch('travel_agent.agent.chat',side_effect=[reply(calls=[call('plan_update',items=[{'kind':'note','title':'x'}])]),reply('저장 불가')]):
            result=self.run_agent(enable_web=False)
        self.assertEqual(result['tool_calls'],1)
        self.assertFalse(result['web_search_performed'])
