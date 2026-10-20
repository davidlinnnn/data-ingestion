"""Native serialization and intervention controls; no model initialization."""
import json
from pathlib import Path
import unittest

from run import effective

HERE = Path(__file__).resolve().parent


class RunnerControls(unittest.TestCase):
    def test_r1_changes_only_orientation_switch(self):
        baseline, modified = effective("R0"), effective("R1")
        self.assertTrue(baseline["ocr_options"]["use_cls"])
        self.assertFalse(modified["ocr_options"]["use_cls"])
        modified["ocr_options"]["use_cls"] = True
        self.assertEqual(modified, baseline)
        retained = json.loads((HERE.parent / "pdf-core-native-round-2026-10-17/S0/effective-options.json").read_text())
        retained["chart_extraction_options"]["model_spec"]["supported_engines"].sort()
        self.assertEqual(baseline, retained)

    def test_saved_native_page_and_profile_item_serialize(self):
        from docling.datamodel.base_models import Page
        from docling.utils.profiling import ProfilingItem, ProfilingScope
        saved = json.loads((HERE.parent / "pdf-core-ocr-boundary-trace-2026-10-19/live/result.json").read_text())["pages"][0]
        page = Page.model_validate(saved)
        cells = [cell.model_dump(mode="json") for cell in page.parsed_page.textline_cells]
        self.assertEqual(cells, saved["parsed_page"]["textline_cells"])
        self.assertEqual(len(cells), 114)
        timing = ProfilingItem(scope=ProfilingScope.PAGE, count=1, times=[1.5])
        self.assertEqual(timing.model_dump(mode="json")["times"], [1.5])


if __name__ == "__main__":
    unittest.main()
