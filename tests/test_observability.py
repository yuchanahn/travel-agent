import unittest
from travel_agent.observability import summarize


class SummaryTests(unittest.TestCase):
    def test_cumulative_http_missing_tokens_and_pending_calls(self):
        observation={'id':'d','started_at':'t','status':'ready'}
        events=[{'kind':'model_start'}, {'kind':'model_end','prompt_tokens':20,'output_tokens':None},
            {'kind':'model_start'}, {'kind':'model_error'},
            {'kind':'document_collection','observations':[observation]},
            {'kind':'document_collection','observations':[observation]},
            {'kind':'tool_start','span':'a'}, {'kind':'tool_start','span':'b'},
            {'kind':'tool_start','span':'c'},
            {'kind':'tool_end','span':'a','result':{'from_document_store':True}},
            {'kind':'tool_error','span':'b','result':{'error':'Identical tool call already attempted; change query'}},
            {'kind':'run_end','result':{'status':'timeout','elapsed_seconds':3}}]
        s=summarize(events)
        self.assertEqual((s['tool_requests'],s['tool_successes'],s['tool_errors'],s['tool_pending']),(3,1,1,1))
        self.assertEqual(s['automatic_http_observations'],1)
        self.assertEqual(s['stored_document_reads'],1)
        self.assertEqual(s['errors_by_type'],{'duplicate_rejected':1})
        self.assertEqual(s['prompt_tokens']['reported_sum'],20)
        self.assertFalse(s['prompt_tokens']['complete'])
        self.assertIsNone(s['output_tokens']['reported_sum'])
        self.assertEqual(s['status'],'timeout')

    def test_result_error_and_complete_zero_usage(self):
        s=summarize([{'kind':'model_start'}, {'kind':'model_end','prompt_tokens':0,'output_tokens':0},
            {'kind':'tool_start','span':'a'}, {'kind':'tool_end','span':'a','result':{'is_error':True}},
            {'kind':'tool_start','span':'b'}, {'kind':'tool_error','span':'b','result':{'http_status':403}},
            {'kind':'run_end','result':{'status':'completed','elapsed_seconds':1}}])
        self.assertTrue(s['prompt_tokens']['complete'])
        self.assertEqual(s['output_tokens']['reported_sum'],0)
        self.assertEqual(s['tool_successes'],0)
        self.assertEqual(s['tool_error_ratio'],1)
        self.assertEqual(s['errors_by_type'],{'tool_error':1,'http_error':1})

    def test_empty_trace_has_no_invented_status_or_usage(self):
        s=summarize([])
        self.assertEqual(s['status'],'incomplete')
        self.assertIsNone(s['elapsed_seconds'])
        self.assertIsNone(s['prompt_tokens']['reported_sum'])
        self.assertIsNone(s['tool_error_ratio'])

    def test_partial_tool_metadata_does_not_break_history(self):
        s=summarize([{'kind':'tool_start'}, {'kind':'tool_end'}])
        self.assertEqual(s['malformed_tool_events'],2)
        self.assertEqual(s['tool_requests'],0)
