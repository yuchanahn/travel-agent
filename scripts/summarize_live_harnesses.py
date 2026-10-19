"""Join model requests, real MCP executions and following model inputs by IDs.

Detailed generated summaries stay private. Publication requires manual selection
and redaction; this script never labels a final answer factually correct.
"""
import argparse
import json
from pathlib import Path


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def byte_size(value):
    return len((value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)).encode('utf-8'))


def anthropic_response_stats(response):
    """Read public usage/stop metadata, never infer hidden reasoning."""
    usage = {}
    stop = None
    for line in response.splitlines():
        if not line.startswith('data: '):
            continue
        event = json.loads(line[6:])
        if event.get('type') == 'message_start':
            usage.update(event.get('message', {}).get('usage', {}))
        if event.get('type') == 'message_delta':
            usage.update(event.get('usage', {}))
            stop = event.get('delta', {}).get('stop_reason', stop)
    return {'usage': usage, 'stop_reason': stop}


def claude_summary(folder):
    wire = jsonl(folder/'wire.jsonl')
    stream = jsonl(folder/'stdout.jsonl')
    http = json.loads((folder/'http.json').read_text(encoding='utf-8'))
    requested = []
    for event in stream:
        message = event.get('message', {})
        blocks = message.get('content', [])
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if isinstance(block, dict) and block.get('type') == 'tool_use':
                requested.append({'id': block['id'], 'name': block['name'],
                    'arguments': block['input'], 'time': event.get('timestamp')})
    calls = []
    used = set()
    for record in wire:
        request = record['message']
        if record['direction'] != 'client_to_server' or request.get('method') != 'tools/call':
            continue
        params = request['params']
        native_id = params.get('_meta', {}).get('claudecode/toolUseId')
        matches = [i for i, item in enumerate(requested) if i not in used and
            (item['id'] == native_id if native_id else
             item['name'].endswith('__'+params['name']) and item['arguments'] == params.get('arguments', {}))]
        index = matches[0] if matches else None
        if index is not None:
            used.add(index)
        model = requested[index] if index is not None else None
        response = next((r for r in wire if r['direction'] in {'server_to_client', 'relay_to_client'}
            and r['message'].get('id') == request.get('id')), None)
        deliveries = []
        for n, transaction in enumerate(http, 1):
            for message in transaction['forwarded_request'].get('messages', []):
                blocks = message.get('content', [])
                if not isinstance(blocks, list):
                    continue
                for block in blocks:
                    if isinstance(block, dict) and block.get('type') == 'tool_result' and model and block.get('tool_use_id') == model['id']:
                        deliveries.append({'model_call': n, 'packet': block,
                            'content_bytes': byte_size(block.get('content', ''))})
        calls.append({'model_requested': model, 'mcp_request_id': request.get('id'),
            'started_at': record['time'], 'server_reply': response,
            'next_model_delivery': deliveries[0] if deliveries else None})
    init = next((e for e in stream if e.get('type') == 'system' and e.get('subtype') == 'init'), {})
    return {'available_tools': init.get('tools'), 'calls': calls,
        'unmatched_model_calls': [r for i, r in enumerate(requested) if i not in used],
        'model_calls': len(http),
        'model_steps': [{'step': n, 'request_bytes': byte_size(r['forwarded_request']),
            **anthropic_response_stats(r.get('response', ''))} for n, r in enumerate(http, 1)]}


def travel_summary(folder):
    traces = list((folder/'traces').glob('*.jsonl'))
    if len(traces) != 1:
        raise ValueError('Expected one travel trace')
    trace = jsonl(traces[0])
    inputs = json.loads((folder/'model-inputs.json').read_text(encoding='utf-8'))
    calls = []
    for start in [e for e in trace if e['kind'] == 'tool_start']:
        span = start['span']
        end = next((e for e in trace if e['kind'] in {'tool_end', 'tool_error'} and e.get('span') == span), None)
        prepared = next((e for e in trace if e['kind'] == 'tool_message_prepared' and e.get('span') == span), None)
        delivery = None
        # span step.index corresponds to the ordered native tool-results batch.
        # Find the immediate following model call, not the last repeated history.
        step = start['step']
        if step < len(inputs):
            packets = [m for m in inputs[step]['messages'] if m.get('role') == 'tool']
            index = int(span.split('.')[1])-1
            batch_size = sum(e['kind'] == 'tool_start' and e.get('step') == step for e in trace)
            batch = packets[-batch_size:] if batch_size else []
            if index < len(batch):
                delivery = {'model_call': step+1, 'packet': batch[index],
                    'content_bytes': byte_size(batch[index].get('content', ''))}
        calls.append({'model_requested': {'id': start.get('tool_call_id'),
            'span': span, 'name': start['name'], 'arguments': start['arguments']},
            'started_at': start['timestamp'], 'server_reply': end,
            'prepared': prepared, 'next_model_delivery': delivery})
    return {'available_tools': [t['function']['name'] for t in trace[0]['tools']],
        'calls': calls, 'model_calls': sum(e['kind'] == 'model_start' for e in trace),
        'model_steps': [{'step': e['step'], 'stop_reason': e.get('done_reason'),
            'output_tokens': e.get('output_tokens'), 'input_tokens': e.get('prompt_tokens'),
            'tool_calls': len(e.get('message', {}).get('tool_calls', []))}
            for e in trace if e['kind'] == 'model_end']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    folder = args.folder.resolve()
    root = Path(__file__).resolve().parents[1]
    if not folder.is_relative_to((root/'data/private').resolve()):
        parser.error('Input/output must stay private')
    report = json.loads((folder/'report.json').read_text(encoding='utf-8'))
    for run in report:
        directory = folder/run.get('directory', f'{run["case"]}-{run["harness"]}')
        try:
            result = (claude_summary if run['harness'] == 'claude' else travel_summary)(directory)
        except FileNotFoundError:
            result = {'trace_unavailable': True}
        (directory/'joined.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(run['case'], run['harness'], 'calls', len(result.get('calls', [])),
            'delivered', sum(bool(c.get('next_model_delivery')) for c in result.get('calls', [])))


if __name__ == '__main__':
    main()
