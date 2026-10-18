"""Branch isolation and recovery after lossy summaries, without model downloads."""
import copy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from travel_agent.agent import run_agent
from travel_agent.memory import MemoryStore, build_bm25_index, search
from travel_agent.session_context import compact_context, turn_events
from travel_agent.web_app import RunManager


def event(identifier, content, role='user'):
    return {'event_id':identifier,'turn_id':identifier,'role':role,
            'timestamp':'2026-10-19T00:00:00+00:00','content':content}


class LexicalMemoryTests(unittest.TestCase):
    def test_lexical_index_restores_exact_offsets_without_encoder(self):
        text='가나다'*450 + '강릉은 계단 때문에 제외했다.'
        with TemporaryDirectory() as folder, MemoryStore(Path(folder)/'db') as store:
            store.add('u','s',[event('a',text)])
            with patch('travel_agent.memory.get_encoder') as encoder:
                build_bm25_index(store,'u','s')
                result=search(store,'u','s','강릉 제외 계단',mode='bm25')
            encoder.assert_not_called()
            self.assertTrue(any('계단' in hit['text'] for hit in result['hits']))
            _, chunks, vectors=store.read_index('u','s')
            chunks.sort(key=lambda c:c['start_char'])
            self.assertEqual(vectors.shape[1],0)
            for chunk in chunks:
                self.assertEqual(chunk['text'].split('\n',1)[1],text[chunk['start_char']:chunk['end_char']])
            self.assertEqual(chunks[0]['start_char'],0)
            self.assertEqual(chunks[-1]['end_char'],len(text))
            self.assertTrue(all(b['start_char']<=a['end_char'] for a,b in zip(chunks,chunks[1:])))
            with self.assertRaises(ValueError):search(store,'u','other','계단',mode='bm25')
            with self.assertRaises(ValueError):search(store,'u','s','계단',mode='hybrid')
            store.add('u','s',[event('b','예산 변경')])
            with self.assertRaises(ValueError):search(store,'u','s','계단',mode='bm25')

    def test_automatic_evidence_is_citable_and_memory_tools_remain_optional(self):
        seen=[]
        def model(messages,**kwargs):
            seen.extend(copy.deepcopy(messages))
            return {'message':{'role':'assistant','content':'계단 때문입니다. [m-abcdef]'},'done_reason':'stop'}
        with TemporaryDirectory() as folder, MemoryStore(Path(folder)/'db') as store:
            store.add('u','s',[event('a','강릉 제외: 계단')])
            build_bm25_index(store,'u','s')
            with patch('travel_agent.agent.chat',side_effect=model):
                result=run_agent(store,'u','s','제외 이유?',summary='여행 후보 검토 중',mode='bm25',
                    recalled_memory={'hits':[{'id':'m-abcdef','text':'강릉 제외: 계단'}]},trace_dir=Path(folder)/'trace')
            self.assertTrue(result['citation_ids_valid'])
            self.assertIn('강릉 제외: 계단',seen[-1]['content'])
            self.assertEqual(result['tool_calls'],0)

    def test_prior_retrieved_citation_survives_followup_without_new_retrieval(self):
        with TemporaryDirectory() as folder, MemoryStore(Path(folder)/'db') as store, \
             patch('travel_agent.agent.chat',return_value={'message':{'role':'assistant','content':'이전 근거입니다. [m-abcdef]'}}):
            result=run_agent(store,'u','s','이전 인용?',prior_memory_ids=['m-abcdef'],trace_dir=Path(folder)/'trace')
        self.assertTrue(result['citation_ids_valid'])


class CompactionTests(unittest.TestCase):
    def history(self):
        return [message for i in range(5) for message in [
            {'role':'user','content':str(i)+' 여행 조건 '+('가나다 '*400)},
            {'role':'assistant','content':'기록했습니다.'}]]

    def test_compaction_retains_complete_recent_groups_and_original_input(self):
        history=self.history();original=copy.deepcopy(history)
        # Include native tool messages in a retained turn.
        history[-1:-1]=[{'role':'assistant','content':'','tool_calls':[{'id':'call1'}]},
                         {'role':'tool','tool_call_id':'call1','content':'result'}]
        with TemporaryDirectory() as folder, patch.dict(os.environ,{'WEB_CONTEXT_COMPACT_BYTES':'4000'}), \
             patch('travel_agent.session_context.chat',return_value={'message':{'content':'여행 조건 요약'},'done_reason':'stop','eval_count':8}) as model:
            recent,summary,info=compact_context(history,'기존 요약',folder=folder,model='test',base_url='http://test')
            self.assertEqual(summary,'여행 조건 요약')
            self.assertTrue(info['compacted'])
            self.assertEqual([m for m in recent if m['role']=='user'],[history[6],history[8]])
            self.assertEqual(recent[-3]['tool_calls'][0]['id'],recent[-2]['tool_call_id'])
            self.assertEqual(history[0],original[0])
            self.assertEqual(model.call_args.kwargs['tools'],[])
            self.assertTrue((Path(folder)/'summary-call.json').exists())

    def test_failed_summary_keeps_all_history_and_prior_summary(self):
        history=self.history()
        with TemporaryDirectory() as folder, patch.dict(os.environ,{'WEB_CONTEXT_COMPACT_BYTES':'4000'}), \
             patch('travel_agent.session_context.chat',side_effect=TimeoutError):
            recent,summary,info=compact_context(history,'이전 요약',folder=folder,model='test',base_url='http://test')
        self.assertEqual(recent,history)
        self.assertEqual(summary,'이전 요약')
        self.assertEqual(info['warning'],'summary_failed')

    def test_short_history_does_not_call_summary_model(self):
        with TemporaryDirectory() as folder, patch('travel_agent.session_context.chat') as model:
            _,_,info=compact_context([{'role':'user','content':'안녕'}],'',folder=folder,model='test',base_url='http://test')
        model.assert_not_called()
        self.assertFalse(info['compacted'])


class BranchMemoryTests(unittest.TestCase):
    def execute(self,manager,query,parent=None):
        # Run synchronously to inspect the exact store and kwargs supplied to the agent.
        with patch.object(manager.pool,'submit'):
            identifier=manager.submit(query,False,parent)
        manager._execute(identifier)
        job=manager.jobs[identifier]
        self.assertEqual(job['state'],'done',job)
        return identifier

    def test_followup_restart_siblings_and_new_chat_are_isolated(self):
        seen=[]
        def agent(store,user,session,query,**kwargs):
            seen.append({'query':query,'events':store.events(user,session),'kwargs':copy.deepcopy(kwargs)})
            return {'status':'completed','answer':'확인했습니다.'}
        with TemporaryDirectory() as folder, patch('travel_agent.web_app.run_agent',side_effect=agent):
            manager=RunManager(folder)
            try:
                root=self.execute(manager,'강릉 제외 이유는 계단')
                branch=self.execute(manager,'예산 30만원',root)
                sibling=self.execute(manager,'비가 오면?',root)
                self.execute(manager,'새 여행')
                self.assertEqual(seen[0]['events'],[])
                self.assertTrue(any('계단' in e['content'] for e in seen[1]['events']))
                self.assertFalse(any('30만원' in e['content'] for e in seen[2]['events']))
                self.assertEqual(seen[3]['events'],[])
                self.assertNotIn('30만원',json.dumps(seen[2]['kwargs']['history'],ensure_ascii=False))
                self.assertTrue((Path(folder)/branch/'context.json').exists())
            finally:manager.pool.shutdown()
            restored=RunManager(folder)
            try:
                self.execute(restored,'처음 제외 이유는?',branch)
                self.assertTrue(any('30만원' in e['content'] for e in seen[-1]['events']))
                self.assertTrue(any('계단' in e['content'] for e in seen[-1]['events']))
            finally:restored.pool.shutdown()

    def test_tool_arguments_and_result_are_archived_without_thinking(self):
        job={'id':'a'*32,'query':'공식 정보','created_at':'2026-10-19T00:00:00+00:00','result':{'answer':'답변'}}
        entries=[{'kind':'model_end','sequence':3,'message':{'content':'확인 중','thinking':'SECRET'}},
                 {'kind':'tool_start','sequence':4,'span':'1.1','tool_call_id':'call-x','arguments':{'query':'public'}},
                 {'kind':'tool_end','sequence':5,'span':'1.1','name':'web_search','result':{'hits':[{'url':'https://example.org'}]}}]
        with TemporaryDirectory() as folder:
            path=Path(folder)/job['id']/'traces';path.mkdir(parents=True)
            (path/'trace.jsonl').write_text('\n'.join(json.dumps(e) for e in entries),encoding='utf-8')
            originals=turn_events(folder,job)
        tool=next(e for e in originals if e['role']=='tool')
        self.assertEqual(tool['arguments'],{'query':'public'})
        self.assertEqual(tool['tool_call_id'],'call-x')
        self.assertEqual(json.loads(tool['content']),entries[-1]['result'])
        self.assertNotIn('SECRET',json.dumps(originals))

    def test_lossy_summary_is_supplemented_from_original_branch_memory(self):
        seen=[]
        def agent(store,user,session,query,**kwargs):
            seen.append(copy.deepcopy(kwargs))
            return {'status':'completed','answer':'확인했습니다.'}
        with TemporaryDirectory() as folder, patch('travel_agent.web_app.run_agent',side_effect=agent), \
             patch.dict(os.environ,{'WEB_CONTEXT_COMPACT_BYTES':'4000','WEB_CONTEXT_KEEP_TURNS':'1'}), \
             patch('travel_agent.session_context.chat',return_value={'message':{'content':'여행 후보를 검토 중이다. 상세 제외 이유는 요약에서 빠졌다.'},'done_reason':'stop'}):
            manager=RunManager(folder)
            try:
                parent=self.execute(manager,'강릉은 계단 때문에 제외했다.')
                for _ in range(3):
                    parent=self.execute(manager,'다른 이야기 '+('숙소 조건 검토 '*150),parent)
                self.execute(manager,'강릉 제외 이유 계단을 기억해?',parent)
                context=seen[-1]
                self.assertTrue(context['summary'])
                self.assertNotIn('계단 때문에',context['summary'])
                self.assertNotIn('계단 때문에',json.dumps(context['history'],ensure_ascii=False))
                self.assertIn('계단 때문에',json.dumps(context['recalled_memory'],ensure_ascii=False))
            finally:manager.pool.shutdown()
