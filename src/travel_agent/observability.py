"""Summaries of observable trace events; no prompts or document text in output."""
from collections import Counter


def summarize(events):
    starts, finishes, http = {}, {}, {}
    model_starts = model_ends = model_errors = 0
    tokens = {'prompt_tokens': [], 'output_tokens': []}
    final = None
    malformed = 0
    for e in events:
        kind = e.get('kind')
        if kind == 'model_start':
            model_starts += 1
        elif kind == 'model_end':
            model_ends += 1
            for key in tokens:
                tokens[key].append(e.get(key))
        elif kind == 'model_error':
            model_errors += 1
        elif kind == 'tool_start':
            if e.get('span') is None:
                malformed += 1
            else:
                starts[e['span']] = e
        elif kind in ('tool_end', 'tool_error'):
            if e.get('span') is None:
                malformed += 1
            else:
                finishes[e['span']] = e
        elif kind == 'document_collection':
            # These observations are cumulative; repeated snapshots are not new HTTP calls.
            for o in e.get('observations', []):
                http[(o.get('id'), o.get('started_at'))] = o
        elif kind == 'run_end':
            final = e.get('result', {})
    errors = Counter()
    success = cached = 0
    for span, e in finishes.items():
        if span not in starts:
            continue
        result = e.get('result', {})
        failed = e['kind'] == 'tool_error' or bool(result.get('is_error') or result.get('error'))
        if failed:
            if str(result.get('error', '')).startswith('Identical tool call already attempted'):
                category = 'duplicate_rejected'
            elif result.get('http_status') is not None:
                category = 'http_error'
            else:
                category = 'tool_error'
            errors[category] += 1
        else:
            success += 1
            cached += int(bool(result.get('from_document_store')))
    n = len(starts)
    return {
        'status': final.get('status') if final is not None else 'incomplete',
        'elapsed_seconds': final.get('elapsed_seconds') if final is not None else None,
        'model_requests': model_starts, 'model_responses': model_ends, 'model_errors': model_errors,
        'malformed_tool_events': malformed,
        'tool_requests': n, 'tool_successes': success, 'tool_errors': sum(errors.values()),
        'tool_pending': n-success-sum(errors.values()), 'errors_by_type': dict(errors),
        'tool_error_ratio': sum(errors.values())/n if n else None,
        'stored_document_reads': cached,
        'automatic_http_observations': len(http),
        'automatic_http_states': dict(Counter(o.get('status', 'unknown') for o in http.values())),
        **{key: {'reported_sum': sum(v for v in values if v is not None) if any(v is not None for v in values) else None,
                 'reported_calls': sum(v is not None for v in values), 'expected_calls': model_starts,
                 'complete': len(values) == model_starts and all(v is not None for v in values)}
           for key, values in tokens.items()},
    }
