"""Local checks for the immutable ACL v3-b trace replay."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("acl_v3_b_trace", HERE / "analyze_trace.py")
assert SPEC and SPEC.loader
TRACE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRACE)


@unittest.skipUnless(
    TRACE.DEFAULT_EVIDENCE.exists(),
    "private immutable ACL v3-b evidence is not present",
)
class CapturedTrace(unittest.TestCase):
    def test_reproduces_cgroup_guard_rejection_without_oom_or_psi(self):
        result = TRACE.summarize(TRACE.DEFAULT_EVIDENCE)
        self.assertEqual(result["verdict"], "RED_CGROUP_GUARD_REJECTED")
        self.assertGreater(
            result["trace"]["observed_maximum_bytes"],
            result["guard"]["ceiling_bytes"],
        )
        self.assertEqual(result["trace"]["vm_oom_kill_values"], [0])
        self.assertEqual(result["trace"]["cgroup_oom_kill_values"], [0])
        self.assertEqual(result["trace"]["maximum_psi_full_avg10"], 0)
        self.assertTrue(result["trace"]["censored_at_guard_stop"])

    def test_measurement_cannot_attribute_shared_cgroup_to_parser(self):
        scope = TRACE.summarize(TRACE.DEFAULT_EVIDENCE)["measurement_scope"]
        self.assertEqual(scope["observed_metric"], "/sys/fs/cgroup/memory.current")
        self.assertFalse(scope["process_rss_or_pss_present"])
        self.assertFalse(scope["memory_stat_or_peak_present"])
        self.assertFalse(scope["exclusive_parser_attribution_supported"])

    def test_green_requirement_is_a_deterministic_red_loop(self):
        completed = subprocess.run(
            [sys.executable, str(HERE / "analyze_trace.py"), "--require-within-guard"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("RED_CGROUP_GUARD_REJECTED", completed.stderr)


if __name__ == "__main__":
    unittest.main()
