"""Run the unchanged travel cases against production tools; reuse saved Claude answers.

All requests, HTTP collection records and responses stay private. This does not
invoke Claude Code, create web conversations, or label answers factually correct.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from travel_agent.agent import run_agent
from travel_agent.llm_client import chat as actual_chat, settings
from travel_agent.llm_config import generation_options
from travel_agent.memory import MemoryStore

ROOT = Path(__file__).resolve().parents[1]


def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', action='store_true', help='Preserve every saved result, including failures')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'data/private').resolve()):
        parser.error('Execution evidence must stay inside data/private')
    config_file = ROOT/'data/private/llm-config.json'
    if config_file.is_file():
        os.environ.setdefault('LLM_CONFIG_FILE', str(config_file))
    os.environ.setdefault('MCP_CONFIG_FILE', str(ROOT/'data/private/mcp-servers.json'))
    config = settings()
    options = generation_options()
    if config['provider'] != 'ollama' or config['model'] != 'qwen3.5:4b-q4_K_M':
        parser.error('The fixed comparison requires the existing Ollama qwen3.5:4b-q4_K_M configuration')
    if options != {'num_ctx':65536, 'num_predict':4096, 'temperature':0}:
        parser.error('The fixed comparison requires context65536/output4096/temperature0')
    cases = json.loads((ROOT/'examples/live-harness-cases.json').read_text(encoding='utf-8'))
    reference = json.loads((ROOT/'docs/research/076-agent-results.json').read_text(encoding='utf-8'))
    for case in cases:
        assert case['query'] == next(row['query'] for row in reference if row['case'] == case['id'])
    commit = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    protocol = {'source_commit':commit, 'cases':cases, 'model':config['model'], 'provider':config['provider'],
        'options':options, 'thinking':False, 'max_steps':40, 'max_tool_calls':36, 'timeout':360,
        'completion_protocol':'native', 'document_collection':os.environ.get('WEB_DOCUMENT_COLLECTION','1') == '1',
        'reference':'074 saved Claude runs; exact answers in 076-agent-results.json; not rerun',
        'started_at':datetime.now(timezone.utc).isoformat(), 'manual_review':'pending'}
    output.mkdir(parents=True, exist_ok=args.resume)
    if args.resume:
        frozen = json.loads((output/'protocol.json').read_text(encoding='utf-8'))
        for key in ('source_commit','cases','model','provider','options','document_collection'):
            if frozen[key] != protocol[key]:
                parser.error('Resume must preserve the source, cases and configuration')
    else:
        save(output/'protocol.json', protocol)
    report = []
    for case in cases:
        folder = output/case['id']
        if (folder/'result.json').is_file():
            report.append(json.loads((folder/'result.json').read_text(encoding='utf-8')))
            continue
        if folder.exists():
            parser.error('Interrupted case directory exists; preserve it and use a new output directory')
        folder.mkdir()
        requests = []
        def observed(messages, **kwargs):
            requests.append({'messages':json.loads(json.dumps(messages)), 'tools':kwargs.get('tools',[])})
            save(folder/'model-inputs.json', requests)
            reply = actual_chat(messages, **kwargs)
            requests[-1]['reply'] = reply
            save(folder/'model-inputs.json', requests)
            return reply
        print('START '+case['id'], flush=True)
        with MemoryStore(folder/'memory.sqlite3') as store, patch('travel_agent.agent.provider_chat', side_effect=observed):
            result = run_agent(store,'synthetic','fixed-eval',case['query'],mode='bm25',
                max_steps=40,max_tool_calls=36,timeout=360,completion_protocol='native',trace_dir=folder/'traces')
        record = {'case':case['id'], 'query':case['query'], 'result':result}
        save(folder/'result.json', record)
        report.append(record)
        save(output/'report.json', report)
        print(json.dumps({'case':case['id'], **{k:result.get(k) for k in
            ('status','model_calls','tool_calls','elapsed_seconds','error')}}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
