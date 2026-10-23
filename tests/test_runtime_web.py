"""One-turn tool growth -> compaction -> recover original evidence -> checkpoint."""
import copy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from travel_agent.web_app import RunManager
from test_agent import call,reply


class RuntimeWebTests(TestCase):
    def test_checkpoint_restores_question_not_harness_feedback(self):
        from travel_agent.trace import Trace
        def agent(store,user,session,query,**kwargs):
            Trace(kwargs['trace_dir']).emit('model_start',messages=[{'role':'system','content':'rules'},
                {'role':'user','content':'현재 요약:\n\n질문:\n'+query},
                {'role':'user','content':'harness finalization'}])
            return {'status':'completed','answer':'fixture'}
        with TemporaryDirectory() as folder,patch('travel_agent.web_app.run_agent',side_effect=agent):
            manager=RunManager(folder)
            try:
                with patch.object(manager.pool,'submit'):rid=manager.submit('actual question',False)
                manager._execute(rid)
                saved=json.loads((Path(folder)/rid/'context.json').read_text(encoding='utf-8'))['history']
                self.assertEqual(saved[0]['content'],'actual question')
                self.assertEqual(saved[1]['content'],'harness finalization')
            finally:manager.pool.shutdown()

    def test_current_tool_original_is_searchable_after_same_turn_compaction(self):
        requests=[]
        def model(messages,**kwargs):
            requests.append(copy.deepcopy(messages))
            if len(requests)==1:return reply(calls=[call('web_search',query='synthetic',top_k=1)])
            if len(requests)==2:return reply(calls=[call('memory_search',query='합성정원 입장료 12345원',top_k=1)])
            return reply('fixture completed')
        result={'hits':[{'id':'web:'+'a'*16,'title':'synthetic','url':'https://example.invalid',
                        'snippet':'일반 설명 '*12000+'합성정원 입장료 12345원'}],
                'searched_at':'2026-10-23T00:00:00Z'}
        with TemporaryDirectory() as folder, \
             patch.dict(os.environ,{'MCP_CONFIG_FILE':str(Path('examples/mcp-servers.example.json').resolve()),'WEB_TOOL_FORMAT':'full_json'}), \
             patch('travel_agent.agent.chat',side_effect=model), \
             patch('travel_agent.web_app.context_chat',return_value=reply('원문을 검색하여 확인할 것')), \
             patch('travel_agent.agent.web_search',return_value=result):
            manager=RunManager(folder)
            try:
                with patch.object(manager.pool,'submit'):rid=manager.submit('합성 여행 조건',True)
                manager._execute(rid)
                job=manager.jobs[rid]
                self.assertEqual(job['state'],'done',job)
                self.assertEqual(job['result']['status'],'completed',job)
                self.assertGreaterEqual(job['context']['compactions'],1)
                self.assertIn('12345',requests[2][-1]['content'])
                checkpoint=json.loads((Path(folder)/rid/'context.json').read_text(encoding='utf-8'))
                self.assertEqual(next(m['content'] for m in reversed(checkpoint['history']) if m['role']=='user'),'합성 여행 조건')
                self.assertEqual(len(requests),3)
            finally:manager.pool.shutdown()
