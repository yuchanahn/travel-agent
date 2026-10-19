import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from travel_agent.agent import run_agent, readable_tools, TOOLS
from travel_agent.brave_mcp import pack_result
from travel_agent.mcp_client import MCPRegistry, model_result
from travel_agent.memory import MemoryStore


def result(items):
    return {'id':'mcp:1234567890abcdef','model_adapter':'brave_search',
        'raw_result': {'content': [{'type':'text','text':json.dumps(item,ensure_ascii=False)} for item in items]}}


class BraveMCPTests(unittest.TestCase):
    def test_read_schema_excludes_completed_pages_without_mutating_shared_tools(self):
        self.assertNotIn('web_read',[t['function']['name'] for t in readable_tools(TOOLS,{},set())])
        tools=readable_tools(TOOLS,{'web:1111111111111111':{},'web:2222222222222222':{}},{'web:1111111111111111'})
        read=next(t for t in tools if t['function']['name']=='web_read')
        self.assertEqual(read['function']['parameters']['properties']['source_id']['enum'],['web:2222222222222222'])
        original=next(t for t in TOOLS if t['function']['name']=='web_read')
        self.assertNotIn('enum',original['function']['parameters']['properties']['source_id'])
    def test_twenty_rich_results_fit_expanded_budget_without_losing_extras(self):
        raw=result([{'title':str(i),'url':f'https://example.com/{i}',
                     'extra_snippets':['검증 문장. '*180]} for i in range(20)])
        previous=json.loads(model_result(raw,max_bytes=48000))
        expanded=json.loads(model_result(raw))
        self.assertLess(previous['returned_results'],20)
        self.assertEqual(expanded['returned_results'],20)
        self.assertEqual(expanded['omitted_results'],0)
        self.assertEqual(expanded['hits'][-1]['extra_snippets'],['검증 문장. '*180])
        self.assertLessEqual(len(model_result(raw).encode()),96000)

    def test_complete_records_and_extra_snippets_survive_default_packet(self):
        sentence='문장 전체를 보존합니다. '*500
        raw=result([{'title':'안내','url':'https://example.com/visit','description':'요약','extra_snippets':[sentence]}])
        packet=json.loads(model_result(raw))
        self.assertEqual(packet['hits'][0]['extra_snippets'],[sentence])
        self.assertFalse(packet['truncated'])
        small=json.loads(model_result(raw,max_bytes=1000))
        self.assertEqual(small['hits'],[])
        self.assertEqual(small['omitted_results'],1)
        self.assertLessEqual(len(model_result(raw,max_bytes=1000).encode()),1000)

    def test_oversized_record_does_not_hide_following_small_record_or_split_text(self):
        raw=result([{'title':'huge','url':'https://example.com/huge','extra_snippets':['x'*10000]},
                    {'title':'small','url':'https://example.com/small','extra_snippets':['Whole sentence.']}])
        packet=json.loads(pack_result(raw,max_bytes=1200))
        self.assertEqual([h['title'] for h in packet['hits']],['small'])
        self.assertEqual(packet['omitted_results'],1)
        bad=result([{'title':'bad','url':'https://example.com/','extra_snippets':'not a list'}])
        self.assertEqual(json.loads(pack_result(bad))['hits'][0]['extra_snippets'],[])

    def test_real_mcp_roundtrip_registers_only_delivered_sources_for_reading(self):
        config={'id':'brave','transport':'stdio','adapter':'brave_search','command':sys.executable,
            'args':[str(Path(__file__).parent/'fixtures/mcp_protocol_server.py')],
            'allowed_tools':['brave_web_search']}
        calls=[]
        def model(messages,**kw):
            calls.append(messages)
            names=[t['function']['name'] for t in kw['tools']]
            self.assertNotIn('web_search',names)
            if len(calls)==1:
                return {'message':{'role':'assistant','content':'','tool_calls':[
                    {'id':'search','function':{'name':'mcp_brave_brave_web_search','arguments':{'query':'합성'}}}]}}
            if len(calls)==2:
                packet=json.loads(messages[-1]['content'])
                self.assertIn('완전한 문장',packet['hits'][0]['extra_snippets'][0])
                return {'message':{'role':'assistant','content':'','tool_calls':[
                    {'id':'read','function':{'name':'web_read','arguments':{'source_id':packet['hits'][0]['id'],'query':'안내'}}}]}}
            self.assertNotIn('web_read',names)
            return {'message':{'role':'assistant','content':'조회 완료'}}
        def read(source,query,**kw):
            self.assertEqual(source['url'],'https://example.com/visit')
            self.assertEqual(kw['max_bytes'],12000)
            return {**source,'text':'합성 본문','truncated':False,'page_fetched':True,'content_kind':'page_excerpt'}
        with TemporaryDirectory() as folder, MemoryStore(Path(folder)/'db') as store, MCPRegistry([config]) as registry:
            with patch('travel_agent.agent.chat',side_effect=model),patch('travel_agent.agent.web_read',side_effect=read):
                answer=run_agent(store,'u','s','합성 질문',mcp_registry=registry,trace_dir=Path(folder)/'trace')
            self.assertEqual(answer['tool_calls'],2)
            self.assertTrue(answer['web_search_attempted'])
            self.assertTrue(answer['web_search_performed'])
            self.assertTrue(answer['web_sources'][0]['page_fetched'])
            calls.clear()
            def offline(messages,**kw):
                self.assertNotIn('mcp_brave_brave_web_search',[t['function']['name'] for t in kw['tools']])
                return {'message':{'role':'assistant','content':'웹 비활성'}}
            with patch('travel_agent.agent.chat',side_effect=offline):
                run_agent(store,'u','s','합성',enable_web=False,mcp_registry=registry,trace_dir=Path(folder)/'offline')

    def test_failed_config_does_not_offer_native_search_as_silent_fallback(self):
        class Failed:
            servers=[{'adapter':'brave_search'}]
            adapters={}
            routes={}
            tools=[]
            status=[{'server':'brave','status':'unavailable'}]
        def model(messages,**kw):
            self.assertNotIn('web_search',[t['function']['name'] for t in kw['tools']])
            return {'message':{'role':'assistant','content':'검색 연결 실패'}}
        with TemporaryDirectory() as folder,MemoryStore(Path(folder)/'db') as store,patch('travel_agent.agent.chat',side_effect=model):
            run_agent(store,'u','s','합성',mcp_registry=Failed(),trace_dir=Path(folder)/'trace')
