"""Export safe excerpts from explicitly selected synthetic real capture runs."""

import argparse
import json
from pathlib import Path
import re


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()
                if k.lower() not in {'authorization', 'cookie', 'set-cookie', 'thinking', 'reasoning'}}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, str):
        return re.sub(r'(?i)(;jsessionid=)[^/?\s"\\]+', r'\1[REDACTED]', value)
    return value


def excerpt(value, limit=1100):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return {'text': text[:limit], 'total_chars': len(text), 'shown_chars': min(len(text), limit)}


def load_run(folder):
    traces = list(folder.glob('traces/*.jsonl'))
    if len(traces) != 1:
        raise ValueError('Expected exactly one trace for an explicitly selected run')
    rows = [json.loads(line) for line in traces[0].read_text(encoding='utf-8').splitlines()]
    starts = [r for r in rows if r['kind'] == 'model_start']
    if not starts:
        raise ValueError('No actual model input')
    query = next(m['content'] for m in reversed(starts[0]['messages']) if m['role'] == 'user')
    user_inputs = [m['content'] for m in starts[0]['messages'] if m['role'] == 'user']
    if any(not text.removeprefix('현재 요약:\n\n질문:\n').startswith('공개 캡처용') for text in user_inputs):
        raise ValueError('Refuse to export a non-synthetic personal run')
    events = []
    labels = {'model_start': '모델 입력', 'model_end': '모델 응답', 'tool_start': '도구 요청',
              'tool_end': '도구 반환', 'tool_message_prepared': '모델 전달 준비',
              'context_checked': 'Context 검사', 'search_selection': '검색 선별', 'run_end': '종료'}
    for r in rows:
        if r['kind'] in labels:
            events.append({k: r[k] for k in ('sequence', 'kind', 'step', 'timestamp', 'name',
                                            'tool_call_id', 'span', 'elapsed_seconds') if k in r}
                          | {'label': labels[r['kind']]})
    tools = []
    for r in rows:
        if r['kind'] != 'tool_start':
            continue
        end = next((e for e in rows if e['kind'] in {'tool_end', 'tool_error'}
                    and e.get('span') == r.get('span')), {})
        result = end.get('result', {})
        if r['name'].startswith('mcp_'):
            blocks = result.get('raw_result', {}).get('content', [])
            first = next((b.get('text', '') for b in blocks if b.get('type') == 'text'), '')
            preview = first or json.dumps(result, ensure_ascii=False)
        else:
            preview = json.dumps(result, ensure_ascii=False, indent=2)
        tools.append({'name': r['name'], 'call_id': r.get('tool_call_id'), 'span': r.get('span'),
                      'start_sequence': r['sequence'], 'end_sequence': end.get('sequence'),
                      'arguments': r.get('arguments'), 'result': excerpt(preview, 1300),
                      'result_id': result.get('id'), 'is_error': end.get('kind') == 'tool_error'})
    requests = []
    for r in starts:
        messages = []
        for m in r['messages']:
            item = {'role': m['role'], 'tool_call_id': m.get('tool_call_id')}
            if m['role'] == 'system':
                item['content'] = {'text': '제품 지침 원문은 이 열람 화면에서 접음',
                                   'total_chars': len(m.get('content', '')), 'shown_chars': 0}
            else:
                item['content'] = excerpt(m.get('content', ''), 1050)
            if m.get('tool_calls'):
                item['tool_calls'] = m['tool_calls']
            if m['role'] == 'tool':
                try:
                    packet = json.loads(m.get('content', ''))
                except (ValueError, TypeError):
                    packet = {}
                item['packet_fields'] = list(packet) if isinstance(packet, dict) else []
                item['hits'] = packet.get('hits', [])[:1] if isinstance(packet, dict) else []
            messages.append(item)
        check = next((e for e in rows if e['kind'] == 'context_checked' and e.get('step') == r['step']), {})
        requests.append({'step': r['step'], 'sequence': r['sequence'], 'input_bytes': r.get('input_bytes'),
                         'messages': messages, 'context': {k: check.get(k) for k in
                         ('before_bytes', 'target_bytes', 'trigger_bytes', 'hard_limit_bytes',
                          'compacted', 'summary_model_calls') if k in check}})
    return clean({'run_id': folder.name, 'request_id': rows[0]['request_id'], 'query': query,
                  'events': events, 'tools': tools, 'requests': requests})


def build(data_dir, run_ids, output):
    runs = [load_run(data_dir / run_id) for run_id in run_ids]
    output.mkdir(parents=True, exist_ok=True)
    (output / 'data.json').write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding='utf-8')
    return output / 'data.json'



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=Path('data/private/web-host'))
    parser.add_argument('--runs', nargs='+', required=True)
    parser.add_argument('--output', type=Path, default=Path('artifacts/portfolio-107-records'))
    args = parser.parse_args()
    print(build(args.data_dir, args.runs, args.output))
