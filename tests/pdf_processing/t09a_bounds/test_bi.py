import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from sentinel import run_warm_pod_cgroup_bi as run
from candidate.warm_v3_reference_bi import verify_v3_bundle
import pod_preflight_bi
import pod_workload_p
from pod_remote_evidence_bi import IncrementalEvidenceMirror, PodEvidenceIdentity


class BoundsWindowTest(unittest.TestCase):
    def test_remote_snapshot_accepts_bounded_phase_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = b"{}"
            (root / "state" / run.PHASE).mkdir(parents=True)
            (root / "state/config.json").write_bytes(config)
            (root / "state" / run.PHASE / "config.json").write_bytes(config)
            identity = PodEvidenceIdentity(
                pod_uid="pod", container_id="container", worker_pid=999999,
                worker_start_ticks=1, config_sha256=hashlib.sha256(config).hexdigest(),
            )
            for name, value in {
                "transport-identity.json": identity.__dict__,
                "supervisor-ownership.json": {"pid": identity.worker_pid, "start_ticks": 1},
                "ownership.json": {"config_sha256": identity.config_sha256},
                "workload-exit.json": {}, "cleanup-complete.json": {},
            }.items():
                (root / name).write_text(json.dumps(value))
            mirror = IncrementalEvidenceMirror(root / "mirror", identity)
            result = subprocess.run(
                [sys.executable, "-c", mirror.request_program(str(root))],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"state/{run.PHASE}/config.json", {
                item["path"] for item in json.loads(result.stdout)["files"]
            })

    def test_budget_adoption_requires_exact_initialized_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            config = {
                "parser_budgets": pod_workload_p.PARSER_BUDGETS,
                "run_id": run.RUN_IDENTITY,
                "profiles": {"08": {}},
                "queues": {"08": "initial"},
            }
            (state / "config.json").write_text(json.dumps(config))
            pod_workload_p.adopt_budget(
                state, state / "adoption.json", run_id=run.RUN_IDENTITY,
                workflow_queue="workflow", activity_queue="activity",
            )
            self.assertEqual(json.loads((state / "config.json").read_text())["run_id"], run.RUN_IDENTITY)
            with self.assertRaisesRegex(ValueError, "initialized run identity changed"):
                pod_workload_p.adopt_budget(
                    state, state / "rejected.json", run_id="different-run",
                )

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
