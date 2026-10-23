import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from travel_agent.travel_plan import blank,mutate,budget,markdown,validate_item
from travel_agent.web_app import RunManager


class PlanTests(TestCase):
    def test_selection_is_not_price_truth_and_changed_model_draft_revokes_confirmation(self):
        p=mutate(blank(),'upsert',{'items':[{'kind':'cost','title':'숙박','amount_won':300000,'basis':'2명1박','cost_status':'estimate'}]},model=True)
        item=p['items'][0]
        p=mutate(p,'confirm',{'id':item['id'],'confirmed':True})
        self.assertEqual(budget(p,True)['estimated_won'],300000)
        p=mutate(p,'upsert',{'items':[{'id':item['id'],'kind':'cost','title':'숙박','amount_won':250000}]},model=True)
        self.assertFalse(p['items'][0]['confirmed'])
        self.assertEqual(budget(p,True)['item_count'],0)

    def test_invalid_batch_is_atomic_and_model_cannot_confirm(self):
        p=blank()
        with self.assertRaises(ValueError):mutate(p,'upsert',{'items':[{'kind':'note','title':'ok'},{'kind':'cost','title':'bad','amount_won':True}]})
        self.assertEqual(p,blank())
        with self.assertRaises(ValueError):mutate(p,'confirm',{'id':'x','confirmed':True},model=True)
        for bad in [{'kind':{},'title':'x'},{'kind':'note','title':'x','date':[]},
                    {'kind':'cost','title':'x','cost_status':{}},{'kind':'note','title':'x','confirmed':True},
                    {'kind':'note','title':'x','source_url':'javascript:alert(1)'},
                    {'kind':'note','title':'x','date':'2026-02-30'},
                    {'kind':'activity','title':'x','start':'18:00','end':'09:00'}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate_item(bad)

    def test_budget_does_not_treat_unknown_as_zero_or_double_count_lodging(self):
        p=mutate(blank(),'upsert',{'items':[{'kind':'cost','title':'요금 미정'},
             {'kind':'cost','title':'입장료','amount_won':24000,'basis':'2명','cost_status':'observed'},
             {'kind':'cost','title':'식비','amount_won':30000,'basis':'2명1끼','cost_status':'estimate'},
             {'kind':'lodging','title':'숙소 후보'}]})
        self.assertEqual(budget(p),{'observed_won':24000,'estimated_won':30000,'unknown_count':1,'item_count':3})
        output=markdown(p)
        self.assertIn('금액 미확인',output)
        self.assertIn('예약 완료나 가격 검증',output)

    def test_markdown_keeps_unknown_and_escapes_injected_html(self):
        p=mutate(blank(),'upsert',{'items':[{'kind':'activity','title':'<script>|[x]','note':'x\ny'}]})
        out=markdown(p)
        self.assertNotIn('<script>',out)
        self.assertIn('&lt;script&gt;',out)
        self.assertIn('미정',out)
        self.assertNotIn('script',markdown(p,True))

    def test_model_iso_time_is_losslessly_split_and_lodging_cost_counted_once(self):
        p=mutate(blank(),'upsert',{'items':[
            {'kind':'activity','title':'산책','start':'2026-11-14T10:00','end':'2026-11-14T12:00'},
            {'kind':'lodging','title':'합성 숙소','amount_won':240000,'basis':'2명1박','cost_status':'estimate'}]},model=True)
        self.assertEqual((p['items'][0]['date'],p['items'][0]['start'],p['items'][0]['end']),('2026-11-14','10:00','12:00'))
        self.assertEqual(budget(p)['estimated_won'],240000)
        self.assertIn('240,000원',markdown(p))
        with self.assertRaises(ValueError):validate_item({'kind':'activity','title':'x','date':'2026-11-15','start':'2026-11-14T10:00'})

    def test_storage_revision_branch_isolation_restart_and_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            manager=RunManager(folder)
            def save(id,parent=None):
                job={'id':id,'query':'synthetic','state':'done','created_at':'2026-10-23','result':{'answer':'fixture'}}
                if parent:job['parent_id']=parent
                manager.jobs[id]=job;manager._save(job)
                return job
            a,b,c='a'*32,'b'*32,'c'*32
            save(a)
            p=manager.update_plan(a,{'revision':0,'action':'upsert','items':[{'kind':'note','title':'2명'}]})
            save(b,a);save(c,a)
            manager.update_plan(b,{'revision':p['revision'],'action':'upsert','items':[{'kind':'note','title':'이천 출발'}]})
            self.assertEqual(len(manager.plan(c)['items']),1)
            with self.assertRaises(RuntimeError):manager.update_plan(b,{'revision':0,'action':'delete','id':p['items'][0]['id']})
            manager.pool.shutdown(wait=True)
            restarted=RunManager(folder)
            self.assertEqual(len(restarted.plan(b)['items']),2)
            restarted.delete_conversation(a)
            self.assertFalse((Path(folder)/b/'plan.json').exists())
            restarted.pool.shutdown(wait=True)
