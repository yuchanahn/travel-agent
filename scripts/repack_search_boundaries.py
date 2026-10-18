"""Compare saved search packets using the same extracted text; no HTTP or LLM."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from travel_agent.evidence_text import body_signal
from travel_agent.web_pipeline import pack_digest


def repack(path):
    report=json.loads(path.read_text(encoding='utf-8'))
    sources, raw_text = [], {}
    for original in report['sources']:
        source=dict(original)
        md=path.parent/('page-'+sha256(source['url'].encode()).hexdigest()[:16]+'.md')
        if source['content_kind']=='page_excerpt':
            # Fail visibly instead of quietly comparing an old excerpt as if
            # it were the complete extracted text.
            text=md.read_text(encoding='utf-8')
            source['_page_text']=text
            source['body_signal']=body_signal(text)
            raw_text[source['url']]=text
        sources.append(source)
    fields=('collected','groups','shortlisted','response_format','locale','stop_reason',
            'retrieval_complete','ranking','min_query_coverage','evidence_status','facts_synthesized','provider')
    metadata={key:report[key] for key in fields if key in report}
    digest,new=pack_digest(report['query'],sources,6000,metadata)
    comparisons=[]
    for old in report['sources']:
        now=next((s for s in new if s['url']==old['url']),None)
        text=raw_text.get(old['url'])
        comparisons.append({'url':old['url'],'body_signal':now.get('body_signal') if now else None,
                            'before':old['delivered_text'],'after':now['delivered_text'] if now else None,
                            'verbatim_segments':all(part in text for part in now['delivered_text'].split('\n\n')) if now and text else None})
    return {'query':report['query'],'capture_id':report['id'],'network_calls':0,'model_invoked':False,
            'before_bytes':report['digest_bytes'],'after_bytes':len(digest.encode()),
            'before_count':len(report['sources']),'after_count':len(new),'comparisons':comparisons,'digest':digest,
            'comparison_scope':'Previously delivered sources only; no new retrieval or candidate reranking',
            'max_bytes':6000}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports',type=Path,nargs='+')
    parser.add_argument('--output',type=Path,default=Path('data/private/search-pipeline/043-boundaries'))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    summary=[]
    for path in args.reports:
        entry=repack(path)
        summary.append(entry)
        (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in entry.items() if k not in {'comparisons','digest'}},ensure_ascii=True))


if __name__=='__main__':
    main()
