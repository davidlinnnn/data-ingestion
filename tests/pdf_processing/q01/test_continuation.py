import unittest
from replay import load
from docling_ibm_models.reading_order.reading_order_rb import ReadingOrderPredictor

class Continuation(unittest.TestCase):
    def test_source_continues_into_body(self):
        elements = load()
        predictor = ReadingOrderPredictor()
        ordered = predictor.predict_reading_order(elements)
        refs = {e.ref.cref: e.cid for e in elements}
        from pdf_processing.continuation import predict_merges
        merges = predict_merges(ordered)
        self.assertIn(refs['#/6/6'], merges.get(refs['#/5/0'], []))
        self.assertNotIn(refs['#/6/14'], merges.get(refs['#/5/0'], []))
"""Synthetic public text at the same PageElement/predict_merges seam as replay."""
import unittest
from docling_core.types.doc import CoordOrigin, RefItem, Size
from docling_ibm_models.reading_order.reading_order_rb import PageElement
from pdf_processing.continuation import predict_merges


def element(cid, page, text, box, label='text'):
    l, t, r, b = box
    return PageElement(cid=cid, ref=RefItem(cref=f'#/{cid}'), page_no=page,
        page_size=Size(width=600, height=800), text=text, label=label,
        l=l, r=r, t=800-t, b=800-b, coord_origin=CoordOrigin.BOTTOMLEFT)


class Continuations(unittest.TestCase):
    def test_margin_before_real_successor(self):
        p = element(0, 1, 'We travel toward', (100, 700, 500, 750))
        m = element(1, 2, 'SIDE NOTE', (20, 400, 70, 430))
        c = element(2, 2, 'North Harbor.', (100, 60, 500, 100))
        self.assertEqual(predict_merges([p, m, c]), {0: [2]})

    def test_cross_column_uppercase(self):
        p = element(0, 1, 'A route toward', (30, 700, 270, 750))
        c = element(1, 1, 'East Harbor.', (320, 60, 560, 100))
        self.assertEqual(predict_merges([p, c]), {0: [1]})

    def test_container_before_text_is_barrier(self):
        p = element(0, 1, 'unfinished prose', (100, 700, 500, 750))
        header = element(1, 2, '', (110, 60, 420, 100), 'key_value_region')
        caption = element(2, 2, 'Figure 8.1 Sample', (120, 140, 490, 190))
        self.assertEqual(predict_merges([p, header, caption]), {})

    def test_lowercase_page_and_chain(self):
        p = element(0, 1, 'first fragment', (100, 680, 500, 750))
        c = element(1, 2, 'second fragment', (100, 60, 500, 750))
        d = element(2, 3, 'last fragment.', (100, 60, 500, 100))
        self.assertEqual(predict_merges([p, c, d]), {0: [1, 2]})

    def test_rejections(self):
        p = element(0, 1, 'unfinished prose', (100, 700, 500, 750))
        for successor in [element(1, 2, 'SIDE', (20, 60, 70, 100)),
                          element(1, 3, 'next text', (100, 60, 500, 100)),
                          element(1, 2, 'mid page', (100, 350, 500, 400)),
                          element(1, 2, 'Heading', (100, 60, 500, 100), 'section_header')]:
            with self.subTest(successor=successor.text):
                self.assertEqual(predict_merges([p, successor]), {})

    def test_full_stop_and_interior_column_rejected(self):
        for text, box in [('Finished.', (100, 700, 500, 750)), ('unfinished', (100, 200, 500, 300))]:
            p = element(0, 1, text, box)
            c = element(1, 2, 'Continuation', (100, 60, 500, 100))
            self.assertEqual(predict_merges([p, c]), {})

    def test_ambiguous_successors_rejected(self):
        p = element(0, 1, 'unfinished', (100, 700, 500, 750))
        a = element(1, 2, 'First', (100, 60, 500, 100))
        b = element(2, 2, 'Second', (100, 60, 500, 100))
        self.assertEqual(predict_merges([p, a, b]), {})




class Preservation(unittest.TestCase):
    def test_ambiguous_owners(self):
        a = element(0, 1, 'first unfinished', (100, 690, 500, 750))
        b = element(1, 1, 'second unfinished', (100, 700, 500, 750))
        c = element(2, 2, 'Continuation.', (100, 60, 500, 100))
        self.assertEqual(predict_merges([a, b, c]), {})

    def test_inline_chain_retained(self):
        a = element(0, 1, 'for each', (100, 200, 140, 210))
        b = element(1, 1, 'action', (145, 200, 180, 210))
        c = element(2, 1, 'in', (185, 200, 200, 210))
        self.assertEqual(predict_merges([a, b, c]), {0: [1, 2]})

    def test_input_content_not_mutated(self):
        values = load()
        original = [e.model_dump() for e in values]
        predict_merges(values)
        self.assertEqual(original, [e.model_dump() for e in values])

    def test_overlapping_entrances_are_ambiguous(self):
        p = element(0, 1, 'unfinished', (100, 700, 500, 750))
        a = element(1, 2, 'First.', (100, 60, 500, 100))
        b = element(2, 2, 'Second.', (101, 61, 499, 101))
        self.assertEqual(predict_merges([p, a, b]), {})

    def test_intervening_content_blocks_column_exit(self):
        for label in ('text', 'key_value_region'):
            for target_page, target_box in ((2, (100, 60, 500, 100)),
                                           (1, (320, 60, 560, 100))):
                with self.subTest(label=label, target_page=target_page):
                    owner_box = (100, 650, 500, 700) if target_page == 2 else (30, 650, 270, 700)
                    barrier_box = (owner_box[0], 710, owner_box[2], 760)
                    p = element(0, 1, 'unfinished prose', owner_box)
                    barrier = element(1, 1, 'Following content.', barrier_box, label)
                    target = element(2, target_page, 'Continuation.', target_box)
                    self.assertEqual(predict_merges([p, barrier, target]), {})
