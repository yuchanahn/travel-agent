import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from travel_agent.plan_sync import extract,user_conditions
from travel_agent.travel_plan import blank
from travel_agent.web_app import RunManager
from travel_agent.trace import Trace


def response(items):
    return {'message':{'tool_calls':[{'function':{'name':'record_trip_draft','arguments':{'items':items}}}]},
            'done_reason':'stop','prompt_eval_count':10,'eval_count':10}


class PlanSyncTests(TestCase):
    def test_wrong_source_repaired_only_when_quote_and_name_exist_in_answer(self):
        data=[{'kind':'activity','title':'합성 정원','source':'user','quote':'합성 정원'},
              {'kind':'activity','title':'없는 정원','source':'user','quote':'없는 인용'}]
        with TemporaryDirectory() as folder:
            items,usage=extract(blank(),'정원을 찾아줘','합성 정원 추천',chat=lambda *a,**kw:response(data),
                model='fixture',base_url='fixture',folder=folder)
        self.assertEqual(len(items),1);self.assertIn('미검증',items[0]['note'])
        self.assertEqual(usage['corrected_sources'],1);self.assertEqual(usage['rejected_candidates'],1)

    def test_explicit_budget_corrections_and_date_shorthand_are_preserved(self):
        items=user_conditions('두 사람이 총25만원 예산으로 2026년 10월 30부터 31일에 차 없이 여행해.',blank())
        self.assertEqual({i['title'] for i in items},{'인원','총예산','여행기간','이동수단'})
        corrected=user_conditions('예산을 25만원에서 20만원으로 바꿀게.',blank())
        self.assertIn('20만원',corrected[0]['note'])
        self.assertEqual(corrected[0]['kind'],'note')

    def test_answer_candidate_cannot_promote_price_or_date_to_verified(self):
        raw={'kind':'lodging','title':'합성 숙소','amount_won':200000,'cost_status':'observed','date':'2026-11-14',
             'source':'assistant','quote':'합성 숙소 20만원 추천'}
        with TemporaryDirectory() as folder:
            items,_=extract(blank(),'','합성 숙소 20만원 추천',chat=lambda *a,**kw:response([raw]),
                            model='fixture',base_url='fixture',folder=folder)
        self.assertNotIn('amount_won',items[0]);self.assertNotIn('date',items[0])
        self.assertIn('미검증',items[0]['note'])

    def test_fabricated_quote_rejected(self):
        with TemporaryDirectory() as folder,self.assertRaises(ValueError):
            extract(blank(),'성인2명','',chat=lambda *a,**kw:response([{'kind':'activity','title':'정원','source':'user','quote':'4명'}]),
                    model='fixture',base_url='fixture',folder=folder)

    def run_job(self,manager,query,parent=None):
        def agent(*args,**kwargs):
            trace=Trace(kwargs['trace_dir']);trace.emit('run_end',result={'status':'completed'})
            return {'status':'completed','answer':'성인2명 조건 확인','request_id':trace.request_id,'trace_path':str(trace.path)}
        with patch.object(manager.pool,'submit'):rid=manager.submit(query,False,parent)
        with patch('travel_agent.web_app.run_agent',side_effect=agent):manager._execute(rid)
        return rid

    def test_no_explicit_save_request_still_updates_plan_and_reports_failure(self):
        item={'kind':'note','title':'인원','note':'성인2명','source':'user','quote':'성인2명'}
        with TemporaryDirectory() as folder,patch('travel_agent.web_app.context_chat',return_value=response([item])):
            manager=RunManager(folder)
            try:
                rid=self.run_job(manager,'성인2명이 여행할 거야')
                self.assertEqual(manager.plan(rid)['items'][0]['title'],'인원')
                self.assertEqual(manager.jobs[rid]['result']['plan_sync']['status'],'conditions_saved')
                with patch('travel_agent.web_app.context_chat',side_effect=TimeoutError):
                    child=self.run_job(manager,'총예산만 20만원으로 바꿔줘',rid)
                self.assertEqual(manager.plan(child)['plan_sync']['status'],'conditions_saved')
                self.assertEqual(manager.plan(child)['plan_sync']['candidate_status'],'failed')
                self.assertTrue(any('20만원' in i.get('note','') for i in manager.plan(child)['items']))
                self.assertEqual(len(manager.plan(rid)['items']),1)
            finally:manager.pool.shutdown()
