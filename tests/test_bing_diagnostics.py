"""Offline regressions for the two observed Bing markup forms; no network."""
import base64
import unittest

from scripts.diagnose_bing import parse_results


class BingDiagnosticTests(unittest.TestCase):
    def test_heading_link(self):
        title, hits = parse_results('<title>Query</title><li class="b_algo"><h2><a href="https://example.invalid/">Official</a></h2></li>')
        self.assertEqual(title, 'Query')
        self.assertEqual(hits, [{'title':'Official', 'url':'https://example.invalid/'}])

    def test_heading_without_link_uses_result_link(self):
        _, hits = parse_results('<li class="b_algo"><a href="https://example.invalid/">Site</a><h2>Official</h2></li>')
        self.assertEqual(hits, [{'title':'Official', 'url':'https://example.invalid/'}])

    def test_bing_redirect_decodes_but_navigation_is_skipped(self):
        encoded = base64.urlsafe_b64encode(b'https://example.invalid/').decode().rstrip('=')
        _, hits = parse_results('<li class="b_algo"><h2>Official</h2><a href="https://www.bing.com/aclick?x=1">Ad</a><a href="https://www.bing.com/ck/a?u=a1'+encoded+'">Site</a></li>')
        self.assertEqual(hits[0]['url'], 'https://example.invalid/')

    def test_unusable_urls_and_partial_class_are_not_hits(self):
        _, hits = parse_results('<li class="b_algo"><h2>Bad</h2><a href="javascript:alert(1)">Bad</a></li><li class="b_algo_extra"><h2><a href="https://example.invalid/">Wrong class</a></h2></li>')
        self.assertEqual(hits, [])


if __name__ == '__main__':
    unittest.main()
