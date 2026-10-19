"""Represent the same web evidence for a model; full results remain in trace."""
from .memory import canonical

FORMATS = {'full_json', 'compact_json', 'compact_md'}


def compact_result(result):
    if 'error' in result:
        return result
    if result.get('content_kind') == 'page_excerpt':
        return {key: result[key] for key in ('id','title','url','content_kind','page_fetched','verified_current',
                                            'selection_query','truncated','fetched_at','text','body_signal',
                                            'document_token','cache_hit','total_chars','start_index',
                                            'next_start_index','reading_mode','text_is_fragment','boundary_split',
                                            'excerpt_unavailable_reason') if key in result}
    return {key: value for key, value in {
        'status':result.get('status'), 'content_kind':result.get('content_kind'),
        'page_fetched':result.get('page_fetched'), 'searched_at':result.get('searched_at'),
        'engines_returned':result.get('engines_returned'), 'search_complete':result.get('search_complete'),
        'errors':{name:event for name,event in result.get('engine_status', {}).items() if event.get('status') == 'error'},
        'omitted_results':result.get('omitted_results', 0),
        'hits':[{key:hit[key] for key in ('id','title','url','snippet','snippet_truncated') if key in hit}
                for hit in result.get('hits', [])],
    }.items() if value is not None and not (key == 'errors' and not value)}


def format_web_result(result, style='compact_md'):
    if style not in FORMATS:
        raise ValueError('Unknown web tool format')
    if style == 'full_json':
        return canonical(result)
    packed = compact_result(result)
    if style == 'compact_json' or 'error' in packed:
        return canonical(packed)
    if packed.get('content_kind') == 'page_excerpt':
        meta = {key:value for key,value in packed.items() if key not in {'title','url','text'}}
        return canonical(meta)+'\n'+packed['title']+'\n'+packed['url']+'\n'+packed['text']
    meta = {key:value for key,value in packed.items() if key != 'hits'}
    parts = [canonical(meta)]
    for hit in packed['hits']:
        parts.append(f"[{hit['id']}] {hit['title']}\n{hit['url']}\n{hit.get('snippet','')}"
                     + ('\n[snippet truncated]' if hit.get('snippet_truncated') else ''))
    return '\n\n'.join(parts)
