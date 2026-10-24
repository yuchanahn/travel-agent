import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from travel_agent.llm_client import chat, openai_messages, ollama_messages, settings


class ProviderTests(unittest.TestCase):
    def test_ollama_decodes_mixed_saved_arguments_without_changing_original_history(self):
        messages=[{'role':'assistant','content':'','tool_calls':[
            {'id':'a','type':'function','function':{'name':'search','arguments':'{"query":"가평","adults":2}'}},
            {'id':'b','function':{'name':'other','arguments':{'items':[1,2]}}}]},
            {'role':'tool','tool_call_id':'b','tool_name':'other','content':'{"unchanged":true}'},
            {'role':'tool','tool_call_id':'a','tool_name':'search','content':'결과'}]
        original=json.dumps(messages,ensure_ascii=False)
        result=ollama_messages(messages)
        self.assertEqual(result[0]['tool_calls'][0]['function']['arguments'],{'query':'가평','adults':2})
        self.assertEqual(result[1],messages[1])
        result[0]['tool_calls'][1]['function']['arguments']['items'].append(3)
        self.assertEqual(json.dumps(messages,ensure_ascii=False),original)
        self.assertEqual(openai_messages(ollama_messages(messages))[2]['tool_call_id'],'a')

    def test_ollama_request_serializes_saved_openai_arguments_as_objects(self):
        history=[{'role':'assistant','content':'','tool_calls':[{'id':'a','function':{'name':'lookup','arguments':'{"adults":2}'}}]}]
        with patch.dict(os.environ,{'LLM_PROVIDER':'ollama','LLM_API_KEY_FILE':''}), \
                patch('travel_agent.llm_client.urlopen',return_value=io.BytesIO(b'{"message":{"role":"assistant","content":"OK"}}')) as network:
            chat(history,model='local',base_url='http://localhost:11434',timeout=3,tools=[])
        request=network.call_args.args[0]
        self.assertTrue(request.full_url.endswith('/api/chat'))
        body=json.loads(request.data)
        self.assertEqual(body['messages'][0]['tool_calls'][0]['function']['arguments'],{'adults':2})
        self.assertEqual(body['options']['num_ctx'],65536)
        self.assertEqual(body['options']['num_predict'],8192)
        self.assertFalse(body['think'])

    def test_invalid_saved_arguments_are_rejected_before_ollama_network_request(self):
        for arguments in ('broken','[]','null','true',[],None):
            with self.subTest(arguments=arguments),patch.dict(os.environ,{'LLM_PROVIDER':'ollama'}), \
                    patch('travel_agent.llm_client.urlopen') as network:
                with self.assertRaises(ValueError):
                    chat([{'role':'assistant','tool_calls':[{'function':{'name':'x','arguments':arguments}}]}],
                        model='local',base_url='http://localhost:11434',timeout=3,tools=[])
                network.assert_not_called()

    def test_legacy_parallel_call_ids_are_matched_in_reverse_result_order(self):
        messages = [{'role': 'assistant', 'content': '', 'tool_calls': [
            {'function': {'name': name, 'arguments': {'query': name}}} for name in ['a', 'b']]},
            {'role': 'tool', 'tool_name': 'b', 'content': 'B'},
            {'role': 'tool', 'tool_name': 'a', 'content': 'A'}]
        result = openai_messages(messages)
        self.assertEqual(result[1]['tool_call_id'], result[0]['tool_calls'][1]['id'])
        self.assertEqual(result[2]['tool_call_id'], result[0]['tool_calls'][0]['id'])
        self.assertEqual(json.loads(result[0]['tool_calls'][0]['function']['arguments']), {'query': 'a'})
        self.assertNotIn('tool_name', result[1])
        self.assertNotIn('id', messages[0]['tool_calls'][0])

    def test_native_ids_and_invalid_argument_strings_are_preserved_for_harness_validation(self):
        call = {'id': 'call_test', 'type': 'function', 'function': {'name': 'x', 'arguments': 'bad json'}}
        result = openai_messages([{'role': 'assistant', 'content': None, 'tool_calls': [call]},
                                  {'role': 'tool', 'tool_call_id': 'call_test', 'content': '{}'}])
        self.assertEqual(result[0]['tool_calls'][0], call)
        self.assertEqual(result[0]['content'], '')
        with self.assertRaises(ValueError):
            openai_messages([{'role': 'tool', 'content': 'orphan'}])

    def test_openai_request_auth_usage_length_and_null_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = Path(tmp)/'key'
            key.write_text('synthetic-test-key', encoding='utf-8')
            data = {'model': 'resolved-model', 'choices': [{'message': {'role': 'assistant', 'content': None},
                    'finish_reason': 'length'}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 20}}
            with patch.dict(os.environ, {'LLM_PROVIDER': 'openai', 'LLM_API_KEY_FILE': str(key), 'LLM_API_KEY': ''}), \
                    patch('travel_agent.llm_client.urlopen', return_value=io.BytesIO(json.dumps(data).encode())) as network:
                result = chat([], model='fixed-model', base_url='http://localhost/v1', timeout=3, tools=[])
            request = network.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual(request.full_url, 'http://localhost/v1/chat/completions')
            self.assertEqual(request.get_header('Authorization'), 'Bearer synthetic-test-key')
            self.assertNotIn('tools', body)
            self.assertNotIn('options', body)
            self.assertNotIn('think', body)
            self.assertEqual(body['max_tokens'], 8192)
            self.assertEqual(result['done_reason'], 'length')
            self.assertEqual(result['response_model'], 'resolved-model')
            self.assertEqual(result['prompt_eval_count'], 10)
            self.assertEqual(result['eval_count'], 20)
            self.assertEqual(result['message']['content'], '')

    def test_explicit_ollama_ignores_private_config_and_failure_has_no_fallback(self):
        with patch.dict(os.environ, {'LLM_PROVIDER': 'ollama', 'LLM_CONFIG_FILE': 'missing.json'}):
            self.assertEqual(settings()['provider'], 'ollama')
        with patch.dict(os.environ, {'LLM_PROVIDER': 'openai', 'LLM_API_KEY_FILE': ''}), \
                patch('travel_agent.llm_client.urlopen', side_effect=HTTPError('url', 429, 'limit', {}, None)) as network:
            with self.assertRaises(HTTPError):
                chat([], model='fixed', base_url='http://localhost/v1', timeout=1, tools=[])
            self.assertEqual(network.call_count, 1)

    def test_malformed_gateway_response_is_controlled_error(self):
        with patch.dict(os.environ, {'LLM_PROVIDER': 'openai', 'LLM_API_KEY_FILE': ''}), \
                patch('travel_agent.llm_client.urlopen', return_value=io.BytesIO(b'{"choices":[]}')):
            with self.assertRaisesRegex(ValueError, 'Malformed'):
                chat([], model='fixed', base_url='http://localhost/v1', timeout=1, tools=[])

    def test_transient_502_retries_once_same_request_with_remaining_budget(self):
        data={'choices':[{'message':{'role':'assistant','content':'recovered'},'finish_reason':'stop'}]}
        with patch.dict(os.environ,{'LLM_PROVIDER':'openai','LLM_API_KEY_FILE':''}), \
                patch('travel_agent.llm_client.time.sleep'), \
                patch('travel_agent.llm_client.urlopen',side_effect=[HTTPError('url',502,'upstream',{},None),io.BytesIO(json.dumps(data).encode())]) as network:
            result=chat([],model='fixed',base_url='http://localhost/v1',timeout=10,tools=[])
        self.assertEqual(result['http_attempts'],2)
        self.assertEqual(result['message']['content'],'recovered')
        self.assertIs(network.call_args_list[0].args[0],network.call_args_list[1].args[0])
        self.assertLessEqual(network.call_args_list[1].kwargs['timeout'],network.call_args_list[0].kwargs['timeout'])

    def test_repeated_502_stops_at_two_attempts_and_short_budget_does_not_retry(self):
        with patch.dict(os.environ,{'LLM_PROVIDER':'openai','LLM_API_KEY_FILE':''}), \
                patch('travel_agent.llm_client.time.sleep'), \
                patch('travel_agent.llm_client.urlopen',side_effect=lambda *a,**k: (_ for _ in ()).throw(HTTPError('url',502,'upstream',{},None))) as network:
            with self.assertRaises(HTTPError) as failure:
                chat([],model='fixed',base_url='http://localhost/v1',timeout=10,tools=[])
            self.assertEqual(network.call_count,2)
            self.assertEqual(failure.exception.llm_http_attempts,2)
            network.reset_mock()
            with self.assertRaises(HTTPError):chat([],model='fixed',base_url='http://localhost/v1',timeout=.5,tools=[])
            self.assertEqual(network.call_count,1)
