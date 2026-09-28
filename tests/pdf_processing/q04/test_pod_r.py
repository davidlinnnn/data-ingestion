"""Regression checks for the R warm Pod adapter."""

import json
import contextlib
import io
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import subprocess
import sys
import unittest

from candidate import warm_pod_window_r as window
import pod_remote_evidence_r as evidence
import pod_topology_r as topology
import pod_workload_r as workload
from pod_durable_evidence import seal
from sentinel import run_warm_pod_cgroup_r as runner


class RWarmPodAdapterTest(unittest.TestCase):
    def test_runtime_identity_and_unchanged_guards_reach_launch(self):
        self.assertEqual(runner.base.WINDOW_SECONDS, 1500)
        self.assertEqual(runner.base.WORKLOAD_SECONDS, 825)
        self.assertEqual(runner.base.CLEANUP_SECONDS, 300)
        self.assertEqual(runner.authorization_scope()["group_requests"], 29)
        self.assertEqual(runner.authorization_scope()["max_requests"], 20)
        self.assertFalse(runner.authorization_scope()["automatic_retry"])
        self.assertIn("pod_workload_r.py", runner.workload_argv()[1])
        self.assertIn("pod_preflight_r.py", runner.preflight_argv()[1])
        self.assertIn(
            "pod-topology-v17/RUNTIME-INTEGRATION-MANIFEST.json",
            repr(workload.base.run.__code__.co_consts),
        )

    def test_q_and_r_runner_import_order_is_isolated(self):
        env = os.environ.copy()
        for modules in (
            "sentinel.run_aima_pod_cgroup_q,sentinel.run_warm_pod_cgroup_r",
            "sentinel.run_warm_pod_cgroup_r,sentinel.run_aima_pod_cgroup_q",
        ):
            subprocess.run([
                sys.executable, "-c",
                "import importlib; [importlib.import_module(x) for x in '" + modules + "'.split(',')]",
            ], check=True, env=env, capture_output=True, text=True)

    def test_projected_aima_oracle_is_bound_in_a_fresh_process(self):
        env = os.environ.copy()
        env.pop("Q02_SOURCE_ORACLE", None)
        script = """
import os
from pathlib import Path
from candidate.warm_pod_window_r import projected_aima_oracle
bundle=Path('/private/tmp/q04-inputs-warm-lifecycle-q-final4')
assert 'Q02_SOURCE_ORACLE' not in os.environ
with projected_aima_oracle(bundle):
 assert os.environ['Q02_SOURCE_ORACLE']==str(bundle/'oracles/aima-code.json')
 assert Path(os.environ['Q02_SOURCE_ORACLE']).is_file()
assert 'Q02_SOURCE_ORACLE' not in os.environ
"""
        subprocess.run(
            [sys.executable, "-c", script], check=True, env=env,
            capture_output=True, text=True,
        )

    def test_cleanup_ignores_worker_log_sibling(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            root = state / workload.PHASE / "worker-1"
            root.mkdir(parents=True)
            (state / workload.PHASE / "worker-1.log").write_text("retained")
            (root / "stopped.json").write_text(json.dumps({
                "parser_absent": True, "scratch_absent": True
            }))
            self.assertTrue(workload.cleanup_markers(state)["worker_absent"])

    def test_measurement_uses_warm_window_and_required_evidence(self):
        args = SimpleNamespace(
            python="python", workspace=Path("/workspace"), bundle=Path("/bundle"),
            state=Path("/state"), capacity=Path("/capacity"), prefix=runner.PREFIX,
        )
        argv = workload.build_measurement_argv(args, workload.RUN_ID, "scope")
        self.assertIn("candidate.warm_pod_window_r", argv)
        self.assertIn("pod-topology-v17/RUNTIME-INTEGRATION-MANIFEST.json", " ".join(argv))
        self.assertIn(f"state/{evidence.PHASE}/warm-proof.json", evidence.FINAL_REQUIRED)

    def test_scope_and_inactive_topology(self):
        path = Path("tests/pdf_processing/q04/pod-topology-v17/RUNTIME-INTEGRATION-MANIFEST.json")
        value = json.loads(path.read_text())
        window.validate_scope(SimpleNamespace(
            integration_manifest=path,
            authorization_scope_sha256=value["authorization_scope_sha256"],
            name=workload.PHASE,
            expected_run_id=workload.RUN_ID,
            expected_prefix=runner.PREFIX,
        ))
        self.assertEqual(topology.kubernetes_list()["items"][3]["spec"]["replicas"], 0)

    def test_two_parser_identities_and_exits_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.jsonl"
            rows = [
                {"processes": [
                    {"pid": 11, "start_ticks": 101, "command_class": "warm_parser", "status": "complete"}
                ], "process_events": []},
                {"processes": [
                    {"pid": 22, "start_ticks": 202, "command_class": "warm_parser", "status": "complete"}
                ], "process_events": [
                    {"event": "exit_observed", "pid": 11, "start_ticks": 101}
                ]},
                {"processes": [], "process_events": [
                    {"event": "exit_observed", "pid": 22, "start_ticks": 202}
                ]},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            result = window.validate_process_evidence({
                "process_attribution_complete": True,
                "qualification_complete": True,
                "resource_attribution_path": str(path),
            }, {"pids": [11, 22]})
            self.assertEqual(result["exits"], 2)

    def test_reviewed_yolo_equivalence_accepts_the_retained_runtime_graph(self):
        reference = json.loads(Path("/private/tmp/q04-inputs-warm-lifecycle-q-final4/references/07.json").read_text())
        actual = json.loads(Path(
            "tests/pdf_processing/q04/pod-topology-v10/first-window-evidence/evidence/"
            "state/yolo-pod-cgroup-k/fresh-07/document.json"
        ).read_text())
        with tempfile.TemporaryDirectory() as tmp:
            checker = window.reviewed_reference_checker(
                Path("/private/tmp/q04-inputs-warm-lifecycle-q-final4"),
                lambda *_: self.fail("YOLO fell through to unreviewed checker"),
            )
            checker(actual, reference, Path(tmp))
            self.assertTrue((Path(tmp) / "source-reviewed-equivalence.json").is_file())

    def test_r_contract_seals_mirrors_and_finalizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "remote"
            (root / "state").mkdir(parents=True)
            (root / "state/config.json").write_text("{}")
            identity = evidence.PodEvidenceIdentity(
                "pod", "container", 42, 99, evidence.base.sha256(b"{}")
            )
            def write(name, value):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value) + "\n")
            write("transport-identity.json", identity.__dict__)
            write("supervisor-ownership.json", {"pid": 42, "start_ticks": 99})
            write("ownership.json", {"config_sha256": identity.config_sha256})
            volume = {"pvc_uid": "claim", "pv_uid": "volume"}
            write("evidence-volume-identity.json", volume)
            for name in evidence.FINAL_REQUIRED - {"durable-terminal-manifest.json"}:
                if not (root / name).exists():
                    write(name, {})
            write(f"state/{evidence.MEASUREMENT}/measurement-contract.json", {
                "workload_succeeded": True,
                "qualification_complete": True,
                "cgroup_resource_complete": True,
            })
            write("workload-exit.json", {"returncode": 0, "automatic_retry": False})
            write("cleanup-complete.json", {
                "worker_absent": True,
                "owned_children_absent": True,
                "scratch_absent": True,
            })
            seal(root, volume_identity=volume, workload_succeeded=True, cleanup_complete=True)
            mirror = evidence.IncrementalEvidenceMirror(base / "mirror", identity)
            program = mirror.request_program(str(root)).replace(
                "Path('/proc')", "Path(" + repr(str(base / "proc")) + ")"
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(program, {})
            mirror.ingest(json.loads(output.getvalue()), received_at=1)
            self.assertEqual(mirror.finalize(require_success=True)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
