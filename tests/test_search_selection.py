import json
from unittest import TestCase
from travel_agent.search_selection import select
from travel_agent.brave_mcp import select_batch,pack_result
from test_brave_mcp import result


class SelectionTests(TestCase):
    def test_dedup_preserves_price_date_and_distinct_source(self):
        hits=[{'id':'a','title':'합성 숙소','snippet':'평일 5만원. 평일 5만원. 주말 8만원.',
               'extra_snippets':['평일 5만원. 11월 14일 요금 미확인.']},
              {'id':'b','title':'다른 숙소','snippet':'평일 5만원.'}]
        ranked,stats=select(hits,'합성 숙소 주말')
        self.assertEqual(ranked[0]['id'],'a');self.assertEqual(stats['exact_sentences_removed'],2)
        text=json.dumps(ranked,ensure_ascii=False)
        self.assertIn('8만원',text);self.assertIn('11월 14일',text)
        self.assertEqual(len(ranked),2)

    def test_parallel_batch_caps_thirty_and_merges_same_url_fragments(self):
        results=[]
        for batch in range(3):
            r=result([{'title':'합성 숙소 '+str(i),'url':f'https://example.com/{i}',
                       'description':f'합성 숙소 안내 {batch}.'} for i in range(batch*20,batch*20+20)])
            r['search_query']='합성 숙소';results.append(('search',r))
        stats=select_batch(results,'합성 숙소')
        packets=[json.loads(pack_result(r)) for _,r in results]
        ids=[h['id'] for p in packets for h in p['hits']]
        self.assertEqual(len(ids),30);self.assertEqual(len(set(ids)),30)
        self.assertEqual(stats['unique_candidates'],60)
        a=result([{'title':'same','url':'https://example.com/a','description':'평일 5만원.'}])
        b=result([{'title':'same','url':'https://example.com/a','description':'주말 8만원.'}])
        select_batch([('x',a),('y',b)],'숙소')
        packet=json.loads(pack_result(a));self.assertIn('8만원',str(packet))
        self.assertEqual(json.loads(pack_result(b))['hits'],[])
        self.assertNotIn('error',json.loads(pack_result(b)))
