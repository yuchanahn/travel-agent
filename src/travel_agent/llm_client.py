"""Provider boundary; keep native tool calls and never silently change models."""
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .llm_config import generation_options


def settings():
    config = {}
    if not os.environ.get('LLM_PROVIDER'):
        path = Path(os.environ.get('LLM_CONFIG_FILE', ''))
        if path.is_file():
            config = json.loads(path.read_text(encoding='utf-8'))
    provider = os.environ.get('LLM_PROVIDER', config.get('provider', 'ollama'))
    if provider not in {'ollama', 'openai'}:
        raise ValueError('LLM_PROVIDER must be ollama or openai')
    return {'provider': provider,
            'model': os.environ.get('LLM_MODEL', config.get('model', os.environ.get('OLLAMA_MODEL', 'qwen3.5:4b-q4_K_M'))),
            'base_url': os.environ.get('LLM_BASE_URL', config.get('base_url', os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434'))).rstrip('/'),
            'key_file': os.environ.get('LLM_API_KEY_FILE', config.get('key_file', ''))}


def headers(config):
    result = {'Content-Type': 'application/json'}
    key = os.environ.get('LLM_API_KEY', '')
    if not key and config['key_file']:
        key = Path(config['key_file']).read_text(encoding='utf-8').strip()
    if key:
        result['Authorization'] = 'Bearer ' + key
    return result


def openai_messages(messages):
    """Convert saved Ollama history, including calls that originally lacked IDs."""
    result, pending = [], []
    for index, message in enumerate(messages):
        item = {'role': message['role'], 'content': message.get('content') or ''}
        if message.get('tool_calls'):
            item['tool_calls'] = []
            for number, call in enumerate(message['tool_calls']):
                function = call['function']
                call_id = call.get('id') or f'call_{index}_{number}'
                arguments = function['arguments']
                item['tool_calls'].append({'id': call_id, 'type': 'function', 'function': {
                    'name': function['name'], 'arguments': arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False)}})
                pending.append((call_id, function['name']))
        if message['role'] == 'tool':
            call_id = message.get('tool_call_id')
            if not call_id:
                call_id = next((key for key, name in pending if name == message.get('tool_name')), None)
            if not call_id:
                raise ValueError('Tool result has no matching call ID')
            item['tool_call_id'] = call_id
            pending = [(key, name) for key, name in pending if key != call_id]
        result.append(item)
    return result


def chat(messages, *, model, base_url, timeout, tools):
    config = settings()
    options = generation_options()
    if config['provider'] == 'ollama':
        body = {'model': model, 'messages': messages, 'tools': tools, 'stream': False,
                'think': False, 'options': options}
        endpoint = '/api/chat'
    else:
        body = {'model': model, 'messages': openai_messages(messages), 'stream': False,
                'max_tokens': options['num_predict'], 'temperature': options['temperature']}
        if tools:
            body['tools'] = tools
        endpoint = '/chat/completions'
    request = Request(base_url + endpoint, data=json.dumps(body, ensure_ascii=False).encode('utf-8'), headers=headers(config))
    started=time.monotonic()
    for attempt in (1,2):
        try:
            with urlopen(request, timeout=max(.001,timeout-(time.monotonic()-started))) as response:
                data = json.load(response)
            break
        except HTTPError as exc:
            # Retry only a transient model HTTP failure; no tools have executed.
            # Keep the same model/provider and original wall-clock budget.
            exc.llm_http_attempts=attempt
            if config['provider']!='openai' or attempt==2 or exc.code not in {502,503,504} or timeout-(time.monotonic()-started)<=1:
                raise
            exc.close()
            time.sleep(.5)
    if config['provider'] == 'ollama':
        return data
    try:
        choice = data['choices'][0]
        message = dict(choice['message'])
        message['content'] = message.get('content') or ''
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError('Malformed chat completion response') from exc
    usage = data.get('usage') or {}
    return {'message': message, 'done_reason': choice.get('finish_reason'),
            'prompt_eval_count': usage.get('prompt_tokens'), 'eval_count': usage.get('completion_tokens'),
            'response_model': data.get('model'), 'provider': 'openai','http_attempts':attempt}
