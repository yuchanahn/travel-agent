"""Read-only, source-scoped lodging observations from model-visible MCP packets."""
import json
import re
from urllib.parse import urlsplit

from .memory import canonical


def listing_key(url):
    """Never join properties by display name, coordinates, or search region."""
    if not isinstance(url, str):
        return None
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme == 'https' and parsed.hostname in {'airbnb.com', 'www.airbnb.com'} and parsed.port in (None,443) and not parsed.username
    except ValueError:
        return None
    if not valid:
        return None
    match = re.fullmatch(r'/rooms/(\d+)/?', parsed.path)
    return 'airbnb:' + match[1] if match else None


class LodgingEvidence:
    def __init__(self, history=()):
        self.records = {}
        self.revision = 0
        for message in history:
            if message.get('role') == 'tool':
                self.ingest(message.get('content', ''))

    def ingest(self, content):
        try:
            packet = json.loads(content)
        except (ValueError, TypeError):
            return
        if not isinstance(packet, dict) or packet.get('error'):
            return
        data = packet.get('data', {})
        legacy_packet = isinstance(data, dict) and data.get('source') == 'Airbnb public page' and packet.get('remote_tool') in {'airbnb_search','airbnb_listing_details'}
        if packet.get('model_adapter') != 'openbnb' and not legacy_packet:
            return
        if 'data' not in packet and isinstance(packet.get('text'), str):
            # Scoped immutable memory contains raw tool results, even after history compaction.
            from .openbnb import pack_result
            self.ingest(pack_result(packet, 6000))
            return
        data = packet.get('data', {})
        source_id = packet.get('id')
        if not isinstance(data, dict) or not isinstance(source_id, str):
            return
        if packet.get('remote_tool') == 'airbnb_search':
            rows = data.get('results', [])
            if not isinstance(rows, list):
                return
            observations = [(row.get('url'), {'candidate': row}) for row in rows if isinstance(row, dict)]
        elif packet.get('remote_tool') == 'airbnb_listing_details':
            observations = [(data.get('listing_url'), {'sections': data.get('sections', []),
                'missing_sections': data.get('missing_sections', []),
                'omitted_sections': data.get('omitted_sections', [])})]
        else:
            return
        for url, observation in observations:
            key = listing_key(url)
            if not key:
                continue
            record = self.records.setdefault(key, {'listing_key': key, 'url': url, 'observations': {}})
            observed = {'source_id': source_id,
                'observed_at': packet.get('observed_at'), 'request_context': packet.get('request_context', {}),
                'price_conditions_verified': False, **observation}
            if record['observations'].get(source_id) != observed:
                record['observations'][source_id] = observed
                self.revision += 1

    def read(self, key=None, *, max_bytes=6000):
        if key is None:
            result = {'content_kind': 'lodging_evidence_index', 'listings': [], 'omitted_count': 0}
            for item in self.records.values():
                row = {k: item[k] for k in ('listing_key', 'url')}
                row['source_ids'] = list(item['observations'])
                result['listings'].append(row)
                if len(canonical(result).encode()) > max_bytes - 60:
                    result['listings'].pop()
                    result['omitted_count'] += 1
            return result
        if key not in self.records:
            raise ValueError('No observed listing with this listing_key; call without listing_key to list known properties')
        item = self.records[key]
        result = {'content_kind': 'lodging_evidence', 'listing_key': key, 'url': item['url'],
            'guidance': 'Only this listing. Observations are separate sources/conditions, not independent verification. Missing is unknown, not unavailable. Not included remains excluded.',
            'observations': [], 'omitted_source_ids': [], 'omitted_source_count': 0}
        # Most recent observations first; never splice an oversized source into a partial fact.
        for observation in reversed(list(item['observations'].values())):
            result['observations'].append(observation)
            if len(canonical(result).encode()) > max_bytes - 500:
                result['observations'].pop()
                result['omitted_source_count'] += 1
                if len(result['omitted_source_ids']) < 5:
                    result['omitted_source_ids'].append(observation['source_id'])
        return result
