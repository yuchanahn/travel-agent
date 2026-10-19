"""Small local Claude Code vs travel harness pilot, with identical synthetic MCP data.

No live web searches, downloads, user conversations or production config edits.
Reports and SDK transcripts stay under data/private. This is not a blind benchmark.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OLLAMA = 'http://127.0.0.1:11434'
SOURCE = 'qwen3.5:4b-q4_K_M'
PROFILE = 'travel-harness-072:latest'
LIMIT = 8


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def api(path, data=None, method=None):
    request = Request(OLLAMA + path, data=None if data is None else json.dumps(data).encode(),
                      headers={'Content-Type': 'application/json'}, method=method)
    with urlopen(request, timeout=180) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def fixture(tool, args, case):
    """Entire synthetic evidence is fixed before either harness runs."""
    if tool == 'search_stays':
        return {'synthetic': True, 'location': '가평', 'results': [
            {'id': 'A', 'name': '솔빛집 A'}, {'id': 'B', 'name': '달빛집 B'}],
            'note': '목록은 상세 시설·날짜·가격을 검증하지 않는다. read_stay로 확인한다.'}
    key = args.get('listing_id')
    if tool != 'read_stay' or key not in {'A', 'B'}:
        raise ValueError('Unknown fixture listing or tool')
    result = {'synthetic': True, 'id': key, 'name': '솔빛집 A' if key == 'A' else '달빛집 B',
              'address': '경기도 가평군 (합성 주소)',
              'facilities': ['수영장', '바비큐'] if key == 'A' else ['바비큐'],
              'excluded_facilities': [] if key == 'A' else ['수영장'],
              'booking_availability_verified': False, 'checkout_total_verified': False}
    if case == 'price-conditions':
        result['display_price'] = {'KRW': 190000 if key == 'A' else 280000,
            'checkin': '2026-12-05' if key == 'A' else '2026-11-14',
            'checkout': '2026-12-06' if key == 'A' else '2026-11-15',
            'adults': 4 if key == 'A' else 2, 'fees_included': 'unknown'}
    return result


def serve(args):
    from mcp.server import MCPServer
    server = MCPServer('frozen-travel-comparison', version='1', log_level='ERROR')
    log = Path(args.log)
    calls = 0
    lock = threading.Lock()

    def call(name, arguments):
        nonlocal calls
        with lock:
            calls += 1
            if calls > LIMIT:
                raise ValueError('Comparison tool budget exhausted')
            result = fixture(name, arguments, args.case)
            with log.open('a', encoding='utf-8') as out:
                out.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
                    'ordinal': calls, 'name': name, 'arguments': arguments,
                    'result': result}, ensure_ascii=False) + '\n')
            return json.dumps(result, ensure_ascii=False)

    @server.tool()
    def search_stays(location: str) -> str:
        """Search synthetic lodging candidates; read_stay provides facility and price evidence."""
        return call('search_stays', {'location': location})

    @server.tool()
    def read_stay(listing_id: str) -> str:
        """Read synthetic lodging details for an ID returned by search_stays (A or B)."""
        return call('read_stay', {'listing_id': listing_id})

    server.run()


@contextmanager
def observed_endpoint(folder):
    """Forward native Anthropic requests to loopback Ollama; never convert protocols.

    Sampling/thinking/output overrides are deliberate experimental controls.
    Credentials are not forwarded or recorded. No other upstream is possible.
    """
    records = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            path = urlsplit(self.path).path
            if path != '/v1/messages':
                with (folder/'rejected-paths.jsonl').open('a', encoding='utf-8') as log:
                    log.write(json.dumps({'path': self.path}) + '\n')
                self.send_error(404)
                return
            if len(records) >= LIMIT:
                self.send_error(429, 'comparison model budget exhausted')
                return
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if body.get('model') != PROFILE:
                self.send_error(400, 'unexpected model')
                return
            original = {k: body.get(k) for k in ('max_tokens', 'temperature', 'thinking')}
            body.update(max_tokens=4096, temperature=0, thinking={'type': 'disabled'})
            record = {'time': datetime.now(timezone.utc).isoformat(), 'incoming_path': self.path,
                      'original_controls': original, 'forwarded_request': body}
            records.append(record)
            save(folder/'http.json', records)
            req = Request(OLLAMA+'/v1/messages', data=json.dumps(body).encode(),
                headers={'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'})
            try:
                with urlopen(req, timeout=150) as response:
                    self.send_response(response.status)
                    self.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    chunks = []
                    while chunk := response.read1(65536):
                        chunks.append(chunk)
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    record['response'] = b''.join(chunks).decode('utf-8', errors='replace')
                record['loaded_models'] = api('/api/ps')
            except (OSError, HTTPError) as exc:
                record['error'] = type(exc).__name__
            finally:
                save(folder/'http.json', records)
                self.close_connection = True
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', records
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run_claude(folder, case, command=None, *, minimal=False, mcp_config=None,
               allowed_tools=None, timeout=180):
    config = mcp_config or {'mcpServers': {'fixture': {'command': sys.executable, 'args': command}}}
    save(folder/'mcp.json', config)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('ANTHROPIC_', 'CLAUDE_'))}
    env.update(ANTHROPIC_API_KEY='ollama', ANTHROPIC_AUTH_TOKEN='ollama',
        CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', CLAUDE_CODE_MAX_OUTPUT_TOKENS='4096',
        MAX_THINKING_TOKENS='0', CLAUDE_CONFIG_DIR=str(folder/'claude-config'))
    with observed_endpoint(folder) as (endpoint, records):
        env['ANTHROPIC_BASE_URL'] = endpoint
        cmd = [shutil.which('claude'), *(['--bare'] if minimal else []), '--restricted', '--tools', '',
            '--strict-mcp-config', '--mcp-config', str(folder/'mcp.json'),
            '--allowedTools', *(allowed_tools or ['mcp__fixture__search_stays', 'mcp__fixture__read_stay']),
            '--permission-mode', 'dontAsk', '--disable-slash-commands', '--setting-sources', '',
            '--no-session-persistence', '--model', PROFILE, '--output-format', 'stream-json',
            '--verbose', '--max-turns', str(LIMIT), '-p', case['query']]
        process = subprocess.Popen(cmd, cwd=folder, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            (folder/'stdout.jsonl').write_text(stdout, encoding='utf-8')
            (folder/'stderr.txt').write_text(stderr, encoding='utf-8')
            events = [json.loads(line) for line in stdout.splitlines() if line.startswith('{')]
            final = next((e for e in reversed(events) if e.get('type') == 'result'), {})
            return {'exit_code': process.returncode, 'answer': final.get('result', ''),
                'status': 'api_error' if final.get('is_error') else final.get('subtype', 'no_result'), 'model_calls': len(records),
                'reported_usage': final.get('usage'), 'permission_denials': final.get('permission_denials'),
                'stop_reason': final.get('stop_reason')}
        except subprocess.TimeoutExpired:
            # Kill only this owned CLI and its MCP children, not other Claude sessions.
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
            else:
                process.kill()
            stdout, stderr = process.communicate(timeout=10)
            (folder/'stdout.jsonl').write_text(stdout, encoding='utf-8')
            (folder/'stderr.txt').write_text(stderr, encoding='utf-8')
            return {'status': 'timeout', 'answer': '', 'model_calls': len(records)}


def run_travel(folder, case, command):
    from travel_agent.agent import run_agent
    from travel_agent.memory import MemoryStore
    from travel_agent.mcp_client import MCPRegistry
    # Empty memory + web disabled means the MCP's two tools are the only exposed tools.
    server = {'id': 'fixture', 'transport': 'stdio', 'command': sys.executable,
        'args': command, 'allowed_tools': ['search_stays', 'read_stay']}
    with tempfile.TemporaryDirectory(dir=folder) as scratch:
        with MemoryStore(Path(scratch)/'memory.sqlite3') as store, MCPRegistry([server]) as registry:
            if len(registry.tools) != 2:
                raise RuntimeError('MCP discovery failed')
            result = run_agent(store, 'synthetic', 'harness', case['query'], mode='bm25',
                enable_web=False, max_steps=LIMIT, max_tool_calls=LIMIT,
                timeout=180, trace_dir=folder/'traces', mcp_registry=registry)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--log')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--minimal-claude', action='store_true', help='Calibration only: --bare changes the default system prompt')
    args = parser.parse_args()
    if args.serve:
        serve(args)
        return
    private = (ROOT/'data/private').resolve()
    folder = args.output.resolve() if args.output else private/'harness-072-pilot'
    if not folder.is_relative_to(private):
        parser.error('Output must be private')
    folder.mkdir(parents=True, exist_ok=False)
    cases = json.loads((ROOT/'examples/harness-cases.json').read_text(encoding='utf-8'))
    tags = api('/api/tags')['models']
    if not any(m['name'] == SOURCE for m in tags) or any(m['name'] == PROFILE for m in tags):
        raise ValueError('Source must exist and temporary profile must not exist')
    protocol = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'claude_version': subprocess.check_output(['claude', '--version'], text=True).strip(),
        'ollama_version': api('/api/version'), 'source_model': SOURCE, 'profile': PROFILE,
        'controls': {'context': 65536, 'output': 4096, 'temperature': 0, 'thinking': False,
                     'model_limit': LIMIT, 'tool_limit': LIMIT, 'timeout': 180},
        'cases': cases, 'repeats': 1, 'order': ['travel', 'claude', 'claude', 'travel'],
        'claude_mode': 'bare' if args.minimal_claude else 'standard-with-restricted-tools',
        'scope': 'Two synthetic tasks; native harness prompts/adapters differ; no quality winner inferred.'}
    save(folder/'protocol.json', protocol)
    report = []
    created = False
    old = {k: os.environ.get(k) for k in ('LLM_PROVIDER', 'LLM_MODEL', 'LLM_BASE_URL',
                                         'AGENT_CONTEXT_TOKENS', 'AGENT_MAX_OUTPUT_TOKENS')}
    try:
        api('/api/create', {'model': PROFILE, 'from': SOURCE, 'stream': False,
            'parameters': {'num_ctx': 65536, 'num_predict': 4096, 'temperature': 0}})
        created = True
        for name, tag in [('source', SOURCE), ('profile', PROFILE)]:
            metadata = api('/api/show', {'model': tag})
            save(folder/(name+'-model.json'), {k: metadata.get(k) for k in
                 ('details', 'parameters', 'capabilities', 'model_info')})
        os.environ.update(LLM_PROVIDER='ollama', LLM_MODEL=PROFILE, LLM_BASE_URL=OLLAMA,
                          AGENT_CONTEXT_TOKENS='65536', AGENT_MAX_OUTPUT_TOKENS='4096')
        for i, case in enumerate(cases):
            for harness in (['travel', 'claude'] if i % 2 == 0 else ['claude', 'travel']):
                run = folder/f'{case["id"]}-{harness}'
                run.mkdir()
                command = [str(Path(__file__).resolve()), '--serve', '--case', case['id'], '--log', str(run/'tools.jsonl')]
                start = time.monotonic()
                result = (run_travel(run, case, command) if harness == 'travel' else
                          run_claude(run, case, command, minimal=args.minimal_claude))
                record = {'case': case['id'], 'harness': harness, 'query': case['query'],
                          'elapsed_seconds': round(time.monotonic()-start, 3),
                          'result': result, 'loaded_models': api('/api/ps')}
                record['context_verified'] = any(m.get('name') == PROFILE and m.get('context_length') == 65536
                    for m in record['loaded_models'].get('models', []))
                save(run/'result.json', record)
                report.append(record)
                save(folder/'report.json', report)
                print(json.dumps({'case': case['id'], 'harness': harness,
                    'status': result.get('status'), 'model_calls': result.get('model_calls'),
                    'answer': result.get('answer')}, ensure_ascii=False), flush=True)
    finally:
        if created:
            api('/api/delete', {'model': PROFILE}, method='DELETE')
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        save(folder/'cleanup.json', {'profile_removed': not any(m['name'] == PROFILE for m in api('/api/tags')['models'])})


if __name__ == '__main__':
    main()
