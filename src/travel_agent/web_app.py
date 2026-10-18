"""Loopback-only development UI over the real agent; requests are independent."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
from threading import BoundedSemaphore, Lock
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen
from uuid import uuid4

from .agent import run_agent
from .brave_provider import api_key
from .llm_config import generation_options
from .memory import MemoryStore

STATIC = Path(__file__).with_name('static')
RUN_ID = re.compile(r'[a-f0-9]{32}')


def now():
    return datetime.now(timezone.utc).isoformat()


def public_result(result):
    return {key:value for key,value in result.items() if key != 'trace_path'}


def visible_event(event):
    """Expose observable actions, never model inputs or hidden thinking."""
    kind=event['kind']
    view={key:event[key] for key in ('sequence','timestamp','kind','step','name','span','tool_call_id') if key in event}
    if kind=='model_start':
        view['input_bytes']=event.get('input_bytes')
    elif kind=='model_end':
        message=event.get('message',{})
        view.update(content=message.get('content',''),proposed_tools=len(message.get('tool_calls',[])),
                    prompt_tokens=event.get('prompt_tokens'),output_tokens=event.get('output_tokens'))
    elif kind=='model_error':
        view.update(error=event.get('error'),error_type=event.get('error_type'))
    elif kind=='tool_start':
        view['arguments']=event.get('arguments')
    elif kind in {'tool_end','tool_error'}:
        view['result']=event.get('result')
        view['elapsed_seconds']=event.get('elapsed_seconds_call')
    elif kind in {'citation_repair','evidence_review'}:
        view['feedback']=event.get('feedback')
    elif kind=='tool_budget_finalization':
        view.update(requested=event.get('requested'),remaining=event.get('remaining'))
    else:
        return None
    return view


class RunManager:
    def __init__(self, directory):
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        self.lock=Lock()
        self.slots=BoundedSemaphore(3)
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='agent-ui')
        self.jobs={}
        for path in sorted(self.directory.glob('*/run.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]:
            if not RUN_ID.fullmatch(path.parent.name):
                continue
            try:
                job=json.loads(path.read_text(encoding='utf-8'))
                if job['id']!=path.parent.name:
                    continue
                if job['state'] in {'queued','running'}:
                    job.update(state='interrupted',error='서버 재시작으로 실행이 중단됐습니다.')
                self.jobs[job['id']]=job
            except (OSError,ValueError,KeyError):
                continue

    def _save(self,job):
        folder=self.directory/job['id']
        folder.mkdir(parents=True,exist_ok=True)
        temporary=folder/'run.tmp'
        temporary.write_text(json.dumps(job,ensure_ascii=False),encoding='utf-8')
        temporary.replace(folder/'run.json')

    def submit(self,query,enable_web):
        if not isinstance(query,str) or not query.strip() or len(query)>4000 or type(enable_web) is not bool:
            raise ValueError('질문은1~4000자, 웹검색 설정은 true/false여야 합니다.')
        if not self.slots.acquire(blocking=False):
            raise RuntimeError('실행 대기열이 가득 찼습니다. 현재 요청이 끝난 뒤 다시 보내주세요.')
        job={'id':uuid4().hex,'query':query.strip(),'enable_web':enable_web,'state':'queued','created_at':now()}
        try:
            with self.lock:
                self.jobs[job['id']]=job
                self._save(job)
                completed=[j for j in self.jobs.values() if j['state'] not in {'queued','running'}]
                for old in sorted(completed,key=lambda j:j['created_at'])[:max(0,len(self.jobs)-30)]:
                    self.jobs.pop(old['id'],None)
            self.pool.submit(self._execute,job['id'])
        except Exception:
            self.slots.release()
            with self.lock:
                self.jobs.pop(job['id'],None)
            raise
        return job['id']

    def _execute(self,run_id):
        try:
            with self.lock:
                job=self.jobs[run_id]
                job.update(state='running',started_at=now())
                self._save(job)
            folder=self.directory/run_id
            with MemoryStore(folder/'memory.sqlite3') as store:
                result=run_agent(store,'local-web',run_id,job['query'],mode='bm25',
                                 enable_web=job['enable_web'],trace_dir=folder/'traces',timeout=180)
            with self.lock:
                job.update(state='done',finished_at=now(),result=public_result(result))
                self._save(job)
        except Exception as exc:
            with self.lock:
                self.jobs[run_id].update(state='error',finished_at=now(),
                                         error='실행 중 오류가 발생했습니다: '+type(exc).__name__)
                self._save(self.jobs[run_id])
        finally:
            self.slots.release()

    def summaries(self):
        with self.lock:
            return [{k:j[k] for k in ('id','query','state','created_at')}
                    for j in sorted(self.jobs.values(),key=lambda j:j['created_at'],reverse=True)]

    def snapshot(self,run_id,after=0):
        with self.lock:
            if run_id not in self.jobs:
                raise KeyError(run_id)
            result=dict(self.jobs[run_id])
        events=[]
        sequence=after
        for path in (self.directory/run_id/'traces').glob('*.jsonl'):
            for line in path.read_text(encoding='utf-8').splitlines():
                try:
                    event=json.loads(line)
                except ValueError:  # An append may still be in progress.
                    continue
                if event['sequence']>after:
                    sequence=max(sequence,event['sequence'])
                    projected=visible_event(event)
                    if projected:
                        events.append(projected)
        result.update(events=events,next_sequence=sequence)
        return result


def health():
    model=os.environ.get('OLLAMA_MODEL','qwen3.5:4b-q4_K_M')
    try:
        host=os.environ.get('OLLAMA_BASE_URL','http://127.0.0.1:11434').rstrip('/')
        with urlopen(host+'/api/tags',timeout=3) as response:
            data=json.load(response)
        ollama={'connected':True,'model_installed':any(m.get('name')==model for m in data.get('models',[]))}
    except Exception:
        ollama={'connected':False,'model_installed':False}
    try:
        api_key()
        configured=True
    except Exception:
        configured=False
    return {'status':'ok','model':model,'ollama':ollama,'brave_configured':configured,
            'options':generation_options(),'independent_requests':True}


def handler_for(manager):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass  # User queries and secrets do not enter container access logs.

        def _allowed(self):
            try:
                host=self.headers.get('Host','')
                parsed=urlsplit('http://'+host)
                if parsed.hostname not in {'localhost','127.0.0.1','::1'} or parsed.username or parsed.password or parsed.path:
                    return False
                parsed.port  # Reject malformed ports.
                origin=self.headers.get('Origin')
                return origin is None or origin=='http://'+host
            except ValueError:
                return False

        def _send(self,status,value,kind='application/json; charset=utf-8'):
            body=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._allowed():
                return self._send(403,{'error':'로컬 화면에서만 접근할 수 있습니다.'})
            path=urlsplit(self.path)
            if path.path=='/api/health':
                return self._send(200,health())
            if path.path=='/api/runs':
                return self._send(200,{'runs':manager.summaries()})
            if path.path.startswith('/api/runs/'):
                run_id=path.path.removeprefix('/api/runs/')
                if not RUN_ID.fullmatch(run_id):
                    return self._send(404,{'error':'실행을 찾을 수 없습니다.'})
                try:
                    after=int(parse_qs(path.query).get('after',['0'])[0])
                    if after<0:raise ValueError()
                    return self._send(200,manager.snapshot(run_id,after))
                except ValueError:
                    return self._send(400,{'error':'잘못된 조회 위치입니다.'})
                except KeyError:
                    return self._send(404,{'error':'실행을 찾을 수 없습니다.'})
            files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
            if path.path in files:
                name,kind=files[path.path]
                return self._send(200,(STATIC/name).read_bytes(),kind)
            return self._send(404,{'error':'페이지를 찾을 수 없습니다.'})

        def do_POST(self):
            if not self._allowed():
                return self._send(403,{'error':'로컬 화면에서만 요청할 수 있습니다.'})
            if self.path!='/api/runs':
                return self._send(404,{'error':'페이지를 찾을 수 없습니다.'})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self._send(415,{'error':'JSON 요청만 지원합니다.'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=32768:
                    return self._send(413,{'error':'질문이 너무 큽니다.'})
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict) or set(payload)-{'query','enable_web'}:
                    raise ValueError()
                run_id=manager.submit(payload.get('query'),payload.get('enable_web',True))
                return self._send(202,{'id':run_id})
            except (ValueError,UnicodeError):
                return self._send(400,{'error':'질문과 웹검색 설정을 확인해주세요.'})
            except RuntimeError as exc:
                return self._send(429,{'error':str(exc)})
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--data-dir',type=Path,default=Path('data/private/web'))
    args=parser.parse_args()
    manager=RunManager(args.data_dir)
    server=ThreadingHTTPServer((args.host,args.port),handler_for(manager))
    try:
        server.serve_forever()
    finally:
        server.server_close()
        manager.pool.shutdown(wait=True)


if __name__=='__main__':
    main()
