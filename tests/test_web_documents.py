import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import sys

from travel_agent.web_documents import DocumentCollection, page_links, source_id
from travel_agent.web import WebSearchError
from travel_agent.agent import run_agent
from travel_agent.memory import MemoryStore
from travel_agent.mcp_client import MCPRegistry


def page(title, text, links='', description='Actual page description'):
    return f'<html><head><meta charset="utf-8"><title>{title}</title><meta name="description" content="{description}"></head><body><article><h1>{title}</h1><p>{text}</p></article>{links}</body></html>'.encode()


class DocumentTests(unittest.TestCase):
    def test_html_parse_failure_preserves_http_observation_and_raw_body(self):
        with TemporaryDirectory() as folder:
            c=DocumentCollection(folder,fetcher=lambda url,timeout:(b'',{'http_status':200}))
            d=c.collect([{'url':'https://example.com/'}])['documents'][0]
            self.assertEqual(d['status'],'failed')
            self.assertTrue(d['page_fetched'])
            self.assertEqual(d['http_status'],200)
            self.assertEqual(len(list(Path(folder).glob('*.html'))),1)
            self.assertTrue(c.read(d['id'])['is_error'])

    def test_real_mcp_search_catalogue_then_model_selected_neighbor_reads_without_network(self):
        config={'id':'brave','transport':'stdio','adapter':'brave_search','command':sys.executable,
            'args':[str(Path(__file__).parent/'fixtures/mcp_protocol_server.py')], 'allowed_tools':['brave_web_search']}
        fetched=[];model_calls=[]
        def fetch(url,timeout):
            fetched.append(url)
            return page('Actual pool page' if url.endswith('/pool') else 'Root','body',
                        '<a href="/pool">수영장 안내</a>'),{'http_status':200}
        def model(messages,**kw):
            model_calls.append(messages)
            if len(model_calls)==1:
                return {'message':{'role':'assistant','content':'','tool_calls':[{'id':'s','function':{'name':'mcp_brave_brave_web_search','arguments':{'query':'수영장'}}}]}}
            if len(model_calls)==2:
                packet=json.loads(messages[-1]['content'])
                doc=next(d for d in packet['document_catalog'] if d['url'].endswith('/pool'))
                self.assertNotIn('Stored pool body',messages[-1]['content'])
                self.assertEqual(doc['anchors'],['수영장 안내'])
                return {'message':{'role':'assistant','content':'','tool_calls':[{'id':'r','function':{'name':'web_read','arguments':{'source_id':doc['id'],'query':'수영장 안내'}}}]}}
            self.assertIn('Stored pool body',messages[-1]['content'])
            self.assertEqual(len(fetched),2)
            return {'message':{'role':'assistant','content':'저장 본문을 확인했습니다.'}}
        with TemporaryDirectory() as folder,MemoryStore(Path(folder)/'db') as store,MCPRegistry([config]) as registry:
            c=DocumentCollection(Path(folder)/'documents',fetcher=fetch)
            with patch('travel_agent.web_documents.extract_page',side_effect=lambda body,url:'Stored pool body' if url.endswith('/pool') else 'Root body'),patch('travel_agent.agent.chat',side_effect=model):
                result=run_agent(store,'u','s','합성 시설 확인',mcp_registry=registry,document_collection=c,trace_dir=Path(folder)/'traces')
            self.assertEqual(result['status'],'completed')
            self.assertEqual(result['tool_calls'],2)
            self.assertTrue(next(d for d in result['web_sources'] if d['url'].endswith('/pool'))['body_delivered'])

    def test_link_identity_filters_deduplicates_and_resolves_without_following_base(self):
        body=page('Root','Readable text', '<base href="https://elsewhere.test/"><a href="/pool#one">Pool</a><a href="/pool#two">Again</a><a href="javascript:alert(1)">bad</a><a href="mailto:x@example.com">mail</a><a href="/pic.jpg">image</a><a href="https://other.test/">Other</a>')
        title,description,links=page_links(body,'https://example.com/')
        self.assertEqual(title,'Root')
        self.assertEqual(description,'Actual page description')
        self.assertEqual([l['url'] for l in links],['https://example.com/pool','https://other.test/'])

    def test_one_hop_cache_catalog_identity_and_exact_read_after_reopen(self):
        calls=[]
        pages={'https://example.com/':page('Root','Root body', '<a href="/pool">수영장</a><a href="/bbq">바비큐</a><a href="https://other.test/">Outside</a>'),
               'https://example.com/pool':page('Pool','Pool facility evidence.', '<a href="/deep">Must not fetch depth two</a>'),
               'https://example.com/bbq':page('BBQ','Private BBQ evidence.')}
        def fetch(url,timeout):
            calls.append(url)
            return pages[url],{'http_status':200}
        with TemporaryDirectory() as folder,patch('travel_agent.web_documents.extract_page',side_effect=lambda body,url: ' Exact whitespace\n  '+url+'\n'):
            c=DocumentCollection(folder,neighbors=2,fetcher=fetch)
            catalog=c.collect([{'url':'https://example.com/','title':'Search title'}],query='수영장 바비큐')
            self.assertEqual(set(calls),set(pages))
            self.assertEqual(catalog['outside_host_links'],1)
            self.assertEqual(len(catalog['documents']),3)
            self.assertNotIn('text',json.dumps(catalog))
            pool=next(d for d in catalog['documents'] if d['title']=='Pool')
            self.assertEqual(pool['parents'],[source_id('https://example.com/')])
            before=len(calls)
            c.collect([{'url':'https://example.com/'}])
            restored=DocumentCollection(folder,fetcher=fetch)
            answer=restored.read(pool['id'])
            self.assertEqual(answer['text'],' Exact whitespace\n  https://example.com/pool\n')
            self.assertFalse(answer['truncated'])
            self.assertEqual(len(calls),before)
            self.assertTrue(list(Path(folder).glob('*.html')))

    def test_failures_empty_body_limits_and_content_dedup_remain_explicit(self):
        calls=[]
        def fetch(url,timeout):
            calls.append(url)
            if 'fail' in url:raise WebSearchError('blocked',details={'http_status':403})
            return page('Same','identical text','<a href="/fail">Failure</a><a href="/duplicate">Duplicate</a><a href="/omitted">Overflow</a>'),{'http_status':200}
        with TemporaryDirectory() as folder,patch('travel_agent.web_documents.extract_page',return_value='identical extracted text'):
            c=DocumentCollection(folder,roots=1,neighbors=3,max_documents=3,fetcher=fetch)
            result=c.collect([{'url':'https://example.com/'}])
            self.assertEqual(len(calls),3)
            self.assertEqual(result['skipped_document_budget'],1)
            fail=next(d for d in result['documents'] if d['status']=='failed')
            self.assertIn('error',c.read(fail['id']))
            self.assertEqual(next(d for d in result['documents'] if d['title']=='Same' and d['parents'])['same_content_as'],source_id('https://example.com/'))
        with TemporaryDirectory() as folder,patch('travel_agent.web_documents.extract_page',side_effect=WebSearchError('empty')):
            c=DocumentCollection(folder,neighbors=0,fetcher=fetch)
            self.assertEqual(c.collect([{'url':'https://example.com/'}])['documents'][0]['status'],'empty')

    def test_pagination_reassembles_exact_text_and_wrong_token_is_rejected(self):
        text=('공백  보존\n"quoted" \\ escaped\n'*700)
        with TemporaryDirectory() as folder,patch('travel_agent.web_documents.extract_page',return_value=text):
            c=DocumentCollection(folder,neighbors=0,fetcher=lambda url,timeout:(page('Doc','text'),{'http_status':200}))
            sid=c.collect([{'url':'https://example.com/'}])['documents'][0]['id']
            offset=0;out='';token=None
            while True:
                r=c.read(sid,start_index=offset,document_token=token,max_bytes=1500)
                self.assertLessEqual(len(json.dumps(r,ensure_ascii=False,separators=(',',':')).encode()),1500)
                out+=r['text']
                if not r['truncated']:break
                self.assertGreater(r['next_start_index'],offset)
                offset=r['next_start_index'];token=r['document_token']
            self.assertEqual(out,text)
            with self.assertRaises(ValueError):c.read(sid,document_token='wrong')
            with self.assertRaises(ValueError):c.read('../anything')

    def test_deadline_storage_budget_and_related_link_selection(self):
        body=page('Root','body','<a href="/about">소개</a><a href="/pool">수영장</a>')
        with TemporaryDirectory() as folder,patch('travel_agent.web_documents.extract_page',return_value='body'):
            c=DocumentCollection(folder,neighbors=1,fetcher=lambda url,timeout:(body,{'http_status':200}))
            docs=c.collect([{'url':'https://example.com/'}],query='수영장')['documents']
            self.assertTrue(any(d['url'].endswith('/pool') for d in docs))
        with TemporaryDirectory() as folder:
            c=DocumentCollection(folder,fetcher=lambda *a,**k:self.fail('deadline must prevent network'))
            self.assertEqual(c.collect([{'url':'https://example.com/'}],timeout=0)['documents'][0]['status'],'not_fetched')
        with TemporaryDirectory() as folder,patch('travel_agent.web_documents.extract_page',return_value='x'*2000):
            c=DocumentCollection(folder,max_bytes=1024,fetcher=lambda url,timeout:(body,{'http_status':200}))
            self.assertEqual(c.collect([{'url':'https://example.com/'}])['documents'][0]['error'],'storage_budget')
