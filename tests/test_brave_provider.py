"""Synthetic credentials and API fixtures only; tests must not access the network."""
from io import BytesIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from travel_agent.brave_provider import api_key, request_search
from travel_agent.web import WebSearchError, web_search, _EngineRows
from travel_agent.web_pipeline import search_evidence


class Response(BytesIO):
    status = 200


class BraveTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'BRAVE_API_KEY':'synthetic-test-credential'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_default_provider_preserves_sources_and_output_contract(self):
        rows=[{'title':'Travel','href':'https://example.org/travel','body':'Travel snippet'}]
        with patch('travel_agent.brave_provider.search',return_value=(rows,{})) as brave, \
                patch('travel_agent.web._provider_search') as bing:
            result=web_search('travel')
        brave.assert_called_once_with('travel',3,15)
        bing.assert_not_called()
        self.assertEqual(result['provider'],'brave')
        self.assertEqual(result['backend_requested'],'brave')
        self.assertTrue(result['hits'][0]['id'].startswith('web:'))
        self.assertFalse(result['page_fetched'])

    def test_key_file_and_environment_precedence(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'key'
            path.write_text('synthetic-file-value\n',encoding='utf-8')
            with patch.dict(os.environ,{'BRAVE_API_KEY_FILE':str(path)}):
                self.assertEqual(api_key(),'synthetic-test-credential')
                with patch.dict(os.environ,{'BRAVE_API_KEY':''}):
                    self.assertEqual(api_key(),'synthetic-file-value')

    def test_missing_key_fails_before_network(self):
        with patch.dict(os.environ,{'BRAVE_API_KEY':'','BRAVE_API_KEY_FILE':'does-not-exist'}), \
                patch('travel_agent.brave_provider.build_opener') as opener:
            with self.assertRaises(WebSearchError) as caught:
                request_search('travel',3,12)
        self.assertEqual(caught.exception.details['reason'],'missing_credentials')
        opener.assert_not_called()

    def test_unicode_query_pagination_and_secret_not_in_diagnostics(self):
        payload={'query':{'more_results_available':True},'web':{'results':[
            {'title':'Travel','url':'https://example.org/a','description':'Content'},
            {'title':'Unsafe','url':'javascript:bad()'}]}}
        with patch('travel_agent.brave_provider.build_opener') as opener:
            opener.return_value.open.return_value=Response(json.dumps(payload).encode())
            raw,rows,info=request_search('강릉 여행',20,12,offset=1)
        request=opener.return_value.open.call_args.args[0]
        params=parse_qs(urlsplit(request.full_url).query)
        self.assertEqual(params['q'],['강릉 여행'])
        self.assertEqual(params['offset'],['1'])
        self.assertEqual(params['country'],['KR'])
        self.assertEqual(len(rows),1)
        self.assertNotIn('synthetic-test-credential',json.dumps([raw,rows,info]))

    def test_auth_and_rate_errors_are_not_retried_or_fallen_back(self):
        for status in (401,429):
            with self.subTest(status=status), patch('travel_agent.brave_provider.build_opener') as opener, \
                    patch('travel_agent.web._provider_search') as bing:
                opener.return_value.open.side_effect=HTTPError('https://api.search.brave.com/',status,'failure',{},None)
                with self.assertRaises(WebSearchError) as caught:
                    web_search('travel')
                self.assertEqual(caught.exception.details['http_status'],status)
                self.assertNotIn('synthetic-test-credential',str(caught.exception.details))
                self.assertEqual(opener.return_value.open.call_count,1)
                bing.assert_not_called()

    def test_malformed_is_failure_but_empty_results_are_allowed(self):
        for payload,ok in [({},False),({'web':{'results':[]}},True),
                           ({'query':{'original':'travel'}},True)]:
            with patch('travel_agent.brave_provider.build_opener') as opener:
                opener.return_value.open.return_value=Response(json.dumps(payload).encode())
                if ok:
                    self.assertEqual(request_search('travel',3,12)[1],[])
                else:
                    with self.assertRaises(WebSearchError):
                        request_search('travel',3,12)

    def test_research_collects_pages_before_reranking_and_keeps_json(self):
        def response(query,count,timeout,offset):
            info={'http_status':200,'more_results_available':offset==0}
            rows=_EngineRows([{'title':'Travel page','href':f'https://example.org/{offset}',
                               'body':'Travel destination'}],info)
            return '{}',rows,info
        with TemporaryDirectory() as folder, patch('travel_agent.brave_provider.request_search',side_effect=response) as request:
            result=search_evidence('Travel',pages=3,read_pages=0,keep_dir=folder)
            self.assertTrue((Path(folder)/result['id']/'serp-1.json').exists())
        self.assertEqual(request.call_count,2)
        self.assertEqual(result['collected'],2)
        self.assertEqual(result['stop_reason'],'provider_no_more_results')
        self.assertEqual(result['provider'],'brave')
        self.assertFalse(result['retrieval_complete'])

    def test_research_stops_when_pagination_is_unknown(self):
        info={'http_status':200}
        rows=_EngineRows([{'title':'Travel','href':'https://example.org/','body':'Travel'}],info)
        with patch('travel_agent.brave_provider.request_search',return_value=('{}',rows,info)) as request:
            result=search_evidence('Travel',pages=3,read_pages=0)
        self.assertEqual(request.call_count,1)
        self.assertEqual(result['stop_reason'],'provider_pagination_unknown')

    def test_research_empty_results_and_api_failure_are_distinct(self):
        with patch('travel_agent.brave_provider.request_search',return_value=('{}',_EngineRows([],{}),{})):
            empty=search_evidence('Travel',read_pages=0)
        with patch('travel_agent.brave_provider.request_search',side_effect=WebSearchError('failure',details={'http_status':429})) as request:
            failed=search_evidence('Travel',read_pages=0)
        self.assertEqual(empty['stop_reason'],'no_results')
        self.assertEqual(failed['stop_reason'],'http_or_parse_error')
        self.assertEqual(failed['events'][0]['error']['http_status'],429)
        self.assertEqual(request.call_count,1)

    def test_oversize_response_is_not_parsed_or_returned(self):
        with patch('travel_agent.brave_provider.MAX_RESPONSE_BYTES',16), \
                patch('travel_agent.brave_provider.build_opener') as opener:
            opener.return_value.open.return_value=Response(b'x'*17)
            with self.assertRaises(WebSearchError) as caught:
                request_search('travel',3,12)
        self.assertEqual(caught.exception.details['reason'],'response_too_large')
