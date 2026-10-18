"""Scope, network boundaries, extraction fidelity and actual model serialization."""
from email.message import Message
from io import BytesIO
import tempfile
import unittest
from unittest.mock import patch

from travel_agent.agent import execute_tool, validate_call
from travel_agent.memory import canonical
from travel_agent.memory import MemoryStore
from travel_agent.agent import run_agent
from travel_agent.web import WebSearchError
from travel_agent.web_context import format_web_result
from travel_agent.web_read import fetch_public_page, select_excerpt, web_read, extract_page

SOURCE = {'id':'web:0123456789abcdef', 'title':'Synthetic museum', 'url':'https://example.invalid/info'}
BODY = ('<html><head><title>Synthetic museum</title></head><body><nav>BUY NOW</nav><main><h1>Visitor information</h1>'
        '<p>Opening hours: 09:00 to 18:00. The museum is closed on Monday.</p>'
        '<p>Take bus 11 from the station. The indoor exhibition is free to enter.</p>'
        '<p>These are synthetic test facts, not a real venue.</p></main></body></html>').encode()


class ReadingTests(unittest.TestCase):
    def test_read_without_prior_search_never_counts_as_search_attempt(self):
        read_call={'function':{'name':'web_read','arguments':{'source_id':SOURCE['id'],'query':'hours'}}}
        replies=[{'message':{'role':'assistant','content':'','tool_calls':[read_call]}},
                 {'message':{'role':'assistant','content':'출처를 먼저 검색해야 합니다.'}}]
        with tempfile.TemporaryDirectory() as folder, MemoryStore(folder+'/db.sqlite3') as store:
            with patch('travel_agent.agent.chat',side_effect=replies), patch('travel_agent.agent.web_read') as reader:
                result=run_agent(store,'u','s','read',trace_dir=folder+'/trace',completion_protocol='legacy')
        reader.assert_not_called()
        self.assertFalse(result['web_search_attempted'])
        self.assertEqual(result['web_sources'],[])

    def test_completed_loop_with_missing_citations_fails_quality_gate(self):
        from scripts.evaluate_travel_search import quality_gate
        result={'status':'completed','citation_ids_valid':False,'web_sources':[{'page_fetched':True}]}
        self.assertFalse(quality_gate(result)['automatic_pass'])
        result['citation_ids_valid']=True
        self.assertTrue(quality_gate(result)['automatic_pass'])
        self.assertTrue(quality_gate(result)['manual_fact_review_required'])

    def test_bare_source_id_is_normalized_but_still_requires_scope(self):
        name,args=validate_call({'function':{'name':'web_read','arguments':{'source_id':'0123456789abcdef','query':'hours'}}})
        self.assertEqual(args['source_id'],SOURCE['id'])
        with patch('travel_agent.agent.web_read') as read, self.assertRaises(ValueError):
            execute_tool(None,'u','s',name,args,mode='hybrid',rerank=False,allowed_sources={})
        read.assert_not_called()

    def test_agent_passes_prior_source_and_records_excerpt_provenance(self):
        search_call={'id':'search-id','function':{'name':'web_search','arguments':{'query':'museum'}}}
        read_call={'id':'read-id','function':{'name':'web_read','arguments':{'source_id':SOURCE['id'],'query':'hours'}}}
        replies=[{'message':{'role':'assistant','content':'','tool_calls':[search_call]}},
                 {'message':{'role':'assistant','content':'','tool_calls':[read_call]}},
                 {'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'web_search','arguments':{'query':'museum transport'}}}]}},
                 {'message':{'role':'assistant','content':'Monday closed ['+SOURCE['id']+']'}}]
        evidence={'hits':[{**SOURCE,'snippet':'Museum'}], 'searched_at':'test','content_kind':'search_snippet',
                  'page_fetched':False,'status':'ok','search_complete':True,'engines_returned':['bing']}
        read={'id':SOURCE['id'],'title':SOURCE['title'],'url':SOURCE['url'],'text':'Monday closed',
              'truncated':False,'page_fetched':True,'verified_current':False,'selection_query':'hours',
              'content_kind':'page_excerpt','fetched_at':'test'}
        with tempfile.TemporaryDirectory() as folder, MemoryStore(folder+'/db.sqlite3') as store:
            with patch('travel_agent.agent.chat',side_effect=replies), patch('travel_agent.agent.web_search',return_value=evidence), patch('travel_agent.agent.web_read',return_value=read) as reader:
                result=run_agent(store,'u','s','museum hours',trace_dir=folder+'/trace',web_tool_format='compact_md',completion_protocol='legacy')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(reader.call_args.args[0]['url'],SOURCE['url'])
        self.assertTrue(result['web_sources'][0]['page_fetched'])
        self.assertEqual(result['web_sources'][0]['content_kind'],'page_excerpt')

    def test_read_requires_a_source_from_this_request(self):
        with patch('travel_agent.agent.web_read') as read:
            with self.assertRaises(ValueError):
                execute_tool(None,'u','s','web_read',{'source_id':SOURCE['id'],'query':'hours'},mode='hybrid',rerank=False)
        read.assert_not_called()

    def test_model_cannot_supply_arbitrary_url(self):
        with self.assertRaises(ValueError):
            validate_call({'function':{'name':'web_read','arguments':{'url':'http://127.0.0.1','query':'x'}}})

    def test_private_or_mixed_dns_addresses_never_connect(self):
        for ips in (['127.0.0.1'], ['10.0.0.1'], ['::1'], ['93.184.216.34','192.168.1.1']):
            addresses = [(2,1,6,'',(ip,443)) for ip in ips]
            with patch('travel_agent.web_read.socket.getaddrinfo',return_value=addresses), patch('travel_agent.web_read.HTTPSConnection') as connection:
                with self.assertRaises(WebSearchError) as caught:
                    fetch_public_page(SOURCE['url'])
            self.assertEqual(caught.exception.details['reason'], 'unsafe_address')
            connection.assert_not_called()

    def test_connection_uses_resolved_ip_and_original_tls_hostname(self):
        headers = Message(); headers['Content-Type'] = 'text/html'
        with patch('travel_agent.web_read.socket.getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))]), patch('travel_agent.web_read.HTTPSConnection') as factory, patch('travel_agent.web_read.socket.create_connection') as connect:
            response = factory.return_value.getresponse.return_value
            response.status=200; response.headers=headers; response.read.return_value=BODY
            response.getheader.return_value='identity'
            body, info = fetch_public_page(SOURCE['url'])
            factory.return_value._create_connection(('example.invalid',443), 7)
        factory.assert_called_once_with('example.invalid',443,timeout=12)
        connect.assert_called_once_with(('93.184.216.34',443),7,None)
        self.assertEqual(body, BODY)

    def test_redirect_is_not_followed(self):
        with patch('travel_agent.web_read.socket.getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))]), patch('travel_agent.web_read.HTTPSConnection') as factory:
            factory.return_value.getresponse.return_value.status=302
            with self.assertRaises(WebSearchError):
                fetch_public_page(SOURCE['url'])
        self.assertEqual(factory.return_value.request.call_count,1)

    def test_extraction_retains_needed_facts_and_stays_in_budget(self):
        with patch('travel_agent.web_read.fetch_public_page',return_value=(BODY,{'http_status':200,'method':'GET'})):
            result=web_read(SOURCE,'Opening hours Monday bus',max_bytes=1400)
        self.assertTrue(result['page_fetched'])
        self.assertFalse(result['verified_current'])
        self.assertIn('Monday',result['text'])
        self.assertLessEqual(len(canonical(result).encode()),1400)
        self.assertNotIn('<html>',result['text'])

    def test_focused_selection_can_retain_late_facts(self):
        text='\n\n'.join(['Unrelated text '+str(i) for i in range(20)]+['Monday closed. bus 11.'])
        selected, indices, total = select_excerpt(text,'Monday bus',100)
        self.assertIn('Monday closed',selected)
        self.assertTrue(indices)
        self.assertTrue(all(0 <= index < total for index in indices))
        self.assertLessEqual(len(selected.encode()),100)

    def test_empty_extraction_is_not_page_success(self):
        with patch('travel_agent.web_read.extract',return_value=None), self.assertRaises(WebSearchError):
            extract_page(b'<html></html>',SOURCE['url'])

    def test_compact_serialization_preserves_source_uncertainty_and_failures(self):
        result={'status':'ok','content_kind':'search_snippet','page_fetched':False,'search_complete':False,
                'engines_returned':['bing'],'engine_status':{'bing':{'status':'error','http_status':429}},
                'hits':[{**SOURCE,'snippet':'Only a snippet','snippet_truncated':True}], 'omitted_results':2}
        content=format_web_result(result,'compact_md')
        for value in (SOURCE['id'],SOURCE['url'],'429','false','omitted_results', 'snippet truncated'):
            self.assertIn(value,content)
        self.assertEqual(result['hits'][0]['snippet'],'Only a snippet')
