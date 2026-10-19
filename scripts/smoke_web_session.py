"""Synthetic live chat check. Always delete only the conversation it created."""
import argparse
import json
import time
from urllib.request import Request, urlopen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:50733')
    args=parser.parse_args()
    base=args.base_url.rstrip('/')
    def api(path,method='GET',payload=None):
        request=Request(base+path,method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Content-Type':'application/json'})
        with urlopen(request,timeout=10) as response:return json.load(response)
    root=None
    try:
        parent=None
        for query in ['합성 테스트입니다. 여행 인원은 성인 두 명입니다. 검색하지 말고 확인만 해주세요.',
                      '방금 말한 인원은 몇 명인가요? 검색하지 말고 답해주세요.']:
            created=api('/api/runs','POST',{'query':query,'enable_web':False,'parent_id':parent})
            parent=created['id']
            root=root or parent
            deadline=time.monotonic()+200
            while True:
                job=api('/api/runs/'+parent)
                if job['state'] not in {'queued','running'}:break
                if time.monotonic()>=deadline:raise TimeoutError('Live test still running; deletion may need retry')
                time.sleep(.5)
            print(json.dumps({'query':query,'answer':job.get('result',{}).get('answer'),
                             'status':job.get('result',{}).get('status')},ensure_ascii=True))
            if job.get('result',{}).get('status')!='completed':raise RuntimeError('Live chat did not complete')
        assert len(job['conversation'])==2 and job['parent_id']==root
    finally:
        if root:
            deleted=api('/api/conversations/'+root,'DELETE')
            print(json.dumps({'cleanup':deleted},ensure_ascii=True))


if __name__=='__main__':main()
