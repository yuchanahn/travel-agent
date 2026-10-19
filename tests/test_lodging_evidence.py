import json
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from travel_agent.lodging_evidence import LodgingEvidence, listing_key
from travel_agent.agent import run_agent, validate_call, execute_batch
from travel_agent.memory import MemoryStore, canonical


def packet(number, facilities, source='mcp:aaaa', context=None):
    return canonical({'id': source, 'model_adapter': 'openbnb', 'remote_tool': 'airbnb_listing_details',
        'request_context': context or {}, 'data': {'listing_url': 'https://www.airbnb.com/rooms/'+number,
        'sections': [{'id': 'AMENITIES_DEFAULT', 'seeAllAmenitiesGroups': facilities}],
        'missing_sections': ['POLICIES_DEFAULT'], 'omitted_sections': []}})


class LodgingEvidenceTests(unittest.TestCase):
    def test_properties_never_share_amenities_and_unknown_is_not_excluded(self):
        store = LodgingEvidence()
        store.ingest(packet('111', {'Outdoor': 'Pool, BBQ grill'}))
        store.ingest(packet('222', {'Entertainment': 'Record player', 'Not included': 'Washer'}, 'mcp:bbbb'))
        second = store.read('airbnb:222')
        self.assertNotIn('BBQ grill', canonical(second))
        self.assertNotIn('Pool', canonical(second))
        self.assertIn('Not included', canonical(second))
        self.assertIn('POLICIES_DEFAULT', canonical(second))
        self.assertEqual(second['observations'][0]['source_id'], 'mcp:bbbb')

    def test_dates_and_sources_remain_separate_not_overwritten(self):
        store = LodgingEvidence()
        for source, day in [('mcp:aaaa', '2026-11-14'), ('mcp:bbbb', '2026-12-14')]:
            store.ingest(packet('111', {'Outdoor': 'Pool'}, source, {'checkin': day}))
        result = store.read('airbnb:111')
        self.assertEqual(len(result['observations']), 2)
        self.assertEqual(result['observations'][0]['request_context']['checkin'], '2026-12-14')
        self.assertTrue(all(o['price_conditions_verified'] is False for o in result['observations']))

    def test_only_tool_history_is_restored(self):
        content = packet('111', {'Outdoor': 'Pool'})
        for role in ['user', 'assistant', 'system']:
            self.assertEqual(LodgingEvidence([{'role':role,'content':content}]).read()['listings'], [])
        self.assertEqual(len(LodgingEvidence([{'role':'tool','content':content}]).read()['listings']), 1)

    def test_unobserved_or_arbitrary_urls_are_not_merged(self):
        for url in ['https://evil.invalid/rooms/111', 'https://airbnb.com.evil.invalid/rooms/111',
                    'http://www.airbnb.com/rooms/111', 'https://www.airbnb.com/rooms/111/extra']:
            self.assertIsNone(listing_key(url))
        self.assertEqual(listing_key('https://www.airbnb.com/rooms/111?adults=2'), 'airbnb:111')
        with self.assertRaises(ValueError): LodgingEvidence().read('airbnb:111')

    def test_budget_omits_whole_observations(self):
        store = LodgingEvidence()
        store.ingest(packet('111', {'Outdoor':'x'*9000}))
        result=store.read('airbnb:111', max_bytes=1200)
        self.assertEqual(result['observations'], [])
        self.assertEqual(result['omitted_source_ids'], ['mcp:aaaa'])
        self.assertLessEqual(len(canonical(result).encode()),1200)

    def test_model_cannot_write_facts(self):
        with self.assertRaises(ValueError):
            validate_call({'function':{'name':'lodging_evidence','arguments':{'listing_key':'airbnb:111','facilities':'Pool'}}})

    def test_duplicate_lookup_is_allowed_only_after_new_evidence(self):
        store=LodgingEvidence()
        store.ingest(packet('111',{'Outdoor':'Pool'}))
        call={'id':'lookup','function':{'name':'lodging_evidence','arguments':{'listing_key':'airbnb:111'}}}
        seen=set()
        def read():
            results,_=execute_batch([call],store=None,user='u',session='s',mode='bm25',rerank=False,
                seen=seen,enable_web=False,deadline=time.perf_counter()+10,trace=Mock(),step=1,workers=1,lodging=store)
            return results[0][1]
        self.assertNotIn('error',read())
        self.assertIn('error',read())
        store.ingest(packet('111',{'Outdoor':'BBQ grill'},'mcp:bbbb'))
        updated=read()
        self.assertNotIn('error',updated)
        self.assertIn('BBQ grill',canonical(updated))

    def test_real_harness_lookup_round_trip_has_original_citation(self):
        history=[{'role':'tool','tool_name':'mcp_openbnb_details','content':packet('222', {'Entertainment':'Record player'}, 'mcp:bbbb')}]
        call={'id':'lookup','function':{'name':'lodging_evidence','arguments':{'listing_key':'airbnb:222'}}}
        replies=[{'message':{'role':'assistant','content':'','tool_calls':[call]}},
                 {'message':{'role':'assistant','content':'Record player [mcp:bbbb]'}}]
        with tempfile.TemporaryDirectory() as folder, MemoryStore(folder+'/db.sqlite3') as memory:
            with patch('travel_agent.agent.chat', side_effect=replies) as chat:
                result=run_agent(memory,'u','s','Compare',history=history,enable_web=False,
                    prior_mcp_sources=[{'id':'mcp:bbbb'}],trace_dir=folder+'/trace')
                sent=chat.call_args.args[0][-1]
        self.assertEqual(result['status'],'completed')
        self.assertTrue(result['citation_ids_valid'])
        self.assertEqual(sent['tool_call_id'],'lookup')
        self.assertEqual(json.loads(sent['content'])['listing_key'],'airbnb:222')

    def test_scoped_store_restores_details_after_history_compaction(self):
        raw={'id':'mcp:bbbb','server':'openbnb','remote_tool':'airbnb_listing_details','model_adapter':'openbnb',
             'text':json.dumps({'listingUrl':'https://www.airbnb.com/rooms/222',
                 'details':[{'id':'AMENITIES_DEFAULT','seeAllAmenitiesGroups':{'Entertainment':'Record player'}}]})}
        event={'event_id':'t-1','turn_id':'turn1','timestamp':'2026-10-19T01:00:00+00:00',
               'role':'tool','content':canonical(raw)}
        replies=[{'message':{'role':'assistant','content':'','tool_calls':[{'id':'lookup','function':{
            'name':'lodging_evidence','arguments':{'listing_key':'airbnb:222'}}}]}},
            {'message':{'role':'assistant','content':'Record player [mcp:bbbb]'}}]
        with tempfile.TemporaryDirectory() as folder, MemoryStore(folder+'/db.sqlite3') as memory:
            memory.add('u','s',[event])
            memory.add('other','s',[{**event,'event_id':'t-2','content':packet('111', {'Outdoor':'Pool'},'mcp:aaaa')}])
            with patch('travel_agent.agent.chat',side_effect=replies) as chat:
                result=run_agent(memory,'u','s','Compare',history=[],summary='요약만 남음',enable_web=False,trace_dir=folder+'/trace')
                sent=chat.call_args.args[0][-1]['content']
        self.assertEqual(result['status'],'completed')
        self.assertTrue(result['citation_ids_valid'])
        self.assertNotIn('Pool',sent)
        self.assertNotIn('mcp:aaaa',result['evidence_ids'])
