"""Local API isolation, bounded execution and public event projection; no live model."""
from http.client import HTTPConnection
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

from travel_agent.web_app import RunManager, handler_for, visible_event


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.manager=RunManager(self.temp.name)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.manager))
        self.thread=Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.port=self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.manager.pool.shutdown(wait=True)
        self.temp.cleanup()

    def request(self,method,path,payload=None,headers=None):
        connection=HTTPConnection('127.0.0.1',self.port,timeout=3)
        data=json.dumps(payload).encode() if payload is not None else None
        default={'Content-Type':'application/json'} if data else {}
        connection.request(method,path,body=data,headers={**default,**(headers or {})})
        response=connection.getresponse()
        result=response.status,response.read(),dict(response.getheaders())
        connection.close()
        return result

    def test_static_assets_and_local_origin_boundary(self):
        status,body,headers=self.request('GET','/')
        self.assertEqual(status,200)
        self.assertIn('여행 에이전트'.encode(),body)
        self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
        self.assertEqual(self.request('GET','/api/runs',headers={'Host':'attacker.invalid'})[0],403)
        self.assertEqual(self.request('POST','/api/runs',{'query':'hi'},headers={'Origin':'https://attacker.invalid'})[0],403)
        self.assertEqual(self.request('GET','/../../pyproject.toml')[0],404)

    def test_input_is_validated_before_model_or_queue(self):
        with patch('travel_agent.web_app.run_agent') as model:
            for payload in [{'query':''},{'query':'x'*4001},{'query':'hi','enable_web':'yes'},
                            {'query':'hi','base_url':'https://attacker.invalid'}]:
                self.assertEqual(self.request('POST','/api/runs',payload)[0],400)
        model.assert_not_called()

    def test_public_tunnel_allows_only_exact_https_origin_with_local_host(self):
        origin_file=Path(self.temp.name)/'public-origin'
        origin_file.write_text('https://example.ngrok-free.app',encoding='utf-8')
        with patch.dict(os.environ,{'WEB_PUBLIC_ORIGIN_FILE':str(origin_file)}):
            self.assertEqual(self.request('GET','/api/runs',headers={'Origin':'https://example.ngrok-free.app'})[0],200)
            for origin in ['https://attacker.invalid','https://example.ngrok-free.app.attacker.invalid','http://example.ngrok-free.app']:
                self.assertEqual(self.request('GET','/api/runs',headers={'Origin':origin})[0],403)
            self.assertEqual(self.request('GET','/api/runs',headers={'Host':'example.ngrok-free.app'})[0],403)
            origin_file.unlink()
            self.assertEqual(self.request('GET','/api/runs')[0],403)

    def test_continuation_uses_server_trace_and_persisted_parent(self):
        parent_id='b'*32
        folder=Path(self.temp.name)/parent_id/'traces';folder.mkdir(parents=True)
        messages=[{'role':'system','content':'old system'},
                  {'role':'user','content':'two people, budget 250000'},
                  {'role':'assistant','tool_calls':[{'id':'old-call'}]},
                  {'role':'tool','tool_call_id':'old-call','content':'retrieved evidence'}]
        (folder/'trace.jsonl').write_text(json.dumps({'kind':'model_start','messages':messages})+'\n',encoding='utf-8')
        source={'id':'web:1234567890abcdef','url':'https://example.org','title':'fixture'}
        parent={'id':parent_id,'query':'two people, budget 250000','state':'done','created_at':'2026-10-19T01:00:00+00:00',
                'result':{'status':'completed','answer':'previous answer','web_sources':[source]}}
        self.manager._save(parent)  # Parent need not be in the recent in-memory list.
        captured={}
        def agent(*args,**kwargs):
            captured.update(kwargs)
            return {'status':'completed','answer':'continued answer'}
        with patch('travel_agent.web_app.run_agent',side_effect=agent):
            status,body,_=self.request('POST','/api/runs',{'query':'change to rain','parent_id':parent_id})
            self.assertEqual(status,202)
            run_id=json.loads(body)['id']
            self.manager.pool.shutdown(wait=True)
        self.assertEqual(captured['history'],messages[1:]+[{'role':'assistant','content':'previous answer'}])
        self.assertEqual(captured['prior_sources'],[source])
        snapshot=self.manager.snapshot(run_id)
        self.assertEqual([t['query'] for t in snapshot['conversation']],['two people, budget 250000','change to rain'])
        self.assertNotIn('retrieved evidence',json.dumps(snapshot))
        for parent_id in ['../secret','f'*32]:
            self.assertEqual(self.request('POST','/api/runs',{'query':'hi','parent_id':parent_id})[0],400)

    def test_job_reaches_real_runner_interface_and_survives_reload(self):
        ready=Event()
        def agent(store,user,session,query,**kwargs):
            ready.set()
            self.assertEqual(query,'public synthetic question')
            self.assertFalse(kwargs['enable_web'])
            self.assertEqual(store.events(user,session),[])
            return {'status':'completed','answer':'Synthetic fixture response','trace_path':'/private/path'}
        with patch('travel_agent.web_app.run_agent',side_effect=agent):
            status,body,_=self.request('POST','/api/runs',{'query':'public synthetic question','enable_web':False})
            self.assertEqual(status,202)
            run_id=json.loads(body)['id']
            self.assertTrue(ready.wait(3))
            self.manager.pool.shutdown(wait=True)
        status,body,_=self.request('GET','/api/runs/'+run_id)
        job=json.loads(body)
        self.assertEqual(status,200)
        self.assertEqual(job['state'],'done')
        self.assertNotIn('trace_path',job['result'])
        restored=RunManager(self.temp.name)
        try:
            self.assertEqual(restored.snapshot(run_id)['result']['answer'],'Synthetic fixture response')
        finally:
            restored.pool.shutdown()

    def test_budget_and_model_failures_keep_parent_context(self):
        for number, reason in enumerate(['tool_limit','step_limit','output_limit','timeout','model_error','protocol_error','context_limit']):
            with self.subTest(reason=reason):
                parent_id=f'{number+1:032x}'
                folder=Path(self.temp.name)/parent_id
                folder.mkdir()
                history=[{'role':'user','content':'Synthetic party of two'},
                         {'role':'assistant','content':'Partial known facts'}]
                (folder/'context.json').write_text(json.dumps({'history':history,'summary':'','session':parent_id}),encoding='utf-8')
                parent={'id':parent_id,'query':'Synthetic party of two','state':'done',
                        'created_at':'2026-10-19T01:00:00+00:00',
                        'result':{'status':reason,'partial_answer':'Partial known facts'}}
                self.manager._save(parent)
                with patch('travel_agent.web_app.run_agent',return_value={'status':'completed','answer':'Two people'}) as agent:
                    status,body,_=self.request('POST','/api/runs',{'query':'How many people?','parent_id':parent_id})
                    self.assertEqual(status,202)
                    run_id=json.loads(body)['id']
                    self.manager.pool.submit(lambda:None).result(timeout=3)
                self.assertEqual(agent.call_args.kwargs['history'],history)
                snapshot=self.manager.snapshot(run_id)
                self.assertEqual(snapshot['parent_id'],parent_id)
                self.assertTrue(snapshot['can_continue'])
                self.assertEqual(snapshot['conversation'][0]['answer'],'Partial known facts')
                self.assertEqual(len(snapshot['conversation']),2)

    def test_history_groups_turns_by_root_and_opens_latest_turn(self):
        root='1'*32;child='2'*32;latest='3'*32;other='4'*32
        for i,(identity,parent) in enumerate([(root,None),(child,root),(latest,child),(other,None)]):
            job={'id':identity,'query':'same title' if parent is None else 'followup',
                 'state':'done','created_at':f'2026-10-19T01:00:0{i}+00:00',
                 'result':{'status':'tool_limit','answer':'fixture'}}
            if parent:job['parent_id']=parent
            self.manager.jobs[identity]=job
            self.manager._save(job)
        status,body,_=self.request('GET','/api/runs')
        chats=json.loads(body)['runs']
        self.assertEqual(status,200)
        self.assertEqual(len(chats),2)
        grouped=next(chat for chat in chats if chat['conversation_id']==root)
        self.assertEqual((grouped['id'],grouped['query'],grouped['turn_count']),(latest,'same title',3))

    def deletion_fixture(self, identity, parent=None, state='done', cached=True):
        job={'id':identity,'query':'Synthetic deletion fixture','state':state,
             'created_at':'2026-10-19T01:00:00+00:00','result':{'status':'completed','answer':'fixture'}}
        if parent:job['parent_id']=parent
        self.manager._save(job)
        (self.manager.directory/identity/'memory.sqlite3').write_text('synthetic memory')
        logs=self.manager.directory/identity/'traces'
        logs.mkdir();(logs/'trace.jsonl').write_text('synthetic trace')
        if cached:self.manager.jobs[identity]=job
        return job

    def test_delete_removes_whole_conversation_branches_and_uncached_descendants(self):
        root='1'*32;child='2'*32;branch='3'*32;other='4'*32
        self.deletion_fixture(root)
        self.deletion_fixture(child,root)
        self.deletion_fixture(branch,root,cached=False)
        self.deletion_fixture(other)
        status,body,_=self.request('DELETE','/api/conversations/'+child)
        result=json.loads(body)
        self.assertEqual(status,200)
        self.assertEqual(set(result['deleted_ids']),{root,child,branch})
        for identity in [root,child,branch]:
            self.assertFalse((self.manager.directory/identity).exists())
            self.assertNotIn(identity,self.manager.jobs)
            self.assertEqual(self.request('GET','/api/runs/'+identity)[0],404)
        self.assertTrue((self.manager.directory/other/'memory.sqlite3').exists())
        restored=RunManager(self.temp.name)
        try:self.assertEqual([j['conversation_id'] for j in restored.summaries()],[other])
        finally:restored.pool.shutdown()

    def test_delete_rejects_active_descendant_foreign_origin_and_bad_path(self):
        root='1'*32;child='2'*32
        self.deletion_fixture(root)
        self.deletion_fixture(child,root,state='running',cached=False)
        self.assertEqual(self.request('DELETE','/api/conversations/'+root)[0],409)
        self.assertTrue((self.manager.directory/root).exists())
        self.assertEqual(self.request('DELETE','/api/conversations/'+root,headers={'Origin':'https://attacker.invalid'})[0],403)
        self.assertEqual(self.request('DELETE','/api/conversations/../secret')[0],404)
        self.assertEqual(self.request('DELETE','/api/conversations/'+'f'*32)[0],404)

    def test_delete_checks_paths_before_any_removal(self):
        root='1'*32
        self.deletion_fixture(root)
        with patch('pathlib.Path.is_symlink',return_value=True):
            self.assertEqual(self.request('DELETE','/api/conversations/'+root)[0],404)
        self.assertTrue((self.manager.directory/root/'memory.sqlite3').exists())

    def test_delete_locked_leaf_keeps_root_and_is_retryable(self):
        root='1'*32;child='2'*32
        self.deletion_fixture(root);self.deletion_fixture(child,root)
        with patch('travel_agent.web_app.shutil.rmtree',side_effect=PermissionError('locked')):
            self.assertEqual(self.request('DELETE','/api/conversations/'+root)[0],500)
        self.assertTrue((self.manager.directory/root).exists())
        self.assertTrue((self.manager.directory/child).exists())
        self.assertEqual(self.request('DELETE','/api/conversations/'+root)[0],200)

    def test_running_or_missing_context_cannot_silently_continue(self):
        for state in ['running','queued','done','interrupted','error']:
            parent={'id':'9'*32,'query':'fixture','state':state,'created_at':'test',
                    'result':{'status':'tool_limit'}}
            self.manager.jobs[parent['id']]=parent
            self.assertFalse(self.manager.snapshot(parent['id'])['can_continue'])
            self.assertEqual(self.request('POST','/api/runs',{'query':'next','parent_id':parent['id']})[0],400)

    def test_three_slots_are_bounded_and_inference_is_serial(self):
        release=Event();started=Event();ids=[]
        def agent(*args,**kwargs):
            started.set()
            release.wait(3)
            return {'status':'completed','answer':'fixture'}
        with patch('travel_agent.web_app.run_agent',side_effect=agent):
            try:
                ids.append(self.manager.submit('one',True))
                self.assertTrue(started.wait(3))
                ids.append(self.manager.submit('two',True))
                ids.append(self.manager.submit('three',True))
                with self.assertRaises(RuntimeError):self.manager.submit('four',True)
                self.assertEqual([j['state'] for j in self.manager.jobs.values()].count('running'),1)
            finally:
                release.set()
                self.manager.pool.shutdown(wait=True)

    def test_trace_projection_hides_model_inputs_and_thinking(self):
        event={'sequence':1,'timestamp':'test','kind':'model_start','messages':['private prompt'],'input_bytes':12}
        self.assertNotIn('messages',visible_event(event))
        event.update(kind='model_end',message={'content':'Public output','thinking':'hidden'})
        self.assertNotIn('hidden',json.dumps(visible_event(event)))
        self.assertEqual(visible_event(event)['content'],'Public output')

    def test_poll_cursor_ignores_incomplete_trace_lines(self):
        run_id='a'*32
        self.manager.jobs[run_id]={'id':run_id,'state':'running','created_at':'test','query':'fixture'}
        folder=Path(self.temp.name)/run_id/'traces';folder.mkdir(parents=True)
        event={'sequence':2,'timestamp':'test','kind':'tool_start','name':'web_search','arguments':{'query':'fixture'}}
        (folder/'trace.jsonl').write_text(json.dumps(event)+'\n{"sequence":',encoding='utf-8')
        data=self.manager.snapshot(run_id,1)
        self.assertEqual(len(data['events']),1)
        self.assertEqual(data['next_sequence'],2)
        self.assertEqual(self.manager.snapshot(run_id,2)['events'],[])
