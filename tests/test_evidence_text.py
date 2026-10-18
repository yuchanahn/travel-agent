"""Evidence boundaries must preserve qualifications and avoid invented fragments."""
import unittest

from travel_agent.evidence_text import bounded_blocks, bounded_prefix, body_signal
from travel_agent.web_pipeline import passages, pack_digest


class EvidenceTextTests(unittest.TestCase):
    def test_long_prose_keeps_complete_sentences_and_closure_exception(self):
        text=('A short introductory sentence. '*25
              +'\n\nMuseum opens at 09:00 except Mondays. Bus 10 stops at the entrance.')
        excerpt,_=passages(text,'museum opens Mondays bus',max_bytes=160)
        self.assertIn('Museum opens at 09:00 except Mondays.',excerpt)
        self.assertTrue(excerpt.endswith('.'))
        self.assertLessEqual(len(excerpt.encode()),160)
        self.assertTrue(all(segment in text for segment in excerpt.split('\n\n')))

    def test_oversized_indivisible_sentence_is_not_sliced_into_a_claim(self):
        text='Museum '+('very '*100)+'closed on Mondays.'
        blocks=bounded_blocks(text,80,80)
        self.assertEqual(blocks,[])
        excerpt,_=passages(text,'Museum',max_bytes=80)
        self.assertEqual(excerpt,'')

    def test_itinerary_and_address_lines_survive_when_they_fit(self):
        text='## Day 1\n\n09:00 Station → Museum\n10:00 Museum → Beach\nAddress: Example Road 12'
        blocks=bounded_blocks(text,600,400)
        self.assertIn('09:00 Station → Museum\n10:00 Museum → Beach',blocks[0])
        self.assertIn('Address: Example Road 12',blocks[0])

    def test_prefix_does_not_cut_a_word_or_treat_decimal_as_sentence_end(self):
        text='Opening hours are 09.30 to 18.00, except holidays.'
        self.assertEqual(bounded_prefix(text,len('Opening hours are 09.'.encode())),'Opening hours are')
        text='관람시간은 오전 9시입니다. 월요일에는 문을 닫습니다.'
        prefix=bounded_prefix(text,len('관람시간은 오전 9시입니다. 월요일에'.encode()))
        self.assertEqual(prefix,'관람시간은 오전 9시입니다.')

    def test_many_menu_lines_do_not_hide_a_long_article(self):
        menu='\n'.join('Menu '+str(i) for i in range(20))
        self.assertEqual(body_signal(menu),'navigation_heavy')
        article='The museum has a long and detailed description of the collection. '*25
        self.assertEqual(body_signal(menu+'\n'+article),'text_extracted')
        self.assertEqual(body_signal('Short but relevant information.'),'text_extracted')

    def test_layout_warning_is_visible_but_does_not_delete_a_terse_list(self):
        text='\n'.join('Museum stop '+str(i) for i in range(14))
        source={'id':'web:fixture','title':'Stops','url':'https://example.org/stops',
                'text':text,'_page_text':text,'page_fetched':True,'content_kind':'page_excerpt',
                'body_signal':body_signal(text)}
        digest,selected=pack_digest('Museum',[source],1500,{})
        self.assertIn('body_signal=navigation_heavy',digest)
        self.assertEqual(len(selected),1)
        self.assertIn('Museum stop 13',digest)
        self.assertLessEqual(len(digest.encode()),1500)
