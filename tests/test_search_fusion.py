"""Synthetic fusion contracts, including actual worker overlap; no network."""
from threading import Barrier
import unittest
from unittest.mock import patch

from travel_agent.web import WebSearchError, _duckduckgo_search, _provider_search, web_search


def row(url, title='Example', body='Synthetic snippet'):
    return {'href':url, 'title':title, 'body':body}


class FusionTests(unittest.TestCase):
    def test_duckduckgo_adapter_get_and_redirect_decoding(self):
        text = '<div class="result__body"><h2>Official</h2><a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.invalid%2F">Snippet</a></div>'
        with patch('travel_agent.web._request_html', return_value=(text, {'method':'GET','http_status':200})) as request:
            rows = _duckduckgo_search('public query',3,10)
        request.assert_called_once_with('duckduckgo', 'public query', 10)
        self.assertEqual(rows[0]['href'], 'https://example.invalid/')
        self.assertEqual(rows.details['http_status'], 200)

    def test_duckduckgo_202_is_an_error_not_empty_results(self):
        with patch('travel_agent.web._request_html', side_effect=WebSearchError('HTTP failure', details={'http_status':202})):
            with self.assertRaises(WebSearchError) as caught:
                _duckduckgo_search('query',3,10)
        self.assertEqual(caught.exception.details['http_status'], 202)

    def test_duckduckgo_unparsed_200_is_not_search_success(self):
        with patch('travel_agent.web._request_html', return_value=('<html>Unexpected response</html>', {'http_status':200})):
            with self.assertRaises(WebSearchError) as caught:
                _duckduckgo_search('query',3,10)
        self.assertEqual(caught.exception.details['reason'], 'empty_or_unparsed')

    def test_both_engines_start_and_each_is_called_once(self):
        barrier = Barrier(2)
        def search(query, count, timeout, engine):
            barrier.wait(timeout=2)
            return [row('https://'+engine+'.invalid/')]
        with patch('travel_agent.web._provider_search', side_effect=search) as provider:
            result = web_search('query', backend='duckduckgo,bing,duckduckgo')
        self.assertCountEqual([call.args[-1] for call in provider.call_args_list], ['duckduckgo','bing'])
        self.assertEqual(result['engines_returned'], ['duckduckgo','bing'])
        self.assertTrue(result['search_complete'])

    def test_shared_url_gets_both_ranks_and_rrf_leads(self):
        def search(query, count, timeout, engine):
            return [row('https://'+engine+'.invalid/'), row('https://SHARED.invalid/page#'+engine)]
        with patch('travel_agent.web._provider_search', side_effect=search):
            result = web_search('query', top_k=5)
        shared = result['hits'][0]
        self.assertEqual(shared['url'], 'https://shared.invalid/page')
        self.assertEqual(shared['engine_ranks'], {'duckduckgo':2,'bing':2})
        self.assertEqual(len(result['hits']), 3)

    def test_one_failure_preserves_sibling_and_reports_incomplete_search(self):
        def search(query, count, timeout, engine):
            if engine == 'bing':
                raise WebSearchError('disabled', details={'reason':'engine_disabled_or_unavailable'})
            return [row('https://example.invalid/')]
        with patch('travel_agent.web._provider_search', side_effect=search):
            result = web_search('query')
        self.assertFalse(result['search_complete'])
        self.assertEqual(result['engines_returned'], ['duckduckgo'])
        self.assertEqual(result['hits'][0]['engines'], ['duckduckgo'])
        self.assertEqual(result['engine_status']['bing']['reason'], 'engine_disabled_or_unavailable')

    def test_unexpected_engine_exception_does_not_drop_sibling(self):
        def search(query, count, timeout, engine):
            if engine == 'bing':
                raise ValueError('unexpected library exception')
            return [row('https://example.invalid/')]
        with patch('travel_agent.web._provider_search', side_effect=search):
            result = web_search('query')
        self.assertEqual(len(result['hits']), 1)
        self.assertEqual(result['engine_status']['bing']['error_type'], 'ValueError')

    def test_all_failures_are_not_an_empty_success(self):
        with patch('travel_agent.web._provider_search', side_effect=WebSearchError('failed')):
            with self.assertRaises(WebSearchError) as caught:
                web_search('query')
        self.assertEqual(set(caught.exception.details['engine_status']), {'duckduckgo','bing'})

    def test_unsupported_engine_does_not_make_a_request(self):
        with patch('travel_agent.web._request_html') as request:
            with self.assertRaises(ValueError):
                _provider_search('query', 3, 10, 'google')
        request.assert_not_called()

    def test_duplicate_within_one_engine_does_not_double_its_rrf_vote(self):
        def search(query, count, timeout, engine):
            if engine == 'duckduckgo':
                return [row('https://repeated.invalid/')]*3
            return [row('https://other.invalid/'),row('https://other.invalid/#same')]
        with patch('travel_agent.web._provider_search', side_effect=search):
            result = web_search('query')
        self.assertEqual(len(result['hits']), 2)
        self.assertEqual(result['hits'][0]['engine_ranks'], {'duckduckgo':1})
