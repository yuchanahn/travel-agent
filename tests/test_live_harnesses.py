"""Evidence joins must distinguish tool requests, execution and delivery."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import compare_live_harnesses as live
from summarize_live_harnesses import claude_summary, anthropic_response_stats


class LiveHarnessTests(unittest.TestCase):
    def test_response_usage_is_metadata_not_content_or_cumulative_sum(self):
        response = '\n'.join('data: '+json.dumps(e) for e in [
            {'type': 'message_start', 'message': {'usage': {'input_tokens': 10, 'output_tokens': 0}}},
            {'type': 'content_block_delta', 'delta': {'text': 'not reasoning evidence'}},
            {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'},
             'usage': {'input_tokens': 10, 'output_tokens': 5}}])
        self.assertEqual(anthropic_response_stats(response),
            {'usage': {'input_tokens': 10, 'output_tokens': 5}, 'stop_reason': 'end_turn'})

    def test_brave_settings_selection_does_not_copy_provider_credentials(self):
        with TemporaryDirectory() as name:
            home = Path(name)
            (home/'.claude').mkdir()
            (home/'.claude/settings.json').write_text(json.dumps({'env': {'ANTHROPIC_AUTH_TOKEN': 'not-copied'},
                'mcpServers': {'brave-search': {'args': ['-y', '@brave/brave-search-mcp-server'],
                    'env': {'BRAVE_API_KEY': 'synthetic-test-key'}}}}), encoding='utf-8')
            with patch.object(live.Path, 'home', return_value=home):
                config = live.configured_server(Path('fixture.js'))
            self.assertEqual(set(config['env']), {'BRAVE_API_KEY', 'BRAVE_MCP_ENABLED_TOOLS'})
            self.assertEqual(config['env']['BRAVE_MCP_ENABLED_TOOLS'], 'brave_web_search')

    def test_rpc_execution_and_model_delivery_are_separate(self):
        with TemporaryDirectory() as name:
            folder = Path(name)
            request = {'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call',
                'params': {'name': 'brave_web_search', 'arguments': {'query': 'synthetic'}}}
            reply = {'jsonrpc': '2.0', 'id': 7, 'result': {'content': [{'type': 'text', 'text': 'fixture'}]}}
            wire = [{'time': 'start', 'direction': 'client_to_server', 'message': request},
                    {'time': 'end', 'direction': 'server_to_client', 'message': reply}]
            (folder/'wire.jsonl').write_text('\n'.join(json.dumps(r) for r in wire), encoding='utf-8')
            event = {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'call-one',
                'name': 'mcp__brave-search__brave_web_search', 'input': {'query': 'synthetic'}}]}}
            (folder/'stdout.jsonl').write_text(json.dumps(event), encoding='utf-8')
            (folder/'http.json').write_text(json.dumps([{'forwarded_request': {'messages': []}}]), encoding='utf-8')
            result = claude_summary(folder)
            self.assertEqual(result['calls'][0]['mcp_request_id'], 7)
            self.assertEqual(result['calls'][0]['server_reply']['message'], reply)
            self.assertIsNone(result['calls'][0]['next_model_delivery'])
            delivered = {'type': 'tool_result', 'tool_use_id': 'call-one', 'content': 'fixture'}
            (folder/'http.json').write_text(json.dumps([{'forwarded_request': {'messages': []}},
                {'forwarded_request': {'messages': [{'role': 'user', 'content': [delivered]}]}}]), encoding='utf-8')
            result = claude_summary(folder)
            self.assertEqual(result['calls'][0]['next_model_delivery']['model_call'], 2)
            self.assertEqual(result['calls'][0]['next_model_delivery']['packet'], delivered)
            # Repeated identical arguments must join by the native toolUseId,
            # rather than whichever assistant call happens to appear first.
            second = json.loads(json.dumps(event))
            second['message']['content'][0]['id'] = 'call-two'
            (folder/'stdout.jsonl').write_text(json.dumps(event)+'\n'+json.dumps(second), encoding='utf-8')
            request['params']['_meta'] = {'claudecode/toolUseId': 'call-two'}
            (folder/'wire.jsonl').write_text('\n'.join(json.dumps(r) for r in wire), encoding='utf-8')
            result = claude_summary(folder)
            self.assertEqual(result['calls'][0]['model_requested']['id'], 'call-two')
            self.assertIsNone(result['calls'][0]['next_model_delivery'])


if __name__ == '__main__':
    unittest.main()
