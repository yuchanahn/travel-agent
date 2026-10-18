"""Capture one Bing HTML response and expose counts before and after top_k.

Raw HTML and complete parsed snippets are private. Packing uses exactly the
captured response, not a second HTTP request or a fresh result substituted for it.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from lxml import html

from travel_agent.web import _request_html, _parse_search_html, _EngineRows, web_search, WebSearchError
from travel_agent.web_context import format_web_result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query',action='append',required=True)
    parser.add_argument('--transport',action='append',choices=['urllib','curl'])
    parser.add_argument('--top-k',type=int,choices=range(1,6),default=3)
    parser.add_argument('--output',type=Path,default=Path('data/private/search-response')/(uuid4().hex+'/report.json'))
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    records=[]
    for query in args.query:
        for transport in args.transport or ['urllib','curl']:
            record={'id':uuid4().hex,'tool':'direct_bing_http_diagnostic','query':query,'transport':transport,
                    'http_params':{'q':query},'top_k':args.top_k,'started_at':datetime.now(timezone.utc).isoformat()}
            try:
                with patch.dict('os.environ',{'WEB_HTTP_TRANSPORT':transport}):
                    text,info=_request_html('bing',query,15)
                (args.output.parent/(record['id']+'.html')).write_text(text,encoding='utf-8')
                tree=html.fromstring(text)
                rows=_parse_search_html(text,'bing')
                main_cards=tree.xpath('//*[@id="b_results"]//li[contains(concat(" ", normalize-space(@class), " "), " b_algo ")]')
                record.update(info,page_title=tree.xpath('string(//title)'),
                              query_inputs=tree.xpath('//input[@name="q"]/@value'),
                              main_result_cards=len(main_cards),
                              **rows.details,parsed_rows=list(rows))
                selected=_EngineRows(rows[:args.top_k],{**info,**rows.details,'selected_results':len(rows[:args.top_k]),
                                                       'not_selected_results':len(rows)-len(rows[:args.top_k])})
                with patch('travel_agent.web._provider_search',return_value=selected):
                    packed=web_search(query,top_k=args.top_k,provider='http',backend='bing')
                record.update(packed_from_same_response=packed,model_content=format_web_result(packed,'compact_md'))
            except (WebSearchError,OSError,ValueError) as exc:
                record['error']={'type':type(exc).__name__,**getattr(exc,'details',{})}
            record['finished_at']=datetime.now(timezone.utc).isoformat()
            records.append(record)
            args.output.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({key:value for key,value in record.items() if key not in {'parsed_rows','packed_from_same_response','model_content'}},ensure_ascii=True),flush=True)
    return 1 if any('error' in record for record in records) else 0


if __name__=='__main__':
    raise SystemExit(main())
