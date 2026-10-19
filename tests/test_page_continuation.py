from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from unittest.mock import patch

from travel_agent.agent import validate_call
from travel_agent.memory import canonical
from travel_agent.web_context import format_web_result
from travel_agent.web_read import PageCache, web_read


SOURCE={'id':'web:0123456789abcdef','title':'Synthetic hotel','url':'https://example.invalid/room'}
TEXT='\n\n'.join('Room policy paragraph %d. Cancellation terms are specific to this room.' % i for i in range(45))


class PageContinuationTests(unittest.TestCase):
    def test_complete_cached_document_reconstructed_without_refetch(self):
        cache=PageCache()
        with patch('travel_agent.web_read.fetch_public_page',return_value=(b'html',{'http_status':200} )) as fetch, \
             patch('travel_agent.web_read.extract_page',return_value=TEXT):
            initial=web_read(SOURCE,'policy',cache=cache,max_bytes=1400)
            self.assertEqual(initial['next_start_index'],0)
            self.assertEqual(initial['reading_mode'],'query_excerpt')
            offset=0
            pieces=[]
            while offset is not None:
                result=web_read(SOURCE,'policy',cache=cache,max_bytes=1400,
                    document_token=initial['document_token'],start_index=offset)
                self.assertTrue(result['cache_hit'])
                self.assertEqual(result['fetched_at'],initial['fetched_at'])
                self.assertLessEqual(len(canonical(result).encode()),1400)
                pieces.append(result['text'])
                new_offset=result['next_start_index']
                self.assertTrue(new_offset is None or new_offset>offset)
                offset=new_offset
            fetch.assert_called_once()
        self.assertEqual(''.join(pieces),TEXT)
        for style in ('compact_json','compact_md','full_json'):
            content=format_web_result(initial,style)
            self.assertIn('document_token',content)
            self.assertIn('next_start_index',content)

    def test_tokens_scoped_to_run_and_source_without_network(self):
        cache=PageCache()
        with patch('travel_agent.web_read.fetch_public_page') as fetch:
            with self.assertRaises(ValueError):
                web_read(SOURCE,'policy',cache=cache,document_token='0'*16,start_index=0)
            fetch.assert_not_called()

    def test_long_unbroken_unicode_is_not_lost_or_presented_as_complete_fact(self):
        text='가나다'*1400
        with patch('travel_agent.web_read.fetch_public_page',return_value=(b'html',{})), \
             patch('travel_agent.web_read.extract_page',return_value=text):
            cache=PageCache()
            page=web_read(SOURCE,'policy',cache=cache,max_bytes=1400)
            self.assertEqual(page['text'],'')
            self.assertIn('excerpt_unavailable_reason',page)
            offset=page['next_start_index']
            pieces=[]
            while offset is not None:
                result=web_read(SOURCE,'policy',cache=cache,document_token=page['document_token'],start_index=offset,max_bytes=1400)
                self.assertTrue(result['text_is_fragment'])
                self.assertLessEqual(len(canonical(result).encode()),1400)
                pieces.append(result['text'])
                offset=result['next_start_index']
        self.assertEqual(''.join(pieces),text)

    def test_new_query_on_same_source_uses_frozen_text(self):
        with patch('travel_agent.web_read.fetch_public_page',return_value=(b'html',{})) as fetch, \
             patch('travel_agent.web_read.extract_page',return_value=TEXT):
            cache=PageCache()
            first=web_read(SOURCE,'policy',cache=cache)
            second=web_read(SOURCE,'cancellation',cache=cache)
        self.assertEqual(first['document_token'],second['document_token'])
        self.assertTrue(second['cache_hit'])
        fetch.assert_called_once()

    def test_parallel_first_read_fetches_once(self):
        cache=PageCache()
        with patch('travel_agent.web_read.fetch_public_page',return_value=(b'html',{})) as fetch, \
             patch('travel_agent.web_read.extract_page',return_value=TEXT), ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda q:web_read(SOURCE,q,cache=cache),['policy','room']))
        self.assertEqual(results[0]['document_token'],results[1]['document_token'])
        fetch.assert_called_once()

    def test_invalid_cursor_pairs_rejected(self):
        for extra in [{'start_index':0},{'document_token':'0'*16},
                      {'document_token':'0'*16,'start_index':True},
                      {'document_token':'0'*16,'start_index':-1}]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_call({'function':{'name':'web_read','arguments':{'source_id':SOURCE['id'],'query':'policy',**extra}}})

    def test_different_sources_still_fetch_in_parallel(self):
        barrier=Barrier(2)
        def fetch(*args):
            barrier.wait(timeout=3)
            return b'html', {}
        cache=PageCache()
        with patch('travel_agent.web_read.fetch_public_page',side_effect=fetch), \
             patch('travel_agent.web_read.extract_page',return_value=TEXT), ThreadPoolExecutor(2) as pool:
            sources=[SOURCE,{**SOURCE,'id':'web:1111111111111111'}]
            results=list(pool.map(lambda source:web_read(source,'policy',cache=cache),sources))
        self.assertEqual(len(results),2)

    def test_cache_capacity_is_explicit_and_does_not_evict_readable_page(self):
        cache=PageCache(max_bytes=len(TEXT.encode()))
        with patch('travel_agent.web_read.fetch_public_page',return_value=(b'html',{})), \
             patch('travel_agent.web_read.extract_page',return_value=TEXT):
            first=web_read(SOURCE,'policy',cache=cache)
            with self.assertRaises(ValueError):
                web_read({**SOURCE,'id':'web:1111111111111111'},'policy',cache=cache)
            again=web_read(SOURCE,'policy',cache=cache,document_token=first['document_token'],start_index=0)
        self.assertTrue(again['cache_hit'])
