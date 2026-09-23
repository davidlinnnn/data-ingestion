"""Cross-page joins must respect Docling's actual reading order."""
from pathlib import Path
import tempfile
import unittest

from docling_core.types.doc import CoordOrigin, RefItem, Size
from docling_ibm_models.reading_order.reading_order_rb import PageElement, ReadingOrderPredictor

from pdf_processing.continuation import METHOD, predict_merges
from pdf_processing.execution import ChildFailure
from pdf_processing.parse import ParseRequest, execute


def element(cid, page, text, left, top, right, bottom, label="text"):
    return PageElement(
        cid=cid, ref=RefItem(cref=f"#/{cid}"), page_no=page,
        page_size=Size(width=600, height=800), text=text, label=label,
        l=left, t=800-top, r=right, b=800-bottom,
        coord_origin=CoordOrigin.BOTTOMLEFT,
    )


class CrossPageReadingOrder(unittest.TestCase):
    def test_source_page_right_column_blocks_left_to_next_page_left(self):
        left = element(0, 1, "Unfinished left-column prose", 48, 680, 300, 755)
        right = element(1, 1, "Intervening right-column prose.", 312, 250, 564, 320)
        next_left = element(2, 2, "Next page prose.", 48, 50, 300, 120)
        ordered = ReadingOrderPredictor().predict_reading_order([left, right, next_left])
        self.assertEqual([item.cid for item in ordered], [0, 1, 2])
        self.assertEqual(predict_merges(ordered), {})

    def test_next_page_left_column_blocks_right_to_next_page_right(self):
        right = element(0, 1, "Unfinished right-column prose", 312, 680, 564, 755)
        next_left = element(1, 2, "Intervening left-column prose.", 48, 50, 300, 120)
        next_right = element(2, 2, "Next right-column prose.", 312, 50, 564, 120)
        ordered = ReadingOrderPredictor().predict_reading_order([right, next_left, next_right])
        self.assertEqual([item.cid for item in ordered], [0, 1, 2])
        self.assertEqual(predict_merges(ordered), {})

    def test_adjacent_single_column_handoff_still_joins(self):
        first = element(0, 1, "Unfinished single-column prose", 100, 680, 500, 755)
        second = element(1, 2, "Continuation follows.", 100, 50, 500, 120)
        ordered = ReadingOrderPredictor().predict_reading_order([first, second])
        self.assertEqual(predict_merges(ordered), {0: [1]})

    def test_margin_picture_does_not_break_single_column_handoff(self):
        first = element(0, 5, "Unfinished single-column prose", 100, 680, 500, 755)
        margin_icon = element(1, 6, "", 35, 180, 65, 205, label="picture")
        second = element(2, 6, "Continuation follows.", 100, 50, 500, 120)
        ordered = [first, margin_icon, second]
        self.assertEqual(predict_merges(ordered), {0: [2]})

    def test_narrow_picture_inside_body_column_blocks_handoff(self):
        first = element(0, 5, "Unfinished single-column prose", 100, 680, 500, 755)
        body_picture = element(1, 6, "", 150, 180, 180, 205, label="picture")
        second = element(2, 6, "Continuation follows.", 100, 50, 500, 120)
        self.assertEqual(predict_merges([first, body_picture, second]), {})

    def test_historical_methods_cannot_select_v3_code(self):
        self.assertEqual(METHOD, "column-edge-continuation-v3")
        for version, source_sha in (
            ("v1", "791e2ebef036d6f2468fb607162a135eecb3c4eaa056d4e35b1a81bffde49772"),
            ("v2", "8c5e68006af438e2c1a5d5f82614436c8e1e7e5fc7f6e0a1d77645c640b23305"),
        ):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                request = ParseRequest(
                    mode="restore", pdf=Path(tmp) / "missing.pdf", out=Path(tmp) / "out",
                    model_cache=Path(tmp), checkpoint=Path(tmp),
                    expected_method={"continuation": {
                        "version": "column-edge-continuation-" + version,
                        "sha256": source_sha,
                    }},
                )
                with self.assertRaises(ChildFailure) as caught:
                    execute(request)
                self.assertEqual(caught.exception.code, "unsupported_continuation_method")
                self.assertFalse(request.out.exists())


if __name__ == "__main__":
    unittest.main()
