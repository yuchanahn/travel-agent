"""Compare real travel tools vs Claude Code's configured Brave web-search MCP.

Only the Claude settings entry for Brave is read. No global settings are changed.
Native MCP wire traffic and native model HTTP are retained privately, without auth.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

import compare_harnesses as common

ROOT = common.ROOT
PROFILE = 'travel-harness-073:latest'
NODE = Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'


def relay(folder):
    """Transparent stdio relay: retain JSON-RPC IDs, results and arrival times."""
    config = json.loads((folder/'server.json').read_text(encoding='utf-8'))
    env = dict(os.environ)
    env.update(config.get('env', {}))
    lock = threading.Lock()
    count = 0

    def record(direction, message, **extra):
        with lock, (folder/'wire.jsonl').open('a', encoding='utf-8') as log:
            log.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
                'direction': direction, 'message': message, **extra}, ensure_ascii=False)+'\n')

    with (folder/'server-stderr.txt').open('ab') as err:
        child = subprocess.Popen([config['command'], *config.get('args', [])],
            env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        def read_output():
            for line in child.stdout:
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeError):
                    record('server_non_json', {'bytes': len(line)})
                    continue
                record('server_to_client', message)
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            for line in sys.stdin.buffer:
                message = json.loads(line)
                if message.get('method') == 'tools/call':
                    count += 1
                record('client_to_server', message, call_count=count)
                if message.get('method') == 'tools/call' and count > 20:
                    reply = {'jsonrpc': '2.0', 'id': message.get('id'), 'result': {
                        'isError': True, 'content': [{'type': 'text', 'text': 'Experiment tool budget exhausted'}]}}
                    record('relay_to_client', reply)
                    sys.stdout.buffer.write(json.dumps(reply).encode()+b'\n')
                    sys.stdout.buffer.flush()
                    continue
                child.stdin.write(line)
                child.stdin.flush()
        finally:
            child.stdin.close()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.terminate()
                child.wait(timeout=5)
            reader.join(timeout=5)


def configured_server(entrypoint):
    source = Path.home()/'.claude/settings.json'
    config = json.loads(source.read_text(encoding='utf-8-sig'))['mcpServers']['brave-search']
    if '@brave/brave-search-mcp-server' not in config.get('args', []):
        raise ValueError('Unexpected Claude Brave MCP package')
    key = config.get('env', {}).get('BRAVE_API_KEY', '')
    if not key:
        raise ValueError('Configured Claude Brave key missing')
    return {'command': str(NODE), 'args': [str(entrypoint), '--transport', 'stdio'],
        'env': {'BRAVE_API_KEY': key, 'BRAVE_MCP_ENABLED_TOOLS': 'brave_web_search'}}


def run_travel(folder, query):
    from travel_agent.agent import run_agent
    from travel_agent.memory import MemoryStore
    from travel_agent.llm_client import chat as actual_chat
    from unittest.mock import patch
    requests = []
    def observed_chat(messages, **kwargs):
        requests.append({'time': datetime.now(timezone.utc).isoformat(),
            'messages': json.loads(json.dumps(messages)), 'tools': kwargs.get('tools', [])})
        common.save(folder/'model-inputs.json', requests)
        reply = actual_chat(messages, **kwargs)
        requests[-1]['reply'] = reply
        common.save(folder/'model-inputs.json', requests)
        return reply
    # Normal production tools, including the configured OpenBnB registry, are kept.
    with tempfile.TemporaryDirectory(dir=folder) as scratch:
        with MemoryStore(Path(scratch)/'memory.sqlite3') as store:
            with patch('travel_agent.agent.provider_chat', side_effect=observed_chat):
                return run_agent(store, 'synthetic', 'live-harness', query, mode='bm25',
                    max_steps=24, max_tool_calls=20, timeout=180, trace_dir=folder/'traces')


def main():
    # Detached Windows jobs can default to cp949 even when logs are UTF-8 files.
    # Console progress must never invalidate an already saved comparison slot.
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--relay', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--entrypoint', type=Path)
    parser.add_argument('--resume', action='store_true', help='Keep completed slots and retain interrupted directories')
    parser.add_argument('--harness', choices=['both','travel','claude'], default='both')
    args = parser.parse_args()
    if args.relay:
        relay(args.relay.resolve())
        return
    if not args.output or not args.entrypoint:
        parser.error('Specify new private --output and installed Brave --entrypoint')
    folder = args.output.resolve()
    if not folder.is_relative_to((ROOT/'data/private').resolve()):
        parser.error('Reports must stay private')
    folder.mkdir(parents=True, exist_ok=args.resume)
    server = configured_server(args.entrypoint.resolve())
    package = args.entrypoint.resolve().parent.parent/'package.json'
    version = json.loads(package.read_text(encoding='utf-8'))['version']
    cases = json.loads((ROOT/'examples/live-harness-cases.json').read_text(encoding='utf-8'))
    common.PROFILE = PROFILE
    common.LIMIT = 24
    tags = common.api('/api/tags')['models']
    if any(m['name'] == PROFILE for m in tags):
        raise ValueError('Temporary model profile already exists')
    protocol = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'cases': cases, 'repeats': 1, 'order': [h for h in ['travel', 'claude', 'claude', 'travel'] if args.harness in {'both', h}],
        'harness_selection': args.harness,
        'model': common.SOURCE, 'profile': PROFILE, 'context': 65536, 'output': 4096,
        'temperature': 0, 'thinking': False, 'model_limit': 24, 'tool_limit': 20, 'timeout': 180,
        'claude': {'version': subprocess.check_output(['claude', '--version'], text=True).strip(),
            'package': '@brave/brave-search-mcp-server', 'package_version': version,
            'only_tool': 'brave_web_search', 'source': 'existing Claude settings entry'},
        'travel': 'Configured production travel tools + web_read; empty new memory. Exact schemas in trace.',
        'scope': 'End-to-end stacks; different real tools, not a pure harness causal comparison'}
    if args.resume:
        frozen = json.loads((folder/'protocol.json').read_text(encoding='utf-8'))
        if frozen['cases'] != cases or frozen['model'] != common.SOURCE or frozen.get('harness_selection','both') != args.harness:
            raise ValueError('Resume must preserve cases and model')
        report = json.loads((folder/'report.json').read_text(encoding='utf-8'))
    else:
        common.save(folder/'protocol.json', protocol)
        report = []
    old = dict(os.environ)
    created = False
    try:
        common.api('/api/create', {'model': PROFILE, 'from': common.SOURCE, 'stream': False,
            'parameters': {'num_ctx': 65536, 'num_predict': 4096, 'temperature': 0}})
        created = True
        os.environ.update(LLM_PROVIDER='ollama', LLM_MODEL=PROFILE, LLM_BASE_URL=common.OLLAMA,
            AGENT_CONTEXT_TOKENS='65536', AGENT_MAX_OUTPUT_TOKENS='4096',
            WEB_SEARCH_PROVIDER='brave', WEB_SEARCH_BACKEND='brave',
            MCP_CONFIG_FILE=str(ROOT/'data/private/mcp-servers.json'))
        # Use the existing project credential, without exporting its value into reports.
        os.environ['BRAVE_API_KEY_FILE'] = str(ROOT/'data/private/brave-api-key')
        for i, case in enumerate(cases):
            for harness in (['travel', 'claude'] if i % 2 == 0 else ['claude', 'travel']):
                if args.harness not in {'both', harness}:
                    continue
                if any(r['case'] == case['id'] and r['harness'] == harness for r in report):
                    continue
                run = folder/f'{case["id"]}-{harness}'
                attempt = 1
                while run.exists():
                    attempt += 1
                    run = folder/f'{case["id"]}-{harness}-attempt{attempt}'
                run.mkdir()
                start = time.monotonic()
                if harness == 'claude':
                    common.save(run/'server.json', server)
                    config = {'mcpServers': {'brave-search': {'command': sys.executable,
                        'args': [str(Path(__file__).resolve()), '--relay', str(run)]}}}
                    result = common.run_claude(run, case, mcp_config=config,
                        allowed_tools=['mcp__brave-search__brave_web_search'])
                else:
                    result = run_travel(run, case['query'])
                record = {'case': case['id'], 'harness': harness, 'query': case['query'], 'directory': run.name,
                    'result': result, 'elapsed_seconds': round(time.monotonic()-start, 3),
                    'loaded_models': common.api('/api/ps')}
                common.save(run/'result.json', record)
                report.append(record)
                common.save(folder/'report.json', report)
                print(json.dumps({'case': case['id'], 'harness': harness,
                    'status': result.get('status'), 'answer': result.get('answer')}, ensure_ascii=False), flush=True)
    finally:
        if created:
            common.api('/api/delete', {'model': PROFILE}, method='DELETE')
        os.environ.clear()
        os.environ.update(old)
        common.save(folder/'cleanup.json', {'profile_removed': not any(m['name'] == PROFILE
            for m in common.api('/api/tags')['models'])})


if __name__ == '__main__':
    main()
