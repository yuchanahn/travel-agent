import json
import unittest
from travel_agent.mcp_client import model_result


class OpenBnBPacketTests(unittest.TestCase):
    def packet(self,payload,tool='airbnb_search',budget=6000,context=None):
        result={'id':'mcp:abcd','server':'openbnb','remote_tool':tool,'model_adapter':'openbnb',
                'text':json.dumps(payload,ensure_ascii=False),'raw_result':{'private':'full'},
                'request_context':context if context is not None else {'checkin':'2026-11-14','checkout':'2026-11-15','adults':2}}
        original=result['text']
        encoded=model_result(result,budget)
        self.assertLessEqual(len(encoded.encode()),budget)
        self.assertEqual(result['text'],original)
        self.assertNotIn('raw_result',json.loads(encoded))
        return json.loads(encoded)

    def test_search_keeps_complete_records_prices_and_cursor_under_budget(self):
        rows=[{'id':str(i),'url':'https://www.airbnb.com/rooms/'+str(i),
               'demandStayListing':{'description':{'name':{'localizedStringWithTranslationPreference':'합성 숙소 '*12}}},
               'structuredDisplayPrice':{'primaryLine':{'accessibilityLabel':'₩179,000 total'}}} for i in range(18)]
        p=self.packet({'searchResults':rows,'paginationInfo':{'pageCursors':['first','second']}})
        self.assertTrue(p['truncated'])
        data=p['data']
        self.assertGreater(len(data['results']),0)
        self.assertEqual(len(data['results'])+data['omitted_count'],18)
        self.assertEqual(data['page_cursors'],['first','second'])
        for row in data['results']:
            self.assertEqual(row['price']['primaryLine']['accessibilityLabel'],'₩179,000 total')
            self.assertTrue(row['url'].endswith(row['id']))

    def test_missing_details_and_not_included_are_not_available_amenities(self):
        p=self.packet({'details':[{'id':'LOCATION_DEFAULT'}, {'id':'AMENITIES_DEFAULT',
                        'seeAllAmenitiesGroups':{'Outdoor':'BBQ grill','Not included':'Washer, Dryer'}}]},'airbnb_listing_details')
        self.assertIn('LOCATION_DEFAULT',p['data']['missing_sections'])
        self.assertIn('POLICIES_DEFAULT',p['data']['missing_sections'])
        self.assertEqual(p['data']['sections'][0]['seeAllAmenitiesGroups']['Not included'],'Washer, Dryer')

    def test_undated_prices_are_withheld_and_requested_dates_are_not_verification(self):
        payload={'searchResults':[{'id':'test','structuredDisplayPrice':{'primaryLine':{'accessibilityLabel':'₩150,000 total'}}}]}
        for context in [{},{'checkin':'2026-11-14','adults':2},
                        {'checkin':'2026-11-15','checkout':'2026-11-14','adults':2},
                        {'checkin':'2026-11-14','checkout':'2026-11-15'}]:
            with self.subTest(context=context):
                packet=self.packet(payload,context=context)
                self.assertIsNone(packet['data']['results'][0]['price'])
                self.assertIsNotNone(packet['data']['price_withheld_reason'])
        packet=self.packet(payload,context={'checkin':'2026-11-14','checkout':'2026-11-17','adults':2})
        self.assertEqual(packet['data']['requested_nights'],3)
        self.assertFalse(packet['data']['price_conditions_verified'])
        self.assertEqual(packet['request_context']['checkout'],'2026-11-17')
        self.assertEqual(packet['data']['results'][0]['price']['primaryLine']['accessibilityLabel'],'₩150,000 total')

    def test_oversized_section_is_omitted_whole_and_invalid_json_is_explicit(self):
        p=self.packet({'details':[{'id':'AMENITIES_DEFAULT','value':'x'*9000}]},'airbnb_listing_details')
        self.assertEqual(p['data']['sections'],[])
        self.assertEqual(p['data']['omitted_sections'],['AMENITIES_DEFAULT'])
        bad=model_result({'model_adapter':'openbnb','text':'broken','id':'mcp:abcd'})
        self.assertIn('error',json.loads(bad))
