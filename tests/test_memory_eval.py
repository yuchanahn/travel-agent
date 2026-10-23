import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('memory_eval',Path(__file__).resolve().parents[1]/'scripts/evaluate_memory_fixed.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MemoryEvalTests(unittest.TestCase):
    def test_gold_ranking_and_scope_negatives_have_separate_denominators(self):
        fixture={'events':[{'id':'a','session':'s','text':'오로라 현관 계단 87개'},
                           {'id':'b','session':'sibling','text':'형제 분기 암호 청동나무'}],
            'cases':[{'id':'positive','session':'s','query':'현관 계단','gold':['a']},
                     {'id':'negative','session':'s','query':'형제 암호','gold':[],'negative':'scope','forbidden':['b']}]}
        result=module.evaluate(fixture)
        self.assertEqual(result['retrieval']['positive_count'],1)
        self.assertEqual(result['retrieval']['hit_at_3_count'],1)
        self.assertEqual(result['retrieval']['mrr_at_3'],1)
        self.assertEqual(result['retrieval']['scope_leaks'],0)
        self.assertIsNone(result['rows'][1]['hit_at_3'])
