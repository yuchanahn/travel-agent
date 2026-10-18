"""Repeat locale and session controls; distinguish topic hits from target URLs.

Raw HTML, cookies and complete rows stay local. Public summaries omit cookie
values and request headers. Query text is unchanged for every profile.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import random
from urllib.parse import urlsplit
from uuid import uuid4

from curl_cffi.requests import Session
from curl_cffi.const import CurlHttpVersion
from lxml import html, etree
from travel_agent.web import _parse_search_html, MAX_RESPONSE_BYTES

CASES = [
    {'id':'museum','query':'국립춘천박물관 관람시간 휴관일 교통','language':'ko','country':'kr',
     'target_host':'chuncheon.museum.go.kr','target_path':None,'terms':['춘천','박물관']},
    {'id':'technical','query':'Python asyncio TaskGroup cancellation official documentation','language':'en','country':'us',
     'target_host':'docs.python.org','target_path':'/3/library/asyncio-task.html','terms':['taskgroup','cancel']},
    {'id':'heldout_docker','query':'how to install docker on debian','language':'en','country':'us',
     'target_host':'docs.docker.com','target_path':'/engine/install/debian','terms':['docker','debian']},
    {'id':'heldout_cablecar','query':'춘천 삼악산 호수케이블카 이용요금 셔틀 운행 안내','language':'ko','country':'kr',
     'target_host':'samaksancablecar.com','target_path':None,'terms':['삼악산','케이블카']},
]


def locale_params(case, profile):
    if profile in {'baseline','session'}:
        return {}
    if profile=='rss':
        return {'format':'rss'}
    if profile=='mkt':
        return {'mkt':case['language']+'-'+case['country'].upper()}
    if profile=='setlang':
        return {'setlang':case['language']}
    if profile=='cc':
        return {'setlang':case['language'],'cc':case['country']}
    if profile=='safe_locale':
        return {'setlang':case['language'],**({'cc':case['country']} if case['country'] not in {'us','cn','ru'} else {})}
    raise ValueError('Unknown profile')


def summarize(events):
    groups=defaultdict(list)
    for event in events:
        groups[(event['case'],event['profile'])].append(event)
    return [{'case':case,'profile':profile,'requests':len(rows),
             'http_200':sum(r.get('http_status')==200 for r in rows),
             'nonempty':sum(bool(r.get('rows')) for r in rows),
             'topic_hit_requests':sum(r.get('topic_hits',0)>0 for r in rows),
             'target_hit_requests':sum(bool(r.get('target_found')) for r in rows),
             'top3_topic_hits':[r.get('top3_topic_hits',0) for r in rows],
             'ordered_url_variants':len({tuple(x['href'] for x in r.get('rows',[])) for r in rows})}
            for (case,profile),rows in groups.items()]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats',type=int,choices=range(1,6),default=3)
    parser.add_argument('--output',type=Path,default=Path('data/private/search-pipeline/036-variance')/uuid4().hex)
    parser.add_argument('--rss-only',action='store_true',help='Probe the same Bing search endpoint in RSS format')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    randomizer=random.Random(20261018)
    sessions={c['id']:Session(impersonate='edge101') for c in CASES[:2]}
    events=[]
    try:
        for repetition in range(args.repeats):
            jobs=[(c,p) for c in CASES for p in (['rss'] if args.rss_only else
                  ['baseline','mkt','setlang','cc','session'] if not c['id'].startswith('heldout') else ['baseline','safe_locale'])]
            randomizer.shuffle(jobs)
            for case,profile in jobs:
                event={'id':uuid4().hex,'tool':'bing_variance_http','case':case['id'],'profile':profile,
                       'repetition':repetition+1,'arguments':{'q':case['query'],**locale_params(case,profile)},
                       'session_policy':'reuse_per_case' if profile=='session' else 'new',
                       'started_at':datetime.now(timezone.utc).isoformat()}
                session=sessions[case['id']] if profile=='session' else Session(impersonate='edge101')
                try:
                    event['cookie_names_before']=sorted(set(session.cookies.keys()))
                    response=session.get('https://www.bing.com/search',params=event['arguments'],timeout=12,allow_redirects=False)
                    event.update(http_status=response.status_code,response_bytes=len(response.content),
                                 http_version=response.http_version,
                                 http_version_name=CurlHttpVersion(response.http_version).name,
                                 response_headers={k:response.headers[k] for k in ['date','age','vary','content-language','cache-control','x-cache','via'] if k in response.headers},
                                 cookie_names_after=sorted(set(session.cookies.keys())))
                    if response.status_code!=200 or len(response.content)>MAX_RESPONSE_BYTES:
                        event['error']='http_status_or_size'
                    else:
                        text=response.content.decode('utf-8',errors='replace')
                        (args.output/(event['id']+('.xml' if profile=='rss' else '.html'))).write_text(text,encoding='utf-8')
                        if profile=='rss':
                            tree=etree.fromstring(response.content,parser=etree.XMLParser(resolve_entities=False,no_network=True))
                            rows=[{'title':item.findtext('title') or '', 'href':item.findtext('link') or '',
                                   'body':item.findtext('description') or ''} for item in tree.findall('./channel/item')]
                            info={'result_cards':len(rows),'parsed_results':len(rows)}
                            page_title=tree.findtext('./channel/title')
                            query_inputs=[]
                        else:
                            tree=html.fromstring(text)
                            rows=_parse_search_html(text,'bing')
                            info=rows.details
                            page_title=tree.xpath('string(//title)')
                            query_inputs=tree.xpath('//input[@name="q"]/@value')
                        def topic(row):
                            content=(row['title']+' '+row['body']).lower()
                            return all(term in content for term in case['terms'])
                        def target(row):
                            p=urlsplit(row['href'])
                            return p.hostname.removeprefix('www.')==case['target_host'] and (case['target_path'] is None or p.path.rstrip('/')==case['target_path'].rstrip('/'))
                        event.update(info,rows=list(rows),page_title=page_title,query_inputs=query_inputs,
                                     topic_hits=sum(topic(r) for r in rows),top3_topic_hits=sum(topic(r) for r in rows[:3]),
                                     target_found=any(target(r) for r in rows),
                                     target_ranks=[i for i,r in enumerate(rows,1) if target(r)])
                except Exception as exc:
                    event['error']=type(exc).__name__
                finally:
                    if profile!='session':
                        session.close()
                event['finished_at']=datetime.now(timezone.utc).isoformat()
                events.append(event)
                report={'seed':20261018,'repeats':args.repeats,'cases':CASES,'events':events,'summary':summarize(events),
                        'note':'One host and short time window; repeated requests share IP history. Topic markers are not semantic relevance labels.'}
                (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps({k:event[k] for k in ['case','profile','repetition','http_status','topic_hits','target_found','error'] if k in event},ensure_ascii=True),flush=True)
    finally:
        for session in sessions.values():
            session.close()
    print('private_report='+str(args.output/'report.json'))
    print(json.dumps(summarize(events),ensure_ascii=True))


if __name__=='__main__':
    main()
