"""Host-configured MCP clients; schemas are discovered, not reimplemented."""
from contextlib import ExitStack
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone

from .memory import canonical
from .evidence_text import bounded_prefix


def load_servers(path=None):
    explicit = path is not None or bool(os.environ.get('MCP_CONFIG_FILE'))
    path = Path(path or os.environ.get('MCP_CONFIG_FILE','data/private/mcp-servers.json'))
    if not path.exists():
        if explicit:
            raise ValueError('Configured MCP file was not found')
        return []
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    servers = config.get('servers',[])
    if not isinstance(servers,list) or len(servers)>3:
        raise ValueError('MCP config must contain at most 3 servers')
    resolved = []
    seen = set()
    for item in servers:
        if item.get('enabled',True) is False:
            continue
        name = item.get('id','')
        if not re.fullmatch('[a-z][a-z0-9_]{0,15}',name) or name in seen:
            raise ValueError('MCP server IDs must be unique lowercase names up to 16 characters')
        seen.add(name)
        allowed = item.get('allowed_tools')
        if not isinstance(allowed,list) or not allowed or not all(isinstance(t,str) and t for t in allowed):
            raise ValueError('Each MCP server requires an explicit allowed_tools list')
        if item.get('transport') not in {'stdio','streamable_http'}:
            raise ValueError('MCP transport must be stdio or streamable_http')
        copy = dict(item)
        for field in ('env_files','header_files'):
            values = {}
            for key, filename in item.get(field,{}).items():
                source = Path(filename)
                if not source.is_absolute():
                    source = path.parent/source
                values[key] = source.read_text(encoding='utf-8-sig').strip()
                if not values[key]:
                    raise ValueError('MCP credential file is empty')
            copy['_env' if field=='env_files' else '_headers'] = values
        resolved.append(copy)
    return resolved


def _check_schema(schema):
    from jsonschema.validators import validator_for
    # Resolve local schema definitions only; discovery cannot cause remote fetches.
    def walk(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k in {'$ref','$dynamicRef'} and (not isinstance(v,str) or not v.startswith('#')):
                    raise ValueError('External JSON Schema references are not supported')
                walk(v)
        elif isinstance(value,list):
            for v in value: walk(v)
    walk(schema)
    validator_for(schema).check_schema(schema)


class MCPRegistry:
    def __init__(self, servers=None, *, targets=None):
        self.servers = load_servers() if servers is None else servers
        self.targets = targets or {}  # In-process SDK servers for protocol tests.
        self.tools = []
        self.routes = {}
        self.adapters = {}
        self.status = []
        self._secrets = [value for s in self.servers for field in ('_env','_headers') for value in s.get(field,{}).values() if value]
        self._stack = ExitStack()

    def __enter__(self):
        if not self.servers:
            return self
        try:
            from anyio.from_thread import start_blocking_portal
            from mcp import Client, StdioServerParameters
            from mcp.client.streamable_http import streamable_http_client
            import httpx2
            self.portal = self._stack.enter_context(start_blocking_portal())
            for server in self.servers:
                sid = server['id']
                # Failed discovery is visible; no fabricated tool schemas.
                try:
                    target = self.targets.get(sid)
                    if target is None and server['transport']=='stdio':
                        from mcp import stdio_client
                        log_dir=Path('data/private/mcp-logs')
                        log_dir.mkdir(parents=True,exist_ok=True)
                        target = stdio_client(StdioServerParameters(command=server['command'],
                            args=server.get('args',[]), cwd=server.get('cwd'),env=server.get('_env',{})),
                            errlog=self._stack.enter_context((log_dir/(sid+'.stderr.log')).open('a',encoding='utf-8')))
                    elif target is None:
                        from urllib.parse import urlsplit
                        url = urlsplit(server['url'])
                        if url.username or url.password or url.query or url.fragment or url.scheme not in {'http','https'}:
                            raise ValueError('MCP URL must not contain credentials, query or fragment')
                        if url.scheme=='http' and url.hostname not in {'localhost','127.0.0.1','::1','host.docker.internal'}:
                            raise ValueError('Remote MCP endpoints require HTTPS')
                        http = self._stack.enter_context(self.portal.wrap_async_context_manager(
                            httpx2.AsyncClient(headers=server.get('_headers',{}),timeout=15)))
                        target = streamable_http_client(server['url'],http_client=http)
                    client = self._stack.enter_context(self.portal.wrap_async_context_manager(
                        Client(target,read_timeout_seconds=15)))
                    found = []
                    cursor = None
                    cursors = set()
                    for _ in range(10):
                        page = self.portal.call(self._list,client,cursor)
                        found.extend(page.tools)
                        cursor = page.next_cursor
                        if cursor is None: break
                        if cursor in cursors: raise ValueError('MCP pagination cycle')
                        cursors.add(cursor)
                    else:
                        raise ValueError('MCP discovery page limit')
                    selected = [t for t in found if t.name in server['allowed_tools']]
                    if set(server['allowed_tools']) != {t.name for t in selected}:
                        raise ValueError('Configured tool was not discovered')
                    additions = []
                    for tool in selected:
                        schema = tool.input_schema
                        _check_schema(schema)
                        alias = f'mcp_{sid}_{tool.name}'
                        if len(alias)>64 or not re.fullmatch('[a-zA-Z0-9_]+',alias):
                            alias=f'mcp_{sid}_{hashlib.sha256(tool.name.encode()).hexdigest()[:12]}'
                        if alias in self.routes or any(a[0]==alias for a in additions):
                            raise ValueError('MCP tool alias collision')
                        additions.append((alias,tool,schema))
                    if len(self.tools)+len(additions)>24:
                        raise ValueError('MCP exposed tool limit is 24')
                    for alias,tool,schema in additions:
                        self.routes[alias] = (client,sid,tool.name,schema)
                        self.adapters[alias] = server.get('adapter')
                        if server.get('adapter')=='openbnb':
                            import copy
                            from .openbnb import GUIDANCE
                            schema=copy.deepcopy(schema)
                            schema.get('properties',{}).pop('ignoreRobotsText',None)
                            description=GUIDANCE+' '+(tool.description or tool.name)
                        else:
                            description=tool.description or tool.name
                        self.tools.append({'type':'function','function':{'name':alias,
                            'description':f'MCP server {sid}: '+description,
                            'parameters':schema}})
                    self.status.append({'server':sid,'transport':server['transport'],'status':'connected',
                                        'discovered':len(found),'exposed':len(additions)})
                except Exception as exc:
                    import traceback
                    log_dir=Path('data/private/mcp-logs')
                    log_dir.mkdir(parents=True,exist_ok=True)
                    with (log_dir/(sid+'.connection.log')).open('a',encoding='utf-8') as diagnostic:
                        diagnostic.write(''.join(traceback.format_exception(exc)))
                    self.status.append({'server':sid,'transport':server['transport'],
                                        'status':'unavailable','error_type':type(exc).__name__})
            return self
        except BaseException:
            self._stack.close()
            raise

    def __exit__(self,*args):
        self._stack.close()

    async def _list(self,client,cursor):
        import anyio
        with anyio.fail_after(15):
            return await client.list_tools(cursor=cursor)

    def validate(self,name,args):
        from jsonschema.validators import validator_for
        if name not in self.routes or not isinstance(args,dict):
            raise ValueError('Unknown MCP tool or malformed arguments')
        schema = self.routes[name][3]
        if self.adapters.get(name)=='openbnb' and 'ignoreRobotsText' in args:
            raise ValueError('OpenBnB request policy is configured by the host')
        try: validator_for(schema)(schema).validate(args)
        except Exception as exc: raise ValueError('MCP arguments do not match discovered schema') from exc

    async def _call(self,client,name,args,timeout):
        import anyio
        with anyio.fail_after(timeout):
            return await client.call_tool(name,args,read_timeout_seconds=timeout)

    def call(self,name,args,*,timeout=15):
        self.validate(name,args)
        client,sid,remote,_ = self.routes[name]
        try:
            reply = self.portal.call(self._call,client,remote,args,timeout)
            wire = reply.model_dump(mode='json',by_alias=True,exclude_none=True)
            from urllib.parse import quote
            serialized = canonical(wire)
            for secret in self._secrets:
                for variant in (secret,quote(secret,safe='')):
                    # Operate on JSON string contents without breaking escaping.
                    serialized = serialized.replace(json.dumps(variant,ensure_ascii=False)[1:-1],'[REDACTED]')
            wire = json.loads(serialized)
            if len(canonical(wire).encode())>1048576:
                raise ValueError('MCP result exceeds storage limit')
            # Binary blocks stay in private raw_result; forward only text or structured JSON.
            blocks = wire.get('content',[])
            text = '\n'.join(b.get('text','') for b in blocks if b.get('type')=='text')
            structured = wire.get('structuredContent')
            if structured is not None: text=canonical(structured)
            if not text and not wire.get('isError'): text='[MCP returned no text content]'
            failed = bool(wire.get('isError')) or wire.get('resultType','complete')!='complete'
            return {'id':'mcp:'+hashlib.sha256(canonical([sid,remote,args,wire]).encode()).hexdigest()[:16],
                    'server':sid,'remote_tool':remote,'content_kind':'mcp_result',
                    'observed_at':datetime.now(timezone.utc).isoformat(),
                    'verified_current':False,'is_error':failed,
                    'text':text,'raw_result':wire,
                    **({'model_adapter':'openbnb'} if self.adapters.get(name)=='openbnb' else {}),
                    **({'error':'MCP server error or unsupported input request'} if failed else {})}
        except Exception as exc:
            # Exception strings can contain request URLs or credentials.
            raise RuntimeError('MCP call failed: '+type(exc).__name__) from None


def model_result(result,max_bytes=6000):
    """Bound the model packet while keeping the full result in private trace."""
    if max_bytes < 256:
        raise ValueError('MCP packet budget must be at least 256 bytes')
    if result.get('model_adapter')=='openbnb':
        from .openbnb import pack_result
        return pack_result(result,max_bytes)
    packed = {k:v for k,v in result.items() if k not in {'raw_result','text'}}
    overhead = len(canonical({**packed,'text':'','truncated':True}).encode())
    if overhead >= max_bytes:
        return canonical({'error':'MCP metadata exceeds model packet limit','truncated':True})
    text = bounded_prefix(result.get('text',''),max(0,(max_bytes-overhead)//2))
    packed.update(text=text,truncated=text!=result.get('text',''))
    while len(canonical(packed).encode())>max_bytes:
        packed['text']=packed['text'][:len(packed['text'])//2]
        packed['truncated']=True
    return canonical(packed)


def with_mcp(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        if kwargs.get('mcp_registry') is not None:
            return function(*args,**kwargs)
        with MCPRegistry() as registry:
            return function(*args,**kwargs,mcp_registry=registry)
    return wrapped
