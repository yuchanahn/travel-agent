import copy
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from travel_agent.runtime_context import prepare, request_bytes


class RuntimeContextTests(TestCase):
    def prepare(self,messages,chat,folder,**kwargs):
        return prepare(messages,[],chat=chat,model='fixture',base_url='local',folder=folder,
                       step=2,deadline=time.perf_counter()+30,max_bytes=196608,**kwargs)

    def test_single_turn_large_parallel_result_is_summarized_without_orphans(self):
        messages=[{'role':'system','content':'rules'}, {'role':'user','content':'budget changed to 200000'},
                  {'role':'assistant','content':'','tool_calls':[{'id':'a'},{'id':'b'}]},
                  {'role':'tool','tool_call_id':'a','content':'가'*24000},
                  {'role':'tool','tool_call_id':'b','content':'나'*24000}]
        original=copy.deepcopy(messages);requests=[]
        def model(m,**kwargs):
            requests.append(copy.deepcopy(m));self.assertEqual(kwargs['tools'],[])
            return {'message':{'content':'budget200000; searched a/b; prices unverified'},'done_reason':'stop'}
        with TemporaryDirectory() as folder:
            prepared,info=self.prepare(messages,model,folder)
            archived=json.loads((Path(folder)/'context-2-before.json').read_text(encoding='utf-8'))
            self.assertEqual(archived['messages'],original)
        self.assertTrue(info['compacted']);self.assertGreater(len(requests),1)
        self.assertEqual(prepared[-1],original[1]);self.assertEqual(prepared[0],original[0])
        self.assertFalse(any(m.get('tool_calls') or m['role']=='tool' for m in prepared))
        self.assertEqual(messages,original);self.assertLess(request_bytes(prepared,[]),64000)
        seen=''.join(json.loads(r[-1]['content'])['records'][0]['text'] for r in requests)
        self.assertIn('가',seen);self.assertIn('나',seen)

    def test_small_call_skips_llm_and_failed_summary_preserves_originals(self):
        small=[{'role':'system','content':'rules'},{'role':'user','content':'hello'}]
        def fail(*a,**kw):raise TimeoutError()
        with TemporaryDirectory() as folder:
            same,info=self.prepare(small,fail,folder)
            self.assertIs(same,small);self.assertEqual(info['summary_model_calls'],0)
            large=small+[{'role':'assistant','content':'x'*90000}]
            same,info=self.prepare(large,fail,folder)
            self.assertIs(same,large);self.assertEqual(info['warning'],'summary_failed')

    def test_repeated_search_catalog_is_indexed_instead_of_refed_in_full(self):
        packet={'hits':[{'id':'web:a','title':'synthetic lodge','snippet':'evidence '*5000}],
                'document_catalog':[{'id':'web:b','title':'nearby','description':'long '*10000}]}
        messages=[{'role':'system','content':'rules'},{'role':'user','content':'budget250000'},
                  {'role':'assistant','content':'old unverified claim'},
                  {'role':'tool','content':json.dumps(packet)},
                  {'role':'tool','content':json.dumps(packet)},
                  {'role':'user','content':'latest question'}]
        seen=[]
        def model(m,**kw):
            seen.append(copy.deepcopy(m));return {'message':{'content':'unverified; web:a web:b'},'done_reason':'stop'}
        with TemporaryDirectory() as folder:
            prepared,info=self.prepare(messages,model,folder)
        self.assertTrue(info['compacted']);self.assertEqual(info['inventory_duplicate_entries'],2)
        self.assertLess(len(json.dumps(seen)),10000)
        self.assertIn(messages[1],prepared);self.assertEqual(prepared[-1],messages[-1])
        self.assertIn('omitted_entries',json.dumps(seen));self.assertEqual(info['verbatim_user_messages'],2)

    def test_fixed_latest_question_is_never_silently_truncated(self):
        messages=[{'role':'system','content':'rules'},{'role':'user','content':'x'*80000}]
        with TemporaryDirectory() as folder:
            same,info=self.prepare(messages,lambda *a,**k:None,folder)
        self.assertIs(same,messages);self.assertEqual(info['warning'],'fixed_context_exceeds_target')

    def test_harness_feedback_does_not_replace_actual_user_question(self):
        question={'role':'user','content':'actual question and budget'}
        messages=[{'role':'system','content':'rules'},question,
                  {'role':'assistant','content':'x'*90000},{'role':'user','content':'harness finalization instruction'}]
        with TemporaryDirectory() as folder:
            prepared,info=self.prepare(messages,lambda *a,**k:{'message':{'content':'summary'},'done_reason':'stop'},
                                       folder,latest_user=question)
        self.assertTrue(info['compacted']);self.assertEqual(prepared[-1],question)

    def test_output_length_or_summary_expansion_is_rejected(self):
        messages=[{'role':'system','content':'rules'},{'role':'user','content':'q'},
                  {'role':'assistant','content':'x'*90000}]
        for response in [{'message':{'content':'short'},'done_reason':'length'},
                         {'message':{'content':'x'*17000},'done_reason':'stop'}]:
            with TemporaryDirectory() as folder:
                same,info=self.prepare(messages,lambda *a,**k:response,folder)
            self.assertIs(same,messages);self.assertEqual(info['warning'],'summary_failed')

    def test_loop_checks_again_after_tools_and_shares_deadline(self):
        import test_agent as fixtures
        from travel_agent.agent import run_agent
        from travel_agent.memory import MemoryStore
        checks=[]
        def manager(messages,tools,**limits):
            checks.append(copy.deepcopy(messages))
            return messages,{'compacted':False,'before_bytes':request_bytes(messages,tools),'summary_model_calls':0}
        with TemporaryDirectory() as folder,MemoryStore(Path(folder)/'memory.db') as store, \
             patch('travel_agent.agent.chat',side_effect=[fixtures.reply(calls=[fixtures.call(query='fixture')]),fixtures.reply('done')]), \
             patch('travel_agent.agent.execute_tool',return_value={'hits':[]}):
            result=run_agent(store,'u','s','q',trace_dir=Path(folder)/'traces',context_manager=manager)
        self.assertEqual(result['status'],'completed');self.assertEqual(len(checks),2)
        self.assertEqual(checks[-1][-1]['role'],'tool')
