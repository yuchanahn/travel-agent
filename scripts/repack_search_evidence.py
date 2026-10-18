"""Compare packing on exactly the same downloaded pages, without HTTP or LLMs."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from travel_agent.web_pipeline import pack_digest

TERMS={'museum':['09:00','18:00','월요일'],
       'rainy':['부모님','걷'],
       'technical':['TaskGroup','CancelledError','ExceptionGroup']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture',type=Path)
    parser.add_argument('--output',type=Path,default=Path('data/private/search-pipeline/035-repacked.json'))
    args=parser.parse_args()
    cases=json.loads((args.capture/'summary.json').read_text(encoding='utf-8'))
    result={'id':uuid4().hex,'tool':'offline_repack','started_at':datetime.now(timezone.utc).isoformat(),
            'network_requests':0,'model_invoked':False,'cases':[]}
    for case in cases:
        directory=args.capture/case['request_id']
        captured=json.loads((directory/'report.json').read_text(encoding='utf-8'))
        sources=captured['sources']
        for source in sources:
            key=sha256(source['url'].encode()).hexdigest()[:16]
            file=directory/f'page-{key}.md'
            if source['content_kind']=='page_excerpt' and file.exists():
                source['_page_text']=file.read_text(encoding='utf-8')
        # Retain identical header/byte budget; isolate only the packing change.
        header=json.loads(captured['digest'].splitlines()[1])
        header.pop('query',None)
        header.pop('verified_current',None)
        digest,delivered=pack_digest(captured['query'],sources,6000,header)
        terms=TERMS[case['id']]
        def present(text):
            return {term:term in text for term in terms}
        by_url={s['url']:s for s in delivered}
        details=[]
        for source in sources:
            after=by_url.get(source['url'],{})
            details.append({'url':source['url'],'content_kind':source['content_kind'],
                            'in_extracted_page':present(source.get('_page_text',source['text'])),
                            'before':present(source['delivered_text']),
                            'after':present(after.get('delivered_text','')),
                            'before_text':source['delivered_text'],'after_text':after.get('delivered_text','')})
        entry={'case':case['id'],'query':case['query'],'original_request_id':case['request_id'],
               'before_bytes':len(captured['digest'].encode()),'after_bytes':len(digest.encode()),
               'before':present('\n'.join(s['delivered_text'] for s in sources)),
               'after':present('\n'.join(s['delivered_text'] for s in delivered)),
               'sources':details,'digest':digest}
        result['cases'].append(entry)
        print(json.dumps({k:v for k,v in entry.items() if k not in {'sources','digest'}},ensure_ascii=True))
    result['finished_at']=datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
