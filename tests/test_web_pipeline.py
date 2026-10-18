import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from travel_agent.web_pipeline import (canonical_url, next_offset, group_candidates,
                                       rank_candidates, pack_digest, search_evidence, passages, tokens)
from travel_agent.web import _parse_search_rss, _bing_locale_params, _request_html


def serp(start, next_first=None):
    cards=''.join(f'<li class="b_algo"><h2><a href="https://example.org/{i}">Python cancellation {i}</a></h2><p>TaskGroup cancellation documentation.</p></li>' for i in range(start,start+3))
    link=f'<a class="sb_pagN" href="/search?q=Python&amp;first={next_first}">Next</a>' if next_first else ''
    return cards+link, {'http_status':200}


class PipelineTests(unittest.TestCase):
    def test_short_korean_query_matches_the_same_term_in_a_compound(self):
        self.assertIn('ko:관광',set(tokens('관광'))&set(tokens('한국관광공사')))
        rows=[{'title':'한국 일반 정보','href':'https://example.org/general','body':'한국 문화 소개','page':1,'rank':1},
              {'title':'대한민국 구석구석','href':'https://example.org/travel','body':'한국관광공사 지역관광 여행소식','page':1,'rank':2}]
        ranked=rank_candidates('한국 관광 명소',group_candidates(rows))
        self.assertEqual(ranked[0]['url'],'https://example.org/travel')
        self.assertIn('ko:관광',ranked[0]['matched_terms'])

    def test_rss_preserves_sources_and_rejects_dtd_or_wrong_format(self):
        feed='<rss><channel><item><title>TaskGroup</title><link>https://docs.python.org/3/library/asyncio-task.html</link><description>&lt;b&gt;Cancellation&lt;/b&gt; semantics</description></item><item><title>Unsafe</title><link>file:///secret</link></item></channel></rss>'
        rows=_parse_search_rss(feed)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['body'],'Cancellation semantics')
        self.assertEqual(rows.details['result_cards'],2)
        for invalid in ['<html><body>Access check</body></html>',
                        '<!DOCTYPE rss [<!ENTITY leak SYSTEM "file:///secret">]><rss><channel/></rss>']:
            with self.assertRaises(ValueError):
                _parse_search_rss(invalid)

    def test_rss_stops_at_feed_limit_not_fake_pagination(self):
        feed='<rss><channel><item><title>Python documentation</title><link>https://docs.python.org/</link><description>Python language documentation</description></item></channel></rss>'
        with patch('travel_agent.web_pipeline._request_html',return_value=(feed,{'http_status':200})) as request:
            result=search_evidence('Python',pages=10,read_pages=0,serp_format='rss')
        self.assertEqual(request.call_count,1)
        self.assertEqual(result['stop_reason'],'feed_limit')
        self.assertFalse(result['retrieval_complete'])
        self.assertEqual(result['sources'][0]['url'],'https://docs.python.org/')

    def test_locale_does_not_send_observed_bad_us_market_parameter(self):
        self.assertEqual(_bing_locale_params('en-US'),{'setlang':'en'})
        self.assertEqual(_bing_locale_params('ko-KR'),{'setlang':'ko','cc':'kr'})
        self.assertEqual(_bing_locale_params('none'),{})
        with self.assertRaises(ValueError):
            _bing_locale_params('en-US&q=another')

    def test_real_request_builder_keeps_query_and_explicit_format(self):
        with patch.dict('os.environ',{'WEB_HTTP_TRANSPORT':'curl'}), patch('curl_cffi.requests.Session') as session:
            get=session.return_value.__enter__.return_value.get
            get.return_value=SimpleNamespace(status_code=200,content=b'<rss><channel/></rss>')
            text,info=_request_html('bing','TaskGroup cancellation',12,search_format='rss',locale='en-US')
        self.assertEqual(get.call_args.kwargs['params'],{'q':'TaskGroup cancellation','format':'rss','setlang':'en'})
        self.assertEqual(info['response_format'],'rss')
        self.assertIn('<rss>',text)

    def test_next_link_cannot_change_query_or_host(self):
        self.assertEqual(next_offset(serp(0,4)[0],'Python',1),4)
        self.assertIsNone(next_offset(serp(0,4)[0],'Other',1))
        self.assertIsNone(next_offset('<a class="sb_pagN" href="https://evil.invalid/search?q=Python&amp;first=4">N</a>','Python',1))

    def test_duplicates_preserve_distinct_source_provenance(self):
        rows=[{'href':'https://example.org/a?utm_source=x','title':'A','body':'content','page':1,'rank':1},
              {'href':'https://example.org/a','title':'A','body':'content','page':2,'rank':2}]
        groups=group_candidates(rows)
        self.assertEqual(len(groups),1)
        self.assertEqual(len(groups[0]['duplicates']),2)
        self.assertEqual(canonical_url('https://example.org/a?id=2&utm_source=x'),'https://example.org/a?id=2')

    def test_relevant_lower_rank_beats_irrelevant_first_result(self):
        rows=[{'href':'https://example.org/'+str(i),'title':title,'body':body,'page':1,'rank':i}
              for i,(title,body) in enumerate([('Store finder','Shopping opening hours'),
                                               ('국립춘천박물관 관람안내','관람시간 및 휴관일 안내')],1)]
        ranked=rank_candidates('국립춘천박물관 관람시간 휴관일',group_candidates(rows))
        self.assertIn('춘천박물관',ranked[0]['title'])
        self.assertEqual(ranked[1]['score'],0)

    def test_repeated_page_stops_without_pretending_new_candidates(self):
        with TemporaryDirectory() as directory, patch('travel_agent.web_pipeline._request_html',side_effect=[serp(0,4),serp(0,7)]) as request:
            result=search_evidence('Python',pages=5,read_pages=0,keep_dir=directory)
            self.assertEqual(request.call_count,2)
            self.assertEqual(result['stop_reason'],'repeated_page')
            self.assertEqual(result['groups'],3)
            self.assertFalse(result['retrieval_complete'])
            saved=json.loads(next(Path(directory).glob('*/report.json')).read_text(encoding='utf-8'))
            self.assertEqual(len(saved['events']),2)
            self.assertEqual(len(list(Path(directory).glob('*/serp-*.html'))),2)

    def test_failed_body_stays_explicitly_a_snippet(self):
        from travel_agent.web import WebSearchError
        with patch('travel_agent.web_pipeline._request_html',return_value=serp(0)), patch('travel_agent.web_pipeline.fetch_public_page',side_effect=WebSearchError('failure',details={'reason':'http_error'})):
            result=search_evidence('Python',read_pages=2)
        self.assertTrue(result['sources'])
        self.assertTrue(all(not s['page_fetched'] and s['content_kind']=='search_snippet' for s in result['sources']))

    def test_utf8_budget_and_passages_do_not_invent_text(self):
        source={'id':'web:123','title':'제목','url':'https://example.org/','content_kind':'page_excerpt','page_fetched':True,'text':'관람시간 안내 '*1000}
        digest,selected=pack_digest('질문',[source],1500,{})
        self.assertLessEqual(len(digest.encode()),1500)
        self.assertIn(source['url'],digest)
        self.assertTrue(source['text'].startswith(selected[0]['delivered_text']))
        excerpt,_=passages('무관한 내용\n\n국립춘천박물관 관람시간 안내','춘천박물관 관람시간')
        self.assertIn('국립춘천박물관 관람시간 안내',excerpt)
        self.assertIn(excerpt,'무관한 내용\n\n국립춘천박물관 관람시간 안내')

    def test_low_overlap_is_not_returned_as_good_evidence(self):
        unrelated='<li class="b_algo"><h2><a href="https://example.org/">국립중앙박물관</a></h2><p>국립 박물관 문화향연</p></li>'
        with patch('travel_agent.web_pipeline._request_html',return_value=(unrelated,{'http_status':200})), patch('travel_agent.web_pipeline.fetch_public_page') as fetch:
            result=search_evidence('국립춘천박물관 관람시간 휴관일 교통')
        self.assertEqual(result['sources'],[])
        self.assertEqual(result['evidence_status'],'insufficient_candidates')
        fetch.assert_not_called()

    def test_budget_is_applied_before_selecting_important_late_passage(self):
        raw=('Welcome to our museum and our introductory visitor story. '*30
             +'\n\nOpening hours 09:00-18:00. Holiday closure Monday. Transit bus 10.')
        source={'id':'web:test','title':'Museum','url':'https://example.org/',
                'content_kind':'page_excerpt','page_fetched':True,'text':raw[:1000],'_page_text':raw}
        digest,included=pack_digest('opening hours holiday transit',[source],1500,{})
        self.assertIn('09:00-18:00',digest)
        self.assertIn('closure Monday',digest)
        self.assertNotIn('_page_text',included[0])
        self.assertLessEqual(len(digest.encode()),1500)


if __name__=='__main__':
    unittest.main()
