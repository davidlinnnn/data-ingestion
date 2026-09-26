import argparse
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from sentinel import run_warm_pod_cgroup_bi as run
from candidate.warm_v3_reference_bi import verify_v3_bundle
import pod_preflight_bi


class BoundsWindowTest(unittest.TestCase):
    def test_projection_and_launch_use_new_identity(self):
        self.assertEqual(run.offline_check()["status"], "PASS_OFFLINE_ONLY")
        self.assertEqual(verify_v3_bundle(run.BUNDLE)[0]["status"], "REVIEWED_EXACT_V3")
        self.assertEqual(pod_preflight_bi.verify_workload_imports_ah(
            workspace=run.topology.base.ROOT, bundle=run.BUNDLE, prefix=run.PREFIX
        )["status"], "PASS")
        self.assertIn("pod_preflight_bi.py", " ".join(run.preflight_argv()))
        self.assertIn("pod_workload_bi.py", " ".join(run.workload_argv()))
        self.assertIn(run.RUN_IDENTITY, run.workload_argv())
        self.assertEqual(run.topology.kubernetes_list()["items"][3]["spec"]["replicas"], 0)

    def test_object_pressure_is_a_fail_stop_signal(self):
        sample = lambda max_events, full: {
            "memory_events": {"max": max_events}, "object_full_total_us": full,
        }
        observed = mock.Mock(error=None, samples=[sample(0, 0), sample(1, 0)])
        with (mock.patch.object(run, "monitor", observed),
              mock.patch.object(run, "base_verify_sample"),
              self.assertRaisesRegex(ValueError, "object-service max/full-PSI")):
            run.verify_sample({}, 0)

    def test_failed_workload_stops_observer_and_restores_object_limit(self):
        events = []
        class Monitor:
            process = object()
            error = None
            def __init__(self, *_args):
                pass
            def start(self, *, seconds):
                events.append(("start", seconds))
            def stop(self):
                events.append(("stop",))
                return {"max_events_delta": 0, "full_psi_delta_us": 0}
        def fail_workload(*_args):
            raise RuntimeError("workload failed")
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(run, "OBJECT_OUT", Path(tmp) / "object"),
            mock.patch.object(run, "offline_check", return_value={}),
            mock.patch.object(run.base, "Kubectl", return_value=object()),
            mock.patch.object(run.object_trial, "capture", return_value={}),
            mock.patch.object(run.object_trial, "enter", side_effect=lambda *_args, **_kwargs: events.append(("enter",))),
            mock.patch.object(run.object_trial, "restore", side_effect=lambda *_args, **_kwargs: events.append(("restore",)) or {}),
            mock.patch.object(run.base, "t09a_health", return_value={"healthy": True}),
            mock.patch.object(run.object_monitor_bh, "ObjectMonitor", Monitor),
            mock.patch.object(run, "adapted_window", fail_workload),
            self.assertRaisesRegex(RuntimeError, "workload failed"),
        ):
            run.execute_window(argparse.Namespace())
        self.assertEqual([row[0] for row in events], ["enter", "start", "stop", "restore"])


if __name__ == "__main__":
    unittest.main()
