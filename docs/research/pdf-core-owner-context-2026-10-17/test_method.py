import unittest
from unittest.mock import Mock
import method as m


class OwnerTests(unittest.TestCase):
    def test_tight_detection_maps_to_full_owner(self):
        self.assertTrue(m.matches([40,40,50,50],[0,0,100,100]))
        self.assertFalse(m.matches([40,40,50,50],[100,100,200,200]))

    def test_edge_touch_or_corner_overlap_is_not_a_unique_match(self):
        self.assertFalse(m.matches([0,0,10,10],[10,0,20,10]))
        self.assertFalse(m.matches([0,0,10,10],[9,9,19,19]))

    def test_transitive_shared_owners_merge_without_dropping_native_seed(self):
        seeds=[dict(owners=['a'],reasons=['native_signal']),dict(owners=['b'],reasons=['r1']),
               dict(owners=['a','b'],reasons=['r2'])]
        out=m.merge(seeds)
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['owners'],['a','b'])
        self.assertEqual(out[0]['reasons'],['native_signal','r1','r2'])
        self.assertEqual(seeds[0]['owners'],['a'])

    def test_context_only_owner_does_not_become_target(self):
        def owner(ref,box):return dict(ref=ref,responsibility='body',pure_formula_picture=False,
            fragments=[dict(page=1,bbox=box)])
        owners=dict(a=owner('a',[0,0,10,10]),b=owner('b',[20,0,30,10]),middle=owner('middle',[12,0,18,10]))
        job=m.context(dict(owners=['a','b'],reasons=[]),owners,{1:dict(pixels_wh=[200,200])},{},Mock())
        self.assertEqual(job['target_owner_refs'],['a','b'])
        self.assertEqual(job['context_crops'][0]['context_only_owner_refs'],['middle'])
        self.assertTrue(job['input_within_bounds'])

    def test_large_context_is_not_silently_clipped(self):
        owner=dict(ref='a',responsibility='body',pure_formula_picture=False,fragments=[dict(page=1,bbox=[0,0,100,90])])
        job=m.context(dict(owners=['a'],reasons=[]),dict(a=owner),{1:dict(pixels_wh=[200,200])},{},Mock())
        self.assertFalse(job['input_within_bounds'])
        self.assertEqual(job['context_crops'][0]['pixels'],[0,0,200,180])
        self.assertIn('page_area_limit',job['budget_failures'])

    def test_mixed_picture_title_is_not_body_writeback(self):
        owners={key:dict(ref=key,responsibility=kind,pure_formula_picture=False,
            fragments=[dict(page=1,bbox=[0,0,10,10])]) for key,kind in [('p','picture'),('t','body')]}
        job=m.context(dict(owners=['p','t'],reasons=[]),owners,{1:dict(pixels_wh=[200,200])},{},Mock())
        self.assertEqual(job['binding'],'unresolved')

    def test_prior_character_rule_has_no_filename_case_exception(self):
        self.assertTrue(m.gate('θ = x'))
        self.assertTrue(m.gate('edit_type'))
        self.assertFalse(m.gate('SKILL.md'))


if __name__=='__main__':unittest.main()
