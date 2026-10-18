"""Real MCP SDK transports, dynamic schemas and harness/memory integration."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from travel_agent.agent import run_agent, validate_call
from travel_agent.mcp_client import MCPRegistry, load_servers, model_result
from travel_agent.memory import MemoryStore
from travel_agent.session_context import turn_events

FIXTURE=Path(__file__).parent/'fixtures/mcp_protocol_server.py'


def server_config(transport='stdio',**extra):
    return {'id':'fixture','transport':transport,'command':sys.executable,
            'args':[str(FIXTURE.resolve())],'allowed_tools':['lookup_place','fail_lookup'],**extra}


class MCPClientTests(unittest.TestCase):
    def test_stdio_discovery_schema_validation_call_and_server_error(self):
        with MCPRegistry([server_config()]) as registry:
            self.assertEqual(registry.status[0]['status'],'connected',registry.status)
            self.assertEqual(len(registry.tools),2)
            with self.assertRaises(ValueError):validate_call({'function':{'name':'mcp_fixture_lookup_place','arguments':{'name':1}}},registry)
            result=registry.call('mcp_fixture_lookup_place',{'name':'합성 장소'})
            self.assertTrue(result['raw_result']['structuredContent']['synthetic'])
            self.assertIn('가상 계단',result['text'])
            error=registry.call('mcp_fixture_fail_lookup',{'name':'fixture'})
            self.assertTrue(error['is_error'])
            self.assertIn('error',error)

    def test_http_transport_is_not_a_fake_http_tool_wrapper(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        process=subprocess.Popen([sys.executable,str(FIXTURE),'--port',str(port)],stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,creationflags=creationflags)
        try:
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                with socket.socket() as sock:
                    if sock.connect_ex(('127.0.0.1',port))==0:break
                if process.poll() is not None:self.fail('MCP fixture exited')
                time.sleep(.05)
            with MCPRegistry([server_config('streamable_http',url=f'http://127.0.0.1:{port}/mcp')]) as registry:
                self.assertEqual(registry.status[0]['status'],'connected',registry.status)
                self.assertIn('가상 계단',registry.call('mcp_fixture_lookup_place',{'name':'합성 장소'})['text'])
        finally:
            process.terminate();process.wait(timeout=5)

    def test_dynamic_tools_result_citation_trace_and_memory(self):
        requests=[]
        def model(messages,**kwargs):
            requests.append(copy.deepcopy(messages))
            if len(requests)==1:
                self.assertIn('mcp_fixture_lookup_place',[t['function']['name'] for t in kwargs['tools']])
                return {'message':{'role':'assistant','content':'','tool_calls':[
                    {'id':'mcp-call-1','function':{'name':'mcp_fixture_lookup_place','arguments':{'name':'합성 장소'}}}]}}
            result=json.loads(messages[-1]['content'])
            return {'message':{'role':'assistant','content':'합성 결과입니다. ['+result['id']+']'}}
        with TemporaryDirectory() as folder, MemoryStore(Path(folder)/'db') as store, MCPRegistry([server_config()]) as registry:
            run_id='a'*32
            traces=Path(folder)/run_id/'traces'
            with patch('travel_agent.agent.chat',side_effect=model):
                result=run_agent(store,'public','fixture','synthetic query',trace_dir=traces,mcp_registry=registry)
            self.assertEqual((result['status'],result['tool_calls']),('completed',1))
            self.assertTrue(result['citation_ids_valid'])
            self.assertEqual(result['mcp_sources'][0]['server'],'fixture')
            archived=turn_events(folder,{'id':run_id,'query':'synthetic query',
                'created_at':'2026-10-19T00:00:00+00:00','result':result})
            tool=next(e for e in archived if e['role']=='tool')
            self.assertEqual(tool['tool_call_id'],'mcp-call-1')
            self.assertEqual(tool['arguments'],{'name':'합성 장소'})
            self.assertIn('raw_result',json.loads(tool['content']))
            self.assertEqual(requests[-1][-1]['tool_call_id'],'mcp-call-1')

    def test_no_discovered_schema_means_no_exposed_tool(self):
        config=server_config(allowed_tools=['not_present'])
        with MCPRegistry([config]) as registry:
            self.assertEqual(registry.tools,[])
            self.assertEqual(registry.status[0]['status'],'unavailable')

    def test_timeout_does_not_become_a_success(self):
        with MCPRegistry([server_config()]) as registry:
            async def timeout(*args):raise TimeoutError('secret-url')
            with patch.object(registry,'_call',side_effect=timeout):
                with self.assertRaisesRegex(RuntimeError,'MCP call failed: TimeoutError') as error:
                    registry.call('mcp_fixture_lookup_place',{'name':'fixture'})
            self.assertNotIn('secret-url',str(error.exception))

    def test_packet_is_bounded_without_truncating_private_raw_result(self):
        result={'id':'mcp:1234567890abcdef','text':'긴 합성 문장입니다. '*2000,'raw_result':{'long':'x'*20000}}
        packet=model_result(result,max_bytes=1200)
        self.assertLessEqual(len(packet.encode()),1200)
        self.assertTrue(json.loads(packet)['truncated'])
        self.assertEqual(len(result['raw_result']['long']),20000)
        metadata=model_result({'remote_tool':'x'*2000,'text':'x'},max_bytes=1200)
        self.assertLessEqual(len(metadata.encode()),1200)
        self.assertIn('error',json.loads(metadata))

    def test_config_credentials_are_file_backed_and_not_in_model_schema(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)
            (path/'key').write_text('SYNTHETIC_SECRET_12345',encoding='utf-8')
            config=server_config(env_files={'FIXTURE_KEY':'key'})
            (path/'mcp.json').write_text(json.dumps({'servers':[config]}),encoding='utf-8')
            resolved=load_servers(path/'mcp.json')
            self.assertEqual(resolved[0]['_env']['FIXTURE_KEY'],'SYNTHETIC_SECRET_12345')
            with MCPRegistry(resolved) as registry:
                self.assertNotIn('SYNTHETIC_SECRET',json.dumps(registry.tools))
            config['allowed_tools']=[]
            (path/'mcp.json').write_text(json.dumps({'servers':[config]}),encoding='utf-8')
            with self.assertRaises(ValueError):load_servers(path/'mcp.json')
            with self.assertRaises(ValueError):load_servers(path/'absent.json')

    def test_parallel_mcp_calls_preserve_request_order_and_call_ids(self):
        count=0
        def model(messages,**kwargs):
            nonlocal count
            count+=1
            if count==1:
                return {'message':{'role':'assistant','content':'','tool_calls':[
                    {'id':str(i),'function':{'name':'mcp_fixture_lookup_place','arguments':{'name':str(i)}}} for i in range(2)]}}
            self.assertEqual([m['tool_call_id'] for m in messages if m['role']=='tool'],['0','1'])
            return {'message':{'role':'assistant','content':'합성 조회 완료'}}
        with TemporaryDirectory() as folder, MemoryStore(Path(folder)/'db') as store, MCPRegistry([server_config()]) as registry, \
             patch('travel_agent.agent.chat',side_effect=model):
            result=run_agent(store,'public','fixture','synthetic parallel query',trace_dir=Path(folder)/'trace',mcp_registry=registry)
        self.assertEqual(result['tool_calls'],2)
        self.assertEqual(len(result['mcp_sources']),2)

    def test_returned_credentials_are_redacted_before_trace_or_model_packet(self):
        from mcp.types import CallToolResult,TextContent
        secret='SYNTHETIC_SECRET/12345'
        config=server_config(_headers={'x-key':secret})
        async def result(*args):
            return CallToolResult(content=[TextContent(type='text',text=secret+' SYNTHETIC_SECRET%2F12345')])
        with MCPRegistry([config]) as registry, patch.object(registry,'_call',side_effect=result):
            response=registry.call('mcp_fixture_lookup_place',{'name':'fixture'})
        self.assertNotIn(secret,json.dumps(response))
        self.assertNotIn('SYNTHETIC_SECRET%2F12345',json.dumps(response))
        self.assertIn('[REDACTED]',response['text'])

    def test_external_schema_references_are_not_resolved_over_network(self):
        from travel_agent.mcp_client import _check_schema
        with self.assertRaises(ValueError):_check_schema({'$ref':'https://example.org/schema'})
        _check_schema({'type':'object','properties':{'x':{'$ref':'#/$defs/X'}},'$defs':{'X':{'type':'string'}}})
