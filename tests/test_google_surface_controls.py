"""Control responses must not be mistaken for ordinary Google SERP results."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('google_surfaces', Path(__file__).resolve().parents[1]/'scripts/probe_google_surfaces.py')
surfaces = importlib.util.module_from_spec(spec)
spec.loader.exec_module(surfaces)


class ControlParsingTests(unittest.TestCase):
    def test_suggestions_are_named_suggestions_without_fabricated_urls(self):
        result = surfaces.classify_control('autocomplete', b'["python", ["python download"]]')
        self.assertEqual(result, {'kind':'suggestions','count':1,'samples':['python download']})

    def test_wrong_json_shape_is_not_a_successful_control(self):
        for body in (b'{}', b'["python", "not a list"]', b'["python", [3]]'):
            with self.assertRaises(ValueError):
                surfaces.classify_control('autocomplete', body)

    @unittest.skipUnless(importlib.util.find_spec('lxml'), 'google-http extra not installed')
    def test_news_is_identified_as_news(self):
        result = surfaces.classify_control('news-rss', b'<rss><channel><item><title>Example</title><link>https://example.com</link></item></channel></rss>')
        self.assertEqual(result['kind'], 'news_articles')
        self.assertEqual(result['count'], 1)

    @unittest.skipUnless(importlib.util.find_spec('lxml'), 'google-http extra not installed')
    def test_html_is_not_an_rss_success(self):
        with self.assertRaises(ValueError):
            surfaces.classify_control('news-rss', b'<html><body>Enable JavaScript</body></html>')
