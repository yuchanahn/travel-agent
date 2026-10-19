import json
import unittest
from unittest.mock import patch
from travel_agent.web_read import extract_page
from travel_agent.structured_lodging import lodging_metadata


class LodgingMetadataTests(unittest.TestCase):
    def html(self,value):
        return ('<script type="application/ld+json">'+json.dumps(value)+'</script>').encode()

    def hotel(self,url='https://example.org/hotel/1'):
        return {'@type':'Hotel','url':url,'name':'Synthetic lodge','address':{'streetAddress':'합성 가평군 주소'},
                'offers':{'price':'FAKE PRICE MUST NOT BE EXTRACTED'}}

    def test_matching_page_preserves_address_without_treating_offers_as_verified(self):
        with patch('travel_agent.web_read.extract',return_value='Synthetic article'):
            text=extract_page(self.html(self.hotel()),'https://example.org/hotel/1?checkIn=2026-11-14')
        self.assertIn('합성 가평군 주소',text)
        self.assertIn('독립 검증 아님',text)
        self.assertIn('Synthetic article',text)
        self.assertNotIn('FAKE PRICE',text)

    def test_other_listing_invalid_json_and_non_lodging_are_not_attributed_to_page(self):
        body=self.html({'@graph':[self.hotel('https://example.org/hotel/2'),{'@type':'Organization','address':{'streetAddress':'office'}}]})
        self.assertEqual(lodging_metadata(body,'https://example.org/hotel/1'),[])
        self.assertEqual(lodging_metadata(b'<script type="application/ld+json">bad</script>','https://example.org'),[])

    def test_graph_address_survives_when_article_extraction_is_empty(self):
        with patch('travel_agent.web_read.extract',return_value=None):
            text=extract_page(self.html({'@graph':[self.hotel()]}),'https://example.org/hotel/1')
        self.assertIn('합성 가평군 주소',text)
