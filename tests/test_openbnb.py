import json
import unittest
from travel_agent.mcp_client import model_result


class OpenBnBPacketTests(unittest.TestCase):
    def packet(self,payload,tool='airbnb_search',budget=6000):
        result={'id':'mcp:abcd','server':'openbnb','remote_tool':tool,'model_adapter':'openbnb',
                'text':json.dumps(payload,ensure_ascii=False),'raw_result':{'private':'full'}}
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

    def test_oversized_section_is_omitted_whole_and_invalid_json_is_explicit(self):
        p=self.packet({'details':[{'id':'AMENITIES_DEFAULT','value':'x'*9000}]},'airbnb_listing_details')
        self.assertEqual(p['data']['sections'],[])
        self.assertEqual(p['data']['omitted_sections'],['AMENITIES_DEFAULT'])
        bad=model_result({'model_adapter':'openbnb','text':'broken','id':'mcp:abcd'})
        self.assertIn('error',json.loads(bad))
