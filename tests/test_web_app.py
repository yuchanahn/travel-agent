"""Local API isolation, bounded execution and public event projection; no live model."""
from http.client import HTTPConnection
import json
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
