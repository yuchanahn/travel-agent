"""Predeclared binary rubric aggregation; no LLM judge or keyword-based fact grading."""


def paired_summary(report, *, require_route_match=False):
    versions = ('baseline', 'current')
    result = {'planned_runs': len(report['schedule']), 'executed_runs': len(report['runs']),
              'complete_pairs': 0, 'reviewed_pairs': 0, 'versions': {}, 'pairs': [],
              'routing_excluded_pairs': 0, 'require_route_match':require_route_match}
    cases = {case['id']: case for case in report['cases']}
    for version in versions:
        runs = [run for run in report['runs'] if run['version'] == version]
        result['versions'][version] = {'attempts': len(runs),
            'completed': sum(run['result'].get('status') == 'completed' for run in runs),
            'errors': sum(run['result'].get('status') != 'completed' for run in runs),
            'model_calls': sum(run['result'].get('model_calls', 0) for run in runs),
            'tool_calls': sum(run['result'].get('tool_calls', 0) for run in runs),
            'prompt_tokens': sum(run['result'].get('prompt_tokens', 0) for run in runs),
            'output_tokens': sum(run['result'].get('output_tokens', 0) for run in runs)}
    for case_id in cases:
        for repeat in range(report['repeats']):
            pair = {r['version']: r for r in report['runs'] if r['case_id'] == case_id and r['repeat'] == repeat}
            if set(pair) != set(versions) or any(r['result'].get('status') != 'completed' for r in pair.values()):
                continue
            result['complete_pairs'] += 1
            if require_route_match:
                routes = {v:{call.get('headers',{}).get('x-routed-via') for call in pair[v].get('http_calls',[]) if call.get('status')==200} for v in versions}
                if any(len(route)!=1 or None in route for route in routes.values()) or routes['baseline']!=routes['current']:
                    result['routing_excluded_pairs'] += 1
                    continue
            rubric = cases[case_id]['rubric']
            reviews = {v: pair[v].get('review', {}) for v in versions}
            if any(set(review) != set(rubric) or any(type(item.get('pass')) is not bool or not item.get('reason')
                    for item in review.values()) for review in reviews.values()):
                continue
            scores = {v: sum(item['pass'] for item in reviews[v].values()) for v in versions}
            result['reviewed_pairs'] += 1
            result['pairs'].append({'case_id': case_id, 'repeat': repeat, 'maximum': len(rubric), **scores,
                'delta': scores['current'] - scores['baseline']})
    result['paired_scores'] = {v: sum(pair[v] for pair in result['pairs']) for v in versions}
    result['paired_maximum'] = sum(pair['maximum'] for pair in result['pairs'])
    result['wins'] = sum(p['delta'] > 0 for p in result['pairs'])
    result['ties'] = sum(p['delta'] == 0 for p in result['pairs'])
    result['losses'] = sum(p['delta'] < 0 for p in result['pairs'])
    result['evaluation_complete'] = (len(report['runs']) == len(report['schedule'])
        and result['reviewed_pairs'] == len(cases) * report['repeats'])
    result['execution_complete'] = len(report['runs']) == len(report['schedule'])
    return result
