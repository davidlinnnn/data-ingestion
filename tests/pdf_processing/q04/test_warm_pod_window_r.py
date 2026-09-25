"""Regression for warm measurement stopping on an unreviewed graph delta."""

import json
from pathlib import Path
import tempfile
import unittest

from candidate.warm_pod_window_r import allow_pending_graph_for_measurement


def document(text="same", child="#/texts/0"):
    node = {
        "self_ref": "#/texts/0",
        "label": "text",
        "text": text,
        "prov": [{
            "page_no": 1,
            "bbox": {"l": 0, "t": 1, "r": 2, "b": 0, "coord_origin": "BOTTOMLEFT"},
            "charspan": [0, len(text)],
        }],
    }
    return {
        "body": {"self_ref": "#/body", "children": [{"$ref": child}]},
        "furniture": {},
        "groups": [],
        "texts": [node],
        "pictures": [],
        "tables": [],
        "key_value_items": [],
        "form_items": [],
        "pages": {"1": {"size": {"width": 2, "height": 1}}},
    }


class WarmMeasurementReferenceTest(unittest.TestCase):
    def test_structural_delta_is_recorded_without_claiming_fixture_acceptance(self):
        reference = document(child="#/texts/missing")
        actual = document()
        with tempfile.TemporaryDirectory() as tmp:
            digest = allow_pending_graph_for_measurement(
                "06", actual, reference, Path(tmp)
            )
            record = json.loads(
                (Path(tmp) / "source-review-pending.json").read_text()
            )
        self.assertEqual(record["actual_graph_sha256"], digest)
        self.assertEqual(record["status"], "NOT_ACCEPTED_WARM_MEASUREMENT_ONLY")
        self.assertEqual(record["fixture_acceptance"], "unproven")

    def test_source_content_delta_still_stops_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "source content changed"):
                allow_pending_graph_for_measurement(
                    "06", document("changed"), document(), Path(tmp)
                )

    def test_native_table_cell_delta_stops_measurement(self):
        reference = document()
        actual = document()
        table = {
            "self_ref": "#/tables/0",
            "label": "table",
            "prov": [],
            "data": {"table_cells": [{"text": "source", "row_span": 1}]},
        }
        reference["tables"] = [table]
        actual["tables"] = [{**table, "data": {
            "table_cells": [{"text": "changed", "row_span": 1}]
        }}]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "source content changed"):
                allow_pending_graph_for_measurement(
                    "native", actual, reference, Path(tmp)
                )

    def test_provenanced_picture_payload_delta_stops_measurement(self):
        reference = document()
        actual = document()
        picture = {
            "self_ref": "#/pictures/0",
            "label": "picture",
            "prov": [{"page_no": 1, "bbox": {}, "charspan": [0, 0]}],
            "annotations": {"kind": "source"},
        }
        reference["pictures"] = [picture]
        actual["pictures"] = [{**picture, "annotations": {"kind": "changed"}}]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "source content changed"):
                allow_pending_graph_for_measurement(
                    "native", actual, reference, Path(tmp)
                )


if __name__ == "__main__":
    unittest.main()
