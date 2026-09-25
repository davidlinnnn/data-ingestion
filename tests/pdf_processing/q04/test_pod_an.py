"""Local contracts for the v3-bound native method invalidation Pod adapter."""

import copy
import asyncio
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

from candidate.method_invalidation_window_an import measurement_contract, switch_to_method_worker, validate_invalidation, validate_scope
from candidate.warm_v3_reference import reviewed_reference_checker, verify_v3_bundle
from consumer import check_reference
import pod_preflight_an as preflight
import pod_remote_evidence_an as evidence
import pod_topology_an as topology
import pod_workload_an as workload
from sentinel import run_method_pod_cgroup_an as runner
from pod_durable_evidence import seal


BUNDLE = Path("/private/tmp/q04-inputs-warm-continuation-v3-ah")
CAPTURES = Path("/private/tmp/q04-local-native-v3-envelope")


class ANProfilePodAdapterTest(unittest.TestCase):
    def test_method_switch_stops_old_worker_before_starting_new_generation(self):
        calls = []
        class Host:
            generation = 1
            async def stop(self):
                calls.append("stop")
            async def prepare_start(self):
                calls.append("prepare")
            async def launch_start(self):
                calls.append("launch")
                self.generation += 1
            async def await_ready(self):
                calls.append("ready")
                await asyncio.sleep(1.1)
        class Collector:
            async def process_transition(self, label, operation):
                calls.append(label)
                await asyncio.wait_for(operation(), 1)
        host = Host()
        run = SimpleNamespace(initial={"old": True})
        asyncio.run(switch_to_method_worker(Collector(), host, run))
        self.assertEqual(calls, ["method_worker_shutdown", "stop", "prepare",
                                 "method_worker_start", "launch", "ready"])
        self.assertEqual(host.generation, 2)
        self.assertIsNone(run.initial)

    @classmethod
    def setUpClass(cls):
        if not (BUNDLE / "inputs.json").exists():
            raise unittest.SkipTest("private AH bundle unavailable")

    def test_identity_argv_and_inactive_topology(self):
        manifest = json.loads((topology.base.Q04 / "pod-topology-v39/RUNTIME-INTEGRATION-MANIFEST.json").read_text())
        self.assertEqual(manifest["identity"], {
            "phase": workload.PHASE,
            "run_id": runner.RUN_IDENTITY,
            "prefix": runner.PREFIX,
        })
        self.assertEqual(topology.OBJECT_PREFIX, runner.PREFIX)
        self.assertEqual(topology.source_manifest()["producer"]["continuation.py"],
                         verify_v3_bundle(BUNDLE)[0]["continuation_source_sha256"])
        self.assertEqual(topology.kubernetes_list()["items"][3]["spec"]["replicas"], 0)
        self.assertFalse(runner.authorization_scope()["automatic_retry"])
        self.assertEqual(runner.authorization_scope()["group_requests"], 22)
        self.assertEqual(runner.authorization_scope()["expected_parser_generations"], 2)
        self.assertNotEqual(runner.PREFIX, "q04/warm-pod-cgroup-20260924-ah/")
        self.assertIn("pod_workload_an.py", runner.workload_argv()[1])
        self.assertIn("pod_preflight_an.py", runner.preflight_argv()[1])
        measurement = workload.build_measurement_argv(
            type("Args", (), {"python": sys.executable, "bundle": BUNDLE,
                "state": Path("/state"), "capacity": Path("/capacity"),
                "prefix": runner.PREFIX, "workspace": topology.base.ROOT})(),
            runner.RUN_IDENTITY, manifest["authorization_scope_sha256"])
        self.assertIn("candidate.method_invalidation_window_an", measurement)
        self.assertIn("pod-topology-v39/RUNTIME-INTEGRATION-MANIFEST.json",
                      " ".join(measurement))
        self.assertEqual(runner.base.validate_created_deployment.__kwdefaults__["deployment_name"],
                         topology.DEPLOYMENT)
        self.assertEqual(runner.base.cleanup_deployment_and_pod.__kwdefaults__["deployment_name"],
                         topology.DEPLOYMENT)
        self.assertEqual(runner.base.offline_check()["status"], "PASS_OFFLINE_ONLY")

    def test_preflight_contract_and_stale_bundle_rejection(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            capacity = root / "capacity.json"
            capacity.write_text(json.dumps({
                "status": "AUTHORIZED", "phase": preflight.PHASE,
                "authorization_scope_sha256": runner.authorization_scope_sha256(),
                "automatic_retry": False, "proposed_window_seconds": 1500,
                "outer_observation_seconds": 180, "outer_continuous_seconds": 60,
                "outer_admission_available_bytes": 4_831_838_208,
                "admission_available_bytes": 3_221_225_472,
                "minimum_work_seconds": 825, "cleanup_seconds": 300,
                "max_cgroup_bytes": 4_294_967_296,
                "container_hard_limit_bytes": 5_368_709_120,
            }))
            source = root / "source.json"
            source.write_text(json.dumps(topology.source_manifest()))
            kwargs = dict(capacity=capacity,
                          authorization_scope_sha256=runner.authorization_scope_sha256(),
                          source_manifest_path=source, bundle=BUNDLE,
                          expected_bundle_sha256=preflight.sha256(BUNDLE / "inputs.json"))
            self.assertEqual(preflight.verify_configuration_an(**kwargs)[1]["status"], "PASS")
            with self.assertRaisesRegex(ValueError, "frozen bundle inputs changed"):
                preflight.verify_configuration_an(**{**kwargs, "expected_bundle_sha256": "0" * 64})
            with self.assertRaisesRegex(ValueError, "capacity configuration changed"):
                capacity.write_text(capacity.read_text().replace("1500", "1501"))
                preflight.verify_configuration_an(**kwargs)

    def test_exact_graph_and_method_fail_closed(self):
        if not (CAPTURES / "capture-native/document.json").exists():
            self.skipTest("offline captures unavailable")
        checker = reviewed_reference_checker(BUNDLE, check_reference)
        for sid in ("native",):
            document = json.loads((CAPTURES / f"capture-{sid}/document.json").read_text())
            reference = json.loads((BUNDLE / "references" / f"{sid}.json").read_text())
            with self.subTest(sid=sid), tempfile.TemporaryDirectory() as raw:
                self.assertEqual(checker(document, reference, Path(raw)),
                                 verify_v3_bundle(BUNDLE)[0]["local_v3_graph_sha256"][sid])
                altered = copy.deepcopy(document)
                altered["texts"][0]["text"] += "!"
                with self.assertRaisesRegex(ValueError, "graph differs"):
                    checker(altered, reference, Path(raw))
        with tempfile.TemporaryDirectory() as raw:
            candidate = Path(raw)
            data = json.loads((BUNDLE / "inputs.json").read_text())
            data["base_profile"]["method"]["continuation"]["version"] = "column-edge-continuation-v2"
            (candidate / "inputs.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "bundle or oracle bytes changed"):
                verify_v3_bundle(candidate)
        reference = json.loads((BUNDLE / "references/native.json").read_text())
        manifest = json.loads((topology.base.Q04 / "pod-topology-v39/RUNTIME-INTEGRATION-MANIFEST.json").read_text())
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(check_reference(reference, reference, Path(raw)),
                             manifest["method_off_reference_graph_sha256"])
            altered = copy.deepcopy(reference)
            altered["texts"][0]["text"] += "!"
            with self.assertRaisesRegex(ValueError, "unreviewed full graph delta"):
                check_reference(altered, reference, Path(raw))

    def test_cleanup_ignores_worker_log_and_preserves_stop_proof(self):
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            phase = state / workload.PHASE
            worker = phase / "worker-1"
            worker.mkdir(parents=True)
            (phase / "worker-1.log").write_text("retained log")
            (worker / "stopped.json").write_text(json.dumps({
                "parser_absent": True, "scratch_absent": True}))
            self.assertEqual(workload.cleanup_markers(state)["worker_generations"], 1)
            self.assertTrue(workload.cleanup_markers(state)["owned_children_absent"])

    def test_scope_and_method_invalidation_fail_closed(self):
        path = topology.base.Q04 / "pod-topology-v39/RUNTIME-INTEGRATION-MANIFEST.json"
        manifest = json.loads(path.read_text())
        args = SimpleNamespace(integration_manifest=path,
            authorization_scope_sha256=manifest["authorization_scope_sha256"],
            name=workload.PHASE, expected_run_id=runner.RUN_IDENTITY,
            expected_prefix=runner.PREFIX, bundle=BUNDLE)
        self.assertEqual(validate_scope(args), manifest)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            mutated = json.loads(path.read_text())
            mutated["native_document_sha256"] = "0" * 64
            changed = root / "manifest.json"
            changed.write_text(json.dumps(mutated))
            with self.assertRaisesRegex(ValueError, "AI native document target changed"):
                validate_scope(SimpleNamespace(**{**vars(args), "integration_manifest": changed}))
            request = {"request_id": "same", "artifact": {"key": "native"}}
            original = {"id": "native-v1", "release": "old",
                        "method": {"version": 3, "continuation": "v3"},
                        "content_evidence": "original"}
            changed_profile = {**original, "release": "new", "method": {"version": 3}}
            upstream = [{"stage": "group", "operation": str(i)} for i in range(11)] + [
                {"stage": "assembly", "operation": "assembly"}]
            for mode in ("fresh", "invalidation", "replay"):
                target = root / f"{mode}-native"
                target.mkdir()
                steps = [{**step, "operation": step["operation"] + "-new"
                          if mode == "invalidation" else step["operation"],
                          "reused": mode == "replay"} for step in upstream]
                steps += [{"stage": "component_ocr", "reused": mode == "replay"}
                          for _ in range(7)]
                (target / "accepted.json").write_text(json.dumps({
                    "request": ({**request, "request_id": "new"} if mode == "invalidation" else request),
                    "producer": {"version": "v3"},
                    "profile": changed_profile if mode == "invalidation" else original,
                    "verified": True,
                    "result": {"status": "complete", "processing_complete": True,
                               "registered_pages": 51, "registered_components": 7,
                               "processing_result": "new" if mode == "invalidation" else "original",
                               "steps": steps},
                    "accepted": {"document_sha256": ("method-off" if mode == "invalidation"
                                                     else manifest["native_document_sha256"]),
                                 "checks": {"full_reference_graph_sha256":
                                            manifest["method_off_reference_graph_sha256"]},
                                 "final": {"content_evidence": mode}},
                }))
            validate_invalidation(root, manifest)
            record = root / "invalidation-native/accepted.json"
            value = json.loads(record.read_text())
            value["result"]["steps"][0]["reused"] = True
            record.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "old group/assembly work survived method change"):
                validate_invalidation(root, manifest)

    def test_success_contract_seals_and_finalizes_in_am_mirror(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            root = base / "remote"
            (root / "state").mkdir(parents=True)
            (root / "state/config.json").write_text("{}")
            identity = evidence.PodEvidenceIdentity(
                "pod", "container", 42, 99, evidence.base.sha256(b"{}"))
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
            contract = measurement_contract(
                SimpleNamespace(qualification_complete=True, cgroup_resource_complete=True),
                {"process_attribution_complete": True}, {"status": "PASS"})
            write(f"state/{evidence.MEASUREMENT}/measurement-contract.json", contract)
            write("workload-exit.json", {"returncode": 0, "automatic_retry": False})
            write("cleanup-complete.json", {
                "worker_absent": True, "owned_children_absent": True, "scratch_absent": True})
            seal(root, volume_identity=volume, workload_succeeded=True, cleanup_complete=True)
            mirror = evidence.IncrementalEvidenceMirror(base / "mirror", identity)
            program = mirror.request_program(str(root)).replace(
                "Path('/proc')", "Path(" + repr(str(base / "proc")) + ")")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(program, {})
            mirror.ingest(json.loads(output.getvalue()), received_at=1)
            self.assertEqual(mirror.finalize(require_success=True)["status"], "PASS")

    @unittest.skipUnless(importlib.util.find_spec("pypdfium2"), "pinned image required")
    def test_exact_projected_workspace_imports(self):
        rendered = topology.kubernetes_list()
        maps = {item["metadata"]["name"]: item["data"] for item in rendered["items"]
                if item["kind"] == "ConfigMap"}
        deployment = next(item for item in rendered["items"] if item["kind"] == "Deployment")
        volume = next(item for item in deployment["spec"]["template"]["spec"]["volumes"]
                      if item["name"] == "workspace")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for source in volume["projected"]["sources"]:
                projection = source["configMap"]
                for item in projection["items"]:
                    path = root / item["path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(maps[projection["name"]][item["key"]])
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONPATH"] = os.pathsep.join((str(root / "src"),
                str(root / "tests/pdf_processing/q04"),
                str(root / "tests/pdf_processing/q02"),
                str(root / "tests/pdf_processing/q03")))
            result = subprocess.run([sys.executable, "-c",
                "import pod_preflight_an; from pathlib import Path; "
                "pod_preflight_an.verify_workload_imports_an("
                f"workspace=Path({str(root)!r}),"
                f"bundle=Path({str(BUNDLE)!r}),"
                f"prefix={runner.PREFIX!r})"],
                cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
