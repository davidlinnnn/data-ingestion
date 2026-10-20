import unittest
import evaluate as e


class EvaluatorTests(unittest.TestCase):
    def test_union_covers_split_context_without_counting_glyph_twice(self):
        points=[(0,1,1),(1,10,10),(2,20,20)]
        a=[[0,0,2,2]];b=[[9,9,21,21],[9,9,21,21]]
        self.assertEqual(e.counts(points,a)['covered_glyphs'],1)
        self.assertEqual(e.counts(points,b)['covered_glyphs'],2)
        self.assertTrue(e.counts(points,a+b)['all_context_glyph_centers_covered'])

    def test_empty_source_cannot_pass(self):
        self.assertFalse(e.counts([],[[0,0,1,1]])['all_context_glyph_centers_covered'])

    def test_original_two_point_tolerance(self):
        self.assertTrue(e.contains([10,10,20,20],8,22))
        self.assertFalse(e.contains([10,10,20,20],7.99,22))

    def test_locator_uses_source_area_and_is_not_semantic_score(self):
        self.assertEqual(e.overlap([0,0,10,10],[0,0,5,10]),.5)
        self.assertEqual(e.overlap([0,0,10,10],[20,20,30,30]),0)


if __name__=='__main__':unittest.main()
