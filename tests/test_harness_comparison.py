"""Protect comparison controls and the adversarial fixture's ground truth."""
import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

spec = importlib.util.spec_from_file_location('compare_harnesses',
    Path(__file__).resolve().parents[1]/'scripts/compare_harnesses.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class HarnessComparisonTests(unittest.TestCase):
    def test_price_conditions_are_distinct_and_total_is_unknown(self):
        a = comparison.fixture('read_stay', {'listing_id': 'A'}, 'price-conditions')
        b = comparison.fixture('read_stay', {'listing_id': 'B'}, 'price-conditions')
        self.assertNotEqual(a['display_price']['checkin'], b['display_price']['checkin'])
        self.assertEqual(a['display_price']['adults'], 4)
        self.assertEqual(b['display_price']['adults'], 2)
        self.assertLess(b['display_price']['KRW'], 300000)
        self.assertFalse(b['checkout_total_verified'])

    def test_facilities_do_not_leak_between_properties(self):
        a = comparison.fixture('read_stay', {'listing_id': 'A'}, 'facilities')
        b = comparison.fixture('read_stay', {'listing_id': 'B'}, 'facilities')
        self.assertIn('수영장', a['facilities'])
        self.assertNotIn('수영장', b['facilities'])
        with self.assertRaises(ValueError):
            comparison.fixture('read_stay', {'listing_id': 'C'}, 'facilities')

    def test_sdk_beta_query_reaches_local_upstream_with_controlled_settings(self):
        class Response(io.BytesIO):
            status = 200
            headers = {'Content-Type': 'application/json'}
        requests = []
        def upstream(request, **kwargs):
            requests.append(request)
            return Response(b'{"content":[]}')
        with TemporaryDirectory() as folder:
            with patch.object(comparison, 'urlopen', side_effect=upstream), patch.object(comparison, 'api', return_value={'models': []}):
                with comparison.observed_endpoint(Path(folder)) as (base, records):
                    req = Request(base+'/v1/messages?beta=true',
                        data=json.dumps({'model': comparison.PROFILE, 'max_tokens': 32000,
                            'thinking': {'type': 'enabled'}, 'temperature': 1}).encode(),
                        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer PRIVATE'})
                    with urlopen(req, timeout=5) as response:
                        self.assertEqual(response.status, 200)
                        response.read()
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0].full_url, comparison.OLLAMA+'/v1/messages')
            self.assertIsNone(requests[0].get_header('Authorization'))
            body = records[0]['forwarded_request']
            self.assertEqual(body['max_tokens'], 4096)
            self.assertEqual(body['temperature'], 0)
            self.assertEqual(body['thinking'], {'type': 'disabled'})


if __name__ == '__main__':
    unittest.main()
