"""Bing-only dispatch, duplicate URLs, and explicit errors; no network."""
import unittest
from unittest.mock import patch

from travel_agent.web import WebSearchError, _provider_search, web_search


def row(url='https://example.invalid/', title='Example', body='Synthetic snippet'):
    return {'href':url, 'title':title, 'body':body}


class BingDispatchTests(unittest.TestCase):
    def test_default_calls_bing_once_and_reports_only_bing(self):
        with patch('travel_agent.web._provider_search', return_value=[row()]) as provider:
            result = web_search('query')
        provider.assert_called_once_with('query', 3, 15, 'bing')
        self.assertEqual(result['engines_returned'], ['bing'])
        self.assertEqual(result['hits'][0]['engines'], ['bing'])
        self.assertTrue(result['search_complete'])

    def test_repeated_bing_configuration_is_deduplicated(self):
        with patch('travel_agent.web._provider_search', return_value=[row()]) as provider:
            web_search('query', backend='bing,bing')
        self.assertEqual(provider.call_count, 1)

    def test_duplicate_url_does_not_gain_an_extra_vote(self):
        with patch('travel_agent.web._provider_search', return_value=[row(), row('https://example.invalid/#same')]):
            result = web_search('query')
        self.assertEqual(len(result['hits']), 1)
        self.assertEqual(result['hits'][0]['engine_ranks'], {'bing':1})

    def test_bing_failure_is_an_error_without_another_engine(self):
        with patch('travel_agent.web._provider_search', side_effect=WebSearchError('HTTP failure', details={'http_status':429})) as provider:
            with self.assertRaises(WebSearchError) as caught:
                web_search('query')
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(set(caught.exception.details['engine_status']), {'bing'})
        self.assertEqual(caught.exception.details['engine_status']['bing']['http_status'], 429)

    def test_removed_engine_configuration_is_rejected_before_network(self):
        with patch('travel_agent.web._request_html') as request:
            for provider in ('http', 'webserp'):
                with self.assertRaises(ValueError):
                    web_search('query', provider=provider, backend='duckduckgo')
            with self.assertRaises(ValueError):
                _provider_search('query', 3, 10, 'duckduckgo')
        request.assert_not_called()

    def test_unparsed_200_is_not_search_success(self):
        with patch('travel_agent.web._request_html', return_value=('<html>Unexpected response</html>', {'http_status':200})):
            with self.assertRaises(WebSearchError) as caught:
                _provider_search('query', 3, 10, 'bing')
        self.assertEqual(caught.exception.details['reason'], 'empty_or_unparsed')
