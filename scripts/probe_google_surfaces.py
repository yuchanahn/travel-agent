"""Compare a historical no-JS Google request with two HTTP control surfaces.

Autocomplete and News RSS are controls, NOT substitutes for general web search.
No browser, proxy, external service, retries, or redirect following is used.
"""
import argparse
from datetime import datetime, timezone
import json
from urllib.parse import urlsplit
from uuid import uuid4

from travel_agent.google_http import PRIVATE, parse_page

OPERA_UA = 'Opera/12.02 (Android 4.1; Linux; Opera Mobi/ADR-1111101157; U; en-US) Presto/2.9.201 Version/12.02'


def classify_control(case, body):
    if case == 'autocomplete':
        data = json.loads(body)
        suggestions = data[1] if isinstance(data, list) and len(data)>1 else None
        if not isinstance(suggestions, list) or not all(isinstance(x,str) for x in suggestions):
            raise ValueError('invalid_suggestions')
        return {'kind':'suggestions','count':len(suggestions),'samples':suggestions[:3]}
    from lxml import etree
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    root = etree.fromstring(body, parser=parser)
    if root.tag != 'rss':
        raise ValueError('not_rss')
    items = root.findall('./channel/item')
    return {'kind':'news_articles','count':len(items),
            'samples':[{'title':x.findtext('title'),'url':x.findtext('link')} for x in items[:3]]}


def main():
    from curl_cffi.requests import Session
    from curl_cffi.requests.errors import RequestsError
    from lxml import etree
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', action='append', choices=['whoogle-opera','autocomplete','news-rss'])
    parser.add_argument('--query', default='Python official website')
    args = parser.parse_args()
    folder = PRIVATE/'surface-controls'/uuid4().hex
    folder.mkdir(parents=True)
    report = []
    for case in dict.fromkeys(args.case or ['whoogle-opera','autocomplete','news-rss']):
        if case == 'whoogle-opera':
            url, params = 'https://www.google.com/search', {'q':args.query,'hl':'en','num':5,'gbv':1}
            headers = {'User-Agent':OPERA_UA}
        elif case == 'autocomplete':
            url, params = 'https://www.google.com/complete/search', {'q':args.query,'client':'firefox','hl':'en'}
            headers = {}
        else:
            url, params = 'https://news.google.com/rss/search', {'q':args.query,'hl':'en-US','gl':'US','ceid':'US:en'}
            headers = {}
        row = {'id':case,'started_at':datetime.now(timezone.utc).isoformat(),
               'url':url,'params':params,'general_web_search_success':False}
        try:
            with Session(impersonate='chrome150') as session:
                response = session.get(url, params=params, headers=headers, timeout=15, allow_redirects=False)
            (folder/(case+'.body')).write_bytes(response.content)
            row.update(http_status=response.status_code,bytes=len(response.content),
                       redirect_path=urlsplit(response.headers.get('location','')).path)
            if case == 'whoogle-opera':
                status,hits = parse_page(response.content,response.url,response.status_code)
                row.update(classification=status,hits=hits,general_web_search_success=bool(hits))
            elif response.status_code == 200:
                row['control'] = classify_control(case,response.content)
        except (RequestsError,ValueError,etree.XMLSyntaxError) as exc:
            row['error_type'] = type(exc).__name__
        row['finished_at'] = datetime.now(timezone.utc).isoformat()
        report.append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
        (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if any(x['general_web_search_success'] for x in report) else 1


if __name__ == '__main__':
    raise SystemExit(main())
