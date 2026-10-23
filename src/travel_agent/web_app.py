"""Loopback-only development UI with server-owned conversation continuations."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
from threading import BoundedSemaphore, Lock
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen
from uuid import uuid4

from .agent import run_agent, execute_tool
from .brave_provider import api_key
from .llm_client import settings as llm_settings, headers as llm_headers
from .llm_config import generation_options
from .memory import MemoryStore, build_bm25_index
from .observability import summarize as summarize_trace
from .session_context import compact_context, trace_events, turn_events, write_json

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
    elif kind in {'citation_repair','evidence_review','continuation_requested'}:
        view['feedback']=event.get('feedback')
    elif kind=='completion_signal':
        view.update(forced_by_budget=event.get('forced_by_budget'),stop_reason=event.get('stop_reason'))
    elif kind=='tool_budget_finalization':
        view.update(requested=event.get('requested'),remaining=event.get('remaining'))
    elif kind=='context_prepared':
        view.update({k:v for k,v in event.items() if k not in {'request_id','sequence','timestamp','kind'}})
    elif kind=='memory_recalled':
        view.update(query=event['query'], result=event['result'])
    elif kind=='mcp_discovery':
        view['servers']=event['servers']
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

    def _job(self,run_id):
        if not isinstance(run_id,str) or not RUN_ID.fullmatch(run_id):
            raise ValueError('대화 실행 ID가 올바르지 않습니다.')
        if run_id in self.jobs:
            return self.jobs[run_id]
        try:
            return json.loads((self.directory/run_id/'run.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):
            raise ValueError('이전 대화를 찾을 수 없습니다.')

    def conversation(self,job):
        turns=[]
        seen=set()
        while job:
            if job['id'] in seen or len(seen)>=100:
                raise ValueError('대화 길이 한도에 도달했습니다. 새 대화를 시작해주세요.')
            seen.add(job['id'])
            turns.append({'id':job['id'],'query':job['query'],
                          'answer':job.get('result',{}).get('answer') or job.get('result',{}).get('partial_answer',''),'state':job['state']})
            job=self._job(job['parent_id']) if job.get('parent_id') else None
        return list(reversed(turns))

    def continuation(self,parent):
        checkpoint = self.directory/parent['id']/'context.json'
        if checkpoint.exists():
            return json.loads(checkpoint.read_text(encoding='utf-8'))['history']
        messages=None
        for path in (self.directory/parent['id']/'traces').glob('*.jsonl'):
            for line in path.read_text(encoding='utf-8').splitlines():
                event=json.loads(line)
                if event['kind']=='model_start':
                    messages=event['messages']
        if messages is None:
            raise ValueError('이전 대화의 모델 입력 기록을 찾을 수 없습니다.')
        return [m for m in messages if m['role']!='system']+[
            {'role':'assistant','content':parent['result']['answer']}]

    def can_continue(self, job):
        # Execution success and having a usable conversation checkpoint differ.
        if job['state'] != 'done':
            return False
        try:
            return bool(self.continuation(job))
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def submit(self,query,enable_web,parent_id=None):
        if not isinstance(query,str) or not query.strip() or len(query)>4000 or type(enable_web) is not bool:
            raise ValueError('질문은1~4000자, 웹검색 설정은 true/false여야 합니다.')
        if parent_id is not None:
            with self.lock:
                parent=self._job(parent_id)
                if not self.can_continue(parent):
                    raise ValueError('이전 실행이 끝나고 대화 문맥이 저장된 뒤 이어서 질문해주세요.')
                if len(self.conversation(parent))>=100:
                    raise ValueError('대화 길이 한도에 도달했습니다. 새 대화를 시작해주세요.')
                self.continuation(parent)
        if not self.slots.acquire(blocking=False):
            raise RuntimeError('실행 대기열이 가득 찼습니다. 현재 요청이 끝난 뒤 다시 보내주세요.')
        job={'id':uuid4().hex,'query':query.strip(),'enable_web':enable_web,'state':'queued','created_at':now()}
        if parent_id is not None:
            job['parent_id']=parent_id
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
            parent=self._job(job['parent_id']) if job.get('parent_id') else None
            ancestors = []
            cursor = parent
            while cursor:
                if cursor['id'] in {p['id'] for p in ancestors} or len(ancestors)>=100:
                    raise ValueError('Invalid conversation chain')
                ancestors.append(cursor)
                cursor = self._job(cursor['parent_id']) if cursor.get('parent_id') else None
            ancestors.reverse()
            session = ancestors[0]['id'] if ancestors else run_id
            history = self.continuation(parent) if parent else []
            checkpoint = self.directory/parent['id']/'context.json' if parent else None
            summary = json.loads(checkpoint.read_text(encoding='utf-8'))['summary'] if checkpoint and checkpoint.exists() else ''
            with MemoryStore(folder/'memory.sqlite3') as store:
                # A run gets only its ancestry, never a sibling branch or another chat.
                for ancestor in ancestors:
                    store.add('local-web',session,turn_events(self.directory,ancestor))
                before_index = build_bm25_index(store,'local-web',session)
                history, summary, context = compact_context(history,summary,folder=folder,
                    model=llm_settings()['model'],
                    base_url=llm_settings()['base_url'])
                recalled = execute_tool(store,'local-web',session,'memory_search',
                    {'query':job['query'],'top_k':3},mode='bm25',rerank=False,max_bytes=6000) if summary and before_index['chunks'] else {'hits':[]}
                context.update(memory_events=before_index['events'],memory_chunks=before_index['chunks'],
                               recalled_hits=len(recalled['hits']))
                result=run_agent(store,'local-web',session,job['query'],mode='bm25',summary=summary,
                                 history=history,prior_sources=parent['result'].get('web_sources',[]) if parent else [],
                                 prior_memory_ids=[i for i in parent['result'].get('evidence_ids',[]) if i.startswith(('m-','event:'))] if parent else [],
                                 prior_mcp_sources=parent['result'].get('mcp_sources',[]) if parent else [],
                                 recalled_memory=recalled,context_info=context,
                                 enable_web=job['enable_web'],trace_dir=folder/'traces',timeout=360)
                finished = {**job,'finished_at':now(),'result':result}
                inserted = store.add('local-web',session,turn_events(self.directory,finished))
                after_index = build_bm25_index(store,'local-web',session)
                latest = next((e['messages'] for e in reversed(trace_events(self.directory,job)) if e['kind']=='model_start'),None)
                if latest:
                    saved_history = [m for m in latest if m['role']!='system']
                    # The request wrapper contains summary/retrieval. Preserve the
                    # original user query in the rolling checkpoint instead.
                    saved_history[len(history)] = {'role':'user','content':job['query']}
                else:
                    saved_history = history + [{'role':'user','content':job['query']}]
                answer = result.get('answer') or result.get('partial_answer')
                if answer:
                    saved_history.append({'role':'assistant','content':answer})
                write_json(folder/'context.json',{'history':saved_history,'summary':summary,'session':session})
                context.update(saved_events=inserted,total_events=after_index['events'],total_chunks=after_index['chunks'])
            with self.lock:
                job.update(state='done',finished_at=finished['finished_at'],result=public_result(result),context=context)
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
            chats = {}
            for job in sorted(self.jobs.values(),key=lambda j:j['created_at'],reverse=True):
                turns = self.conversation(job)
                root = turns[0]
                if root['id'] not in chats:
                    chats[root['id']] = {**{k:job[k] for k in ('id','state','created_at')},
                        'query':root['query'], 'conversation_id':root['id'], 'turn_count':len(turns)}
            return list(chats.values())

    def delete_conversation(self, run_id):
        """Delete a whole root and its branches, including uncached disk records."""
        with self.lock:
            root_id=self.conversation(self._job(run_id))[0]['id']
            records={}
            for path in self.directory.glob('*/run.json'):
                if not RUN_ID.fullmatch(path.parent.name):
                    continue
                try:
                    record=json.loads(path.read_text(encoding='utf-8'))
                    if record.get('id')==path.parent.name:
                        records[record['id']]=record
                except (OSError,ValueError):
                    continue
            records.update(self.jobs)
            selected={root_id}
            while True:
                descendants={key for key,job in records.items() if job.get('parent_id') in selected}
                expanded=selected|descendants
                if expanded==selected:
                    break
                selected=expanded
            if any(records.get(key,{}).get('state') in {'queued','running'} for key in selected):
                raise RuntimeError('실행 중이거나 대기 중인 질문이 있습니다. 종료 후 삭제해주세요.')
            root=self.directory.resolve()
            targets=[]
            def depth(key):
                ancestors=set()
                while key!=root_id:
                    if key in ancestors:
                        raise ValueError('Invalid conversation chain')
                    ancestors.add(key)
                    key=records[key]['parent_id']
                return len(ancestors)
            # Leaves first: if a locked file interrupts deletion, surviving
            # records still have their ancestors and the operation can be retried.
            for key in sorted(selected,key=depth,reverse=True):
                if not RUN_ID.fullmatch(key):
                    raise ValueError('Invalid conversation record')
                target=self.directory/key
                if target.is_symlink() or target.is_junction() or target.resolve().parent!=root:
                    raise ValueError('Unsafe conversation path')
                targets.append(target)
            for target in targets:
                if target.exists():
                    shutil.rmtree(target)
                self.jobs.pop(target.name,None)
            return {'conversation_id':root_id,'deleted_ids':sorted(selected),'deleted_count':len(selected)}

    def snapshot(self,run_id,after=0):
        with self.lock:
            if run_id not in self.jobs:
                raise KeyError(run_id)
            result=dict(self.jobs[run_id])
        events=[]
        observed=[]
        sequence=after
        for path in (self.directory/run_id/'traces').glob('*.jsonl'):
            for line in path.read_text(encoding='utf-8').splitlines():
                try:
                    event=json.loads(line)
                except ValueError:  # An append may still be in progress.
                    continue
                observed.append(event)
                if event['sequence']>after:
                    sequence=max(sequence,event['sequence'])
                    projected=visible_event(event)
                    if projected:
                        events.append(projected)
        result.update(events=events,next_sequence=sequence)
        result['execution_summary']=summarize_trace(observed)
        result['conversation']=self.conversation(result)
        result['can_continue']=self.can_continue(result)
        return result


def health():
    config=llm_settings()
    model=config['model']
    try:
        host=config['base_url']
        from urllib.request import Request
        endpoint='/api/tags' if config['provider']=='ollama' else '/models'
        with urlopen(Request(host+endpoint,headers=llm_headers(config)),timeout=3) as response:
            data=json.load(response)
        ollama={'connected':True,'model_installed':any((m.get('name')==model or m.get('id')==model) for m in data.get('models',data.get('data',[])))}
    except Exception:
        ollama={'connected':False,'model_installed':False}
    try:
        api_key()
        configured=True
    except Exception:
        configured=False
    return {'status':'ok','model':model,'provider':config['provider'],'llm':ollama,'ollama':ollama if config['provider']=='ollama' else {'connected':False,'model_installed':False},'brave_configured':configured,
            'options':generation_options(),'independent_requests':False}


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
                allowed = { 'http://'+host }
                # Opt-in exact public origin for a separately authenticated
                # tunnel instance. Host rewriting must still pass the local check.
                origin_file = os.environ.get('WEB_PUBLIC_ORIGIN_FILE')
                if origin_file:
                    public_origin = Path(origin_file).read_text(encoding='utf-8').strip()
                    public = urlsplit(public_origin)
                    if public.scheme == 'https' and public.netloc and not public.path and not public.query and not public.fragment and not public.username:
                        allowed.add(public_origin)
                return origin is None or origin in allowed
            except (ValueError, OSError):
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
            files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/theme.js':('theme.js','text/javascript; charset=utf-8'),'/theme.css':('theme.css','text/css; charset=utf-8')}
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
                if not isinstance(payload,dict) or set(payload)-{'query','enable_web','parent_id'}:
                    raise ValueError()
                run_id=manager.submit(payload.get('query'),payload.get('enable_web',True),payload.get('parent_id'))
                return self._send(202,{'id':run_id})
            except (ValueError,UnicodeError):
                return self._send(400,{'error':'질문과 웹검색 설정을 확인해주세요.'})
            except RuntimeError as exc:
                return self._send(429,{'error':str(exc)})

        def do_DELETE(self):
            if not self._allowed():
                return self._send(403,{'error':'로컬 화면에서만 삭제할 수 있습니다.'})
            path=urlsplit(self.path).path
            prefix='/api/conversations/'
            if not path.startswith(prefix) or not RUN_ID.fullmatch(path[len(prefix):]):
                return self._send(404,{'error':'대화를 찾을 수 없습니다.'})
            try:
                return self._send(200,manager.delete_conversation(path[len(prefix):]))
            except ValueError:
                return self._send(404,{'error':'삭제할 대화를 찾을 수 없습니다.'})
            except RuntimeError as exc:
                return self._send(409,{'error':str(exc)})
            except OSError:
                return self._send(500,{'error':'파일을 삭제하지 못했습니다. 잠시 후 다시 시도해주세요.'})
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
