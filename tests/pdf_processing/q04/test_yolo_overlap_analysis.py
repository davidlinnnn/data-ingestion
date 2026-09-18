"""Regression checks for attribution-B lifecycle point selection."""

import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).parent
ANALYZER = HERE / "diagnosis/yolo-attribution-b/analyze_overlap.py"
EVIDENCE = HERE / "diagnosis/yolo-attribution-b/evidence/lifecycle-overlap.json"
spec = importlib.util.spec_from_file_location("analyze_overlap", ANALYZER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class YoloOverlapAnalysisTests(unittest.TestCase):
    def test_retained_analysis_proves_overlap_before_cancel_without_using_peak(self):
        result = json.loads(EVIDENCE.read_text())
        self.assertFalse(result["measurement_complete"])
        self.assertTrue(result["pre_cancel_overlap_proven"])
        breach = result["points"]["at_first_guard_breach"]
        peak = result["points"]["peak"]
        self.assertGreater(breach["memory_current_bytes"], result["guard_bytes"])
        self.assertGreater(breach["warm_parser_pss_bytes"], 0)
        self.assertGreater(breach["fresh_parse_child_pss_bytes"], 0)
        self.assertLess(breach["time"], result["temporal_cancel_requested_at"])
        self.assertGreater(peak["time"], result["temporal_cancel_requested_at"])

    def test_point_selection_uses_reported_boundaries(self):
        process = lambda kind, pss: {
            "ownership": "owned", "command_class": kind, "pss_bytes": pss, "pid": pss
        }
        rows = []
        for index, memory in enumerate((80, 90, 110, 130, 70)):
            rows.append({
                "time": float(index),
                "memory_current": memory,
                "owned_pss_total_bytes": memory // 2,
                "attribution_complete": True,
                "observations": ([{"label": "workflow_progress_assembling_observed", "observed_at": 1.5}] if index == 2 else []),
                "processes": ([process("worker", 1)]
                              + ([process("warm_parser", 20)] if index <= 3 else [])
                              + ([process("fresh_parse_child", 10)] if 2 <= index <= 3 else [])),
            })
        summary = {
            "run_id": "run",
            "outcome": "guard",
            "measurement_complete": False,
            "workload": {
                "cgroup_ceiling_bytes": 100,
                "first_guard_breach_at": "1970-01-01T00:00:02+00:00",
                "first_guard_breach_bytes": 101,
            },
            "attribution": {"temporal_cancel_requested_at": "1970-01-01T00:00:03+00:00"},
        }
        result = module.analyze(summary, rows)
        self.assertEqual(result["points"]["before_assembly"]["sample_index"], 1)
        self.assertEqual(result["points"]["before_first_guard_breach"]["sample_index"], 1)
        self.assertEqual(result["points"]["at_first_guard_breach"]["sample_index"], 2)
        self.assertEqual(result["points"]["before_cancel"]["sample_index"], 2)
        self.assertEqual(result["points"]["peak"]["sample_index"], 3)
        self.assertEqual(result["points"]["exit"]["sample_index"], 4)


if __name__ == "__main__":
    unittest.main()
