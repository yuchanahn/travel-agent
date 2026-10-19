import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from travel_agent.agent import CITATIONS
from travel_agent.acceptance import run_journey,mechanical_checks,assessment


class JourneyTests(unittest.TestCase):
    def test_completed_journey_requires_explicit_factual_review_to_release(self):
        report={'case':{'turns':[{}]},'turns':[{'checks':{'completed':True,'same_conversation':True,
            'answer_present':True,'lodging_search_without_dates':False,'lodging_date_mismatch_spans':[]}}],
            'cleanup':{'deleted_count':1},'manual_review':{'verdict':'pending'}}
        self.assertTrue(assessment(report)['mechanical_gate'])
        self.assertFalse(assessment(report)['release_gate'])
        report['manual_review']['verdict']='fail'
        self.assertFalse(assessment(report)['release_gate'])
        report['manual_review']['verdict']='pass'
        self.assertTrue(assessment(report)['release_gate'])
    def test_real_model_citation_variants_preserve_identifiers(self):
        self.assertEqual(CITATIONS.findall('[\u200bmcp:92c067d320840cd6] 【web:0123456789abcdef】 [m-abcd]'),
                         ['mcp:92c067d320840cd6','web:0123456789abcdef','m-abcd'])

    def test_finished_loops_do_not_hide_invented_dates_and_quality_stays_pending(self):
        events=[{'kind':'tool_start','span':'1','name':'mcp_openbnb_airbnb_search',
                 'arguments':'{"checkin":"2026-11-01","checkout":"2026-11-02"}'},
                {'kind':'tool_end','span':'1','name':'mcp_openbnb_airbnb_search','result':{'id':'mcp:test'}}]
        job={'result':{'status':'completed','answer':'Looks complete'},'conversation':[{'id':'root'}],'events':events}
        checks=mechanical_checks({'dates':None},job,'root')
        self.assertTrue(checks['completed'])
        self.assertTrue(checks['lodging_search_without_dates'])
        checks=mechanical_checks({'dates':['2026-11-14','2026-11-15']},job,'root')
        self.assertEqual(checks['lodging_date_mismatch_spans'],['1'])
        self.assertEqual(checks['manual_fact_review'],'pending')

    def test_chained_turns_record_evidence_then_delete_only_test_root(self):
        requests=[];submitted=[]
        def api(path,method='GET',payload=None):
            requests.append((path,method,copy.deepcopy(payload)))
            if method=='POST':
                submitted.append(payload);return {'id':'root' if len(submitted)==1 else 'child'}
            if method=='DELETE':return {'deleted_count':2,'deleted_ids':['root','child']}
            return {'id':path.rsplit('/',1)[-1],'state':'done','can_continue':True,
                    'conversation':[{'id':'root'}],'result':{'status':'completed','answer':'fixture'},'events':[]}
        case={'turns':[{'id':'first','query':'synthetic'},{'id':'second','query':'changed budget'}]}
        with TemporaryDirectory() as tmp:
            report=run_journey(api,case,Path(tmp)/'report')
            self.assertTrue((Path(tmp)/'report'/'report.json').exists())
        self.assertIsNone(submitted[0]['parent_id'])
        self.assertEqual(submitted[1]['parent_id'],'root')
        self.assertEqual(requests[-1],('/api/conversations/root','DELETE',None))
        self.assertEqual(report['cleanup']['deleted_count'],2)
        self.assertEqual(report['manual_review']['verdict'],'pending')

    def test_poll_failure_still_cleans_up_and_records_execution_error(self):
        requests=[]
        def api(path,method='GET',payload=None):
            requests.append((path,method))
            if method=='POST':return {'id':'root'}
            if method=='DELETE':return {'deleted_count':1}
            raise OSError('synthetic poll failure')
        with TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                run_journey(api,{'turns':[{'id':'first','query':'synthetic'}]},Path(tmp)/'report')
            import json
            result=json.loads((Path(tmp)/'report'/'report.json').read_text(encoding='utf-8'))
        self.assertEqual(requests[-1],('/api/conversations/root','DELETE'))
        self.assertIn('OSError',result['execution_error'])
