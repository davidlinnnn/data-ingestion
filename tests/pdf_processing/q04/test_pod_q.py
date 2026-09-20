"""Adapter checks for the Q run over the reviewed P Pod engine."""

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import pod_remote_evidence_q as evidence
import pod_topology_q as topology
import pod_workload_q as workload
from sentinel import run_aima_pod_cgroup_q as runner


class QPodAdapterTest(unittest.TestCase):
    def test_runtime_identity_reaches_every_launch_and_evidence_program(self):
        self.assertEqual(runner.base.WINDOW_SECONDS, 1500)
        self.assertEqual(runner.base.WORKLOAD_SECONDS, 825)
        self.assertEqual(runner.base.CLEANUP_SECONDS, 300)
        self.assertIn("pod_workload_q.py", runner.workload_argv()[1])
        self.assertIn("pod_preflight_q.py", runner.preflight_argv()[1])
        programs = (
            runner.base.sample_program(),
            runner.base.stop_owned_supervisor_program(1),
            runner.base.terminal_cleanup_program(),
            runner.base.force_stop_supervisor_program(),
            runner.base.archive_fingerprint_program(),
        )
        for program in programs:
            self.assertIn(runner.EVIDENCE, program)
            self.assertNotIn(runner.P_EVIDENCE, program)
        constants = repr(runner.base.execute_window.__code__.co_consts)
        self.assertIn(runner.EVIDENCE, constants)
        self.assertNotIn(runner.P_EVIDENCE, constants)

    def test_cleanup_ignores_worker_log_sibling(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            root = state / workload.PHASE / "worker-1"
            root.mkdir(parents=True)
            (state / workload.PHASE / "worker-1.log").write_text("retained")
            (root / "stopped.json").write_text(
                json.dumps({"parser_absent": True, "scratch_absent": True})
            )
            self.assertTrue(workload.cleanup_markers(state)["worker_absent"])

    def test_measurement_and_transport_use_q_paths(self):
        args = SimpleNamespace(
            python="python",
            workspace=Path("/workspace"),
            bundle=Path("/bundle"),
            state=Path("/state"),
            capacity=Path("/capacity"),
            prefix=runner.PREFIX,
        )
        argv = workload.build_measurement_argv(args, workload.RUN_ID, "scope")
        self.assertIn("candidate.aima_pod_window_q", argv)
        self.assertIn("pod-topology-v16/RUNTIME-INTEGRATION-MANIFEST.json", " ".join(argv))
        self.assertIn(
            f"state/{evidence.MEASUREMENT}/measurement-contract.json",
            evidence.FINAL_REQUIRED,
        )

    def test_topology_is_inactive_and_current_producer_bound(self):
        value = topology.kubernetes_list()
        self.assertEqual(value["items"][3]["spec"]["replicas"], 0)
        self.assertEqual(
            topology.source_manifest()["producer"],
            json.loads(
                Path("tests/pdf_processing/q04/candidate/warm-lifecycle-q/MANIFEST.json").read_text()
            )["producer"],
        )


if __name__ == "__main__":
    unittest.main()
