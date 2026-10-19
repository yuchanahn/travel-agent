import copy
import unittest

from travel_agent.quality import paired_summary


class PairedQualityTests(unittest.TestCase):
    def report(self):
        return {'cases':[{'id':'case','rubric':{'fact':'correct fact','citation':'correct source'}}],
            'repeats':1,'schedule':[{},{}], 'runs':[
                {'case_id':'case','repeat':0,'version':v,'result':{'status':'completed'},
                 'review':{'fact':{'pass':v=='current','reason':'recorded claim'},
                           'citation':{'pass':True,'reason':'recorded source'}}}
                for v in ('baseline','current')]}

    def test_equal_paired_denominator_and_delta(self):
        result=paired_summary(self.report())
        self.assertEqual(result['paired_scores'],{'baseline':1,'current':2})
        self.assertEqual(result['paired_maximum'],2)
        self.assertEqual(result['wins'],1)
        self.assertTrue(result['evaluation_complete'])

    def test_provider_failure_is_not_scored_as_factual_zero(self):
        report=self.report()
        report['runs'][0]['result']={'status':'model_error','error':'HTTP429'}
        result=paired_summary(report)
        self.assertEqual(result['reviewed_pairs'],0)
        self.assertEqual(result['paired_maximum'],0)
        self.assertEqual(result['versions']['baseline']['errors'],1)
        self.assertFalse(result['evaluation_complete'])

    def test_missing_or_invented_rubric_and_nonboolean_values_cannot_pass(self):
        for edit in ['missing','extra','nonboolean','no_reason']:
            report=copy.deepcopy(self.report())
            review=report['runs'][0]['review']
            if edit=='missing':review.pop('fact')
            elif edit=='extra':review['new']={'pass':True,'reason':'not predeclared'}
            elif edit=='nonboolean':review['fact']['pass']=1
            else:review['fact']['reason']=''
            self.assertEqual(paired_summary(report)['reviewed_pairs'],0)

    def test_same_model_alias_does_not_hide_different_or_unknown_routes(self):
        report=self.report()
        self.assertEqual(paired_summary(report,require_route_match=True)['routing_excluded_pairs'],1)
        for i,run in enumerate(report['runs']):
            run['http_calls']=[{'status':200,'headers':{'x-routed-via':'provider'+str(i)+'/model'}}]
        self.assertEqual(paired_summary(report,require_route_match=True)['reviewed_pairs'],0)
        report['runs'][1]['http_calls']=copy.deepcopy(report['runs'][0]['http_calls'])
        self.assertEqual(paired_summary(report,require_route_match=True)['reviewed_pairs'],1)
