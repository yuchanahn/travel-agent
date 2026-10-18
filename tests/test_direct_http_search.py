"""Transport failures and live-markup regressions without external requests."""
import base64
import builtins
import os
from io import BytesIO
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from types import SimpleNamespace

from travel_agent.web import (
    MAX_RESPONSE_BYTES, WebSearchError, _direct_search, _parse_search_html,
    _request_html, _unwrap_search_url, web_search,
)


class Response(BytesIO):
    status = 200


@patch.dict(os.environ, {'WEB_HTTP_TRANSPORT':'urllib'})
class DirectSearchTests(unittest.TestCase):
    def test_curl_transport_preserves_query_and_never_follows_redirects(self):
        with patch.dict(os.environ, {'WEB_HTTP_TRANSPORT':'curl'}), patch('curl_cffi.requests.Session') as session:
            session.return_value.__enter__.return_value.get.return_value = SimpleNamespace(status_code=200,content=b'<html>body</html>')
            _, details = _request_html('bing','public query',7)
        request=session.return_value.__enter__.return_value.get
        self.assertEqual(request.call_args.kwargs['params'],{'q':'public query'})
        self.assertFalse(request.call_args.kwargs['allow_redirects'])
        self.assertEqual(details['http_transport'],'curl')

    def test_get_preserves_unicode_query_and_fixed_engine_endpoint(self):
        with patch('travel_agent.web.build_opener') as opener:
            opener.return_value.open.return_value = Response(b'<html>body</html>')
            text, details = _request_html('bing', '박물관 & cafe', 7)
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(urlsplit(request.full_url).netloc, 'www.bing.com')
        self.assertEqual(parse_qs(urlsplit(request.full_url).query), {'q':['박물관 & cafe']})
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'], 7)
        self.assertEqual(details['http_status'], 200)

    def test_http_error_is_preserved_and_not_followed_or_retried(self):
        error = HTTPError('https://www.bing.com/search', 429, 'limit', {}, BytesIO())
        with patch('travel_agent.web.build_opener') as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(WebSearchError) as caught:
                _request_html('bing', 'query', 7)
        self.assertEqual(caught.exception.details['http_status'], 429)
        self.assertEqual(opener.return_value.open.call_count, 1)

    def test_network_failure_and_oversized_body_are_errors(self):
        with patch('travel_agent.web.build_opener') as opener:
            opener.return_value.open.side_effect = URLError('unavailable')
            with self.assertRaises(WebSearchError) as caught:
                _request_html('bing', 'query', 7)
        self.assertEqual(caught.exception.details['reason'], 'request_failed')
        with patch('travel_agent.web.build_opener') as opener:
            opener.return_value.open.return_value = Response(b'x' * (MAX_RESPONSE_BYTES + 1))
            with self.assertRaises(WebSearchError) as caught:
                _request_html('bing', 'query', 7)
        self.assertEqual(caught.exception.details['reason'], 'response_too_large')

    def test_challenge_200_is_not_a_success(self):
        with patch('travel_agent.web._request_html', return_value=('<div id="b_captcha">check</div>', {'http_status':200})):
            with self.assertRaises(WebSearchError) as caught:
                _direct_search('query', 3, 7, 'bing')
        self.assertEqual(caught.exception.details['reason'], 'access_challenge')

    def test_bing_linkless_heading_and_snippet(self):
        rows = _parse_search_html('<li class="b_algo"><a href="https://example.invalid/">Site</a><h2>Official</h2><p>Opening hours</p></li>', 'bing')
        self.assertEqual(rows, [{'title':'Official','href':'https://example.invalid/','body':'Opening hours'}])

    def test_tracking_redirect_and_unsafe_targets(self):
        encoded = base64.urlsafe_b64encode(b'https://example.invalid/').decode().rstrip('=')
        self.assertEqual(_unwrap_search_url('https://www.bing.com/ck/a?u=a1'+encoded,'bing'), 'https://example.invalid/')
        for url in ['https://www.bing.com/aclick?x=1','https://www.bing.com/ck/a?u=a1invalid','javascript:alert(1)']:
            self.assertIsNone(_unwrap_search_url(url, 'bing'))

    def test_runtime_works_when_ddgs_import_is_forbidden(self):
        original = builtins.__import__
        def reject(name, *args, **kwargs):
            if name == 'ddgs' or name.startswith('ddgs.'):
                raise AssertionError('DDGS must not be imported by the runtime')
            return original(name, *args, **kwargs)
        def response(engine, query, timeout):
            card = '<h2><a href="https://example.invalid/">Official</a></h2><p>Snippet</p>'
            text = '<li class="b_algo">'+card+'</li>'
            return text, {'method':'GET','http_status':200}
        with patch('builtins.__import__', side_effect=reject), patch('travel_agent.web._request_html', side_effect=response):
            result = web_search('query', provider='http')
        self.assertTrue(result['search_complete'])
        self.assertEqual(result['hits'][0]['engines'], ['bing'])

    def test_old_provider_configuration_gets_migration_error(self):
        with self.assertRaisesRegex(ValueError, 'ddgs was replaced by http'):
            web_search('query', provider='ddgs')


if __name__ == '__main__':
    unittest.main()
