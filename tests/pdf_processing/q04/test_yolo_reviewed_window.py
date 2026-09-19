"""Offline integration checks for the reviewed fixture-07 candidate window."""

import copy
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from candidate import build_yolo_reviewed_manifest as manifest_builder
from candidate import yolo_reviewed_window as window
from sentinel import run_yolo_reviewed_b as runner


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BUNDLE = Path("/private/tmp/q04-inputs-yolo-lifecycle-v1")
RETAINED_REPLAY = (
    HERE / "candidate/yolo-reviewed-b-fail/RETAINED-REPLAY.json"
)


def sample(memory=2 * 1024**3, *, final=False):
    observations = []
    if final:
        observations = [
            {"label": "owned_cleanup_finished"},
            {"label": "post_cleanup_sample"},
        ]
    return {
        "memory_current": memory,
        "attribution_complete": True,
        "process_coverage": {"status": "complete"},
        "memory_events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
        "memory_pressure_raw": (
            "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
            "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
        ),
        "observations": observations,
    }


def summary(count):
    return {
        "status": "complete",
        "attribution_complete": True,
        "process_attribution_complete": True,
        "qualification_complete": True,
        "cgroup_resource_complete": True,
        "samples": count,
        "incomplete_samples": 0,
        "hard_incomplete_sample_indexes": [],
        "classified_cgroup_transition_sample_indexes": [],
        "unclassified_incomplete_sample_indexes": [],
        "errors": [],
        "missing_required_observation_labels": [],
        "required_observations_in_order": True,
        "no_warm_fresh_overlap": True,
        "warm_fresh_overlap_sample_indexes": [],
        "parser_lifecycle_contract": {"complete": True},
        "maximum_gap_seconds": 0.25,
        "observed_observation_labels": [
            "baseline_before_worker",
            "warm_handoff_observed",
            "owned_cleanup_finished",
            "post_cleanup_sample",
        ],
    }


def accepted_matrix(*, retained_adjacent_pid=False):
    operations = ["group-1-5", "group-6-10", "group-11-15"]
    fresh_groups = []
    for index, operation in enumerate(operations, start=1):
        pid = 1000 + index
        if retained_adjacent_pid and index == 2:
            pid = 1001
        fresh_groups.append(
            {
                "stage": "group",
                "operation": operation,
                "reused": False,
                "parser": {
                    "pid": pid,
                    "recycles": index,
                    "restarts": index,
                },
            }
        )
    request = {
        "request_id": "q04-fresh",
        "artifact": {"key": "q04/reviewed/sources/07.pdf"},
    }
    records = {}
    for mode in window.MODES:
        current_request = copy.deepcopy(request)
        if mode == "restored":
            current_request["request_id"] = "q04-restored"
        groups = (
            copy.deepcopy(fresh_groups)
            if mode == "fresh"
            else [
                {"stage": "group", "operation": operation, "reused": True}
                for operation in operations
            ]
        )
        records[mode] = {
            "sid": "07",
            "mode": mode,
            "request": current_request,
            "profile": {"group_pages": 5},
            "result": {
                "status": "complete",
                "processing_complete": True,
                "pages": 15,
                "steps": groups,
            },
        }
    return records


class ReviewedResourceGateTests(unittest.TestCase):
    def test_gate_accepts_every_complete_sample_and_final_cleanup_markers(self):
        samples = [sample(), sample(window.MAX_CGROUP_BYTES), sample(final=True)]
        result = window.evaluate_resource_gate(samples, summary(len(samples)))
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["final_sample_has_cleanup_markers"])
        self.assertEqual(result["samples_evaluated"], 3)

    def test_retained_exit_race_qualifies_cgroup_but_keeps_pss_unknown(self):
        retained = json.loads(RETAINED_REPLAY.read_text())
        samples = copy.deepcopy(retained["transition_samples"])
        samples[-1]["observations"] = [
            {"label": "owned_cleanup_finished"},
            {"label": "post_cleanup_sample"},
        ]
        retained_summary = summary(len(samples))
        retained_summary.update(
            {
                "status": "qualification_complete_process_attribution_incomplete",
                "attribution_complete": False,
                "process_attribution_complete": False,
                "incomplete_samples": 1,
                "hard_incomplete_sample_indexes": [1],
                "classified_cgroup_transition_sample_indexes": [1],
            }
        )

        result = window.evaluate_resource_gate(samples, retained_summary)

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["process_attribution_incomplete_sample_indexes"], [1])
        self.assertEqual(result["classified_cgroup_transition_sample_indexes"], [1])
        self.assertEqual(result["incomplete_sample_indexes"], [])
        self.assertFalse(samples[1]["attribution_complete"])
        self.assertIsNone(samples[1]["processes"][-1]["pss_bytes"])

        retained_summary["classified_cgroup_transition_sample_indexes"] = []
        result = window.evaluate_resource_gate(samples, retained_summary)
        self.assertEqual(result["status"], "FAIL_RESOURCE_GATE")
        self.assertEqual(result["incomplete_sample_indexes"], [1])

    def test_gate_rejects_each_fixed_resource_boundary(self):
        cases = {}

        over = [sample(), sample(window.MAX_CGROUP_BYTES + 1), sample(final=True)]
        cases["memory"] = (over, summary(len(over)), "memory_violations")

        incomplete = [sample(), sample(final=True)]
        incomplete[0]["attribution_complete"] = False
        incomplete[0]["process_coverage"]["status"] = "incomplete"
        incomplete_summary = summary(len(incomplete))
        incomplete_summary["attribution_complete"] = False
        incomplete_summary["incomplete_samples"] = 1
        incomplete_summary["hard_incomplete_sample_indexes"] = [0]
        incomplete_summary["status"] = "incomplete"
        cases["incomplete"] = (
            incomplete,
            incomplete_summary,
            "incomplete_sample_indexes",
        )

        oom = [sample(), sample(final=True)]
        oom[0]["memory_events"]["oom_kill"] = 1
        cases["oom"] = (oom, summary(len(oom)), "oom_violations")

        missing_oom = [sample(), sample(final=True)]
        missing_oom[0]["memory_events"].pop("oom_kill")
        cases["missing_oom"] = (
            missing_oom,
            summary(len(missing_oom)),
            "oom_violations",
        )

        missing_oom_group = [sample(), sample(final=True)]
        missing_oom_group[0]["memory_events"].pop("oom_group_kill")
        cases["missing_oom_group"] = (
            missing_oom_group,
            summary(len(missing_oom_group)),
            "oom_violations",
        )

        for event in ("oom", "oom_kill", "oom_group_kill"):
            for label, value in (("null", None), ("string", "0"), ("bool", False)):
                malformed = [sample(), sample(final=True)]
                malformed[0]["memory_events"][event] = value
                cases[f"{event}_{label}"] = (
                    malformed,
                    summary(len(malformed)),
                    "oom_violations",
                )

        psi = [sample(), sample(final=True)]
        psi[0]["memory_pressure_raw"] = (
            "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
            "full avg10=0.01 avg60=0.00 avg300=0.00 total=1\n"
        )
        cases["psi"] = (psi, summary(len(psi)), "psi_violations")

        early_cleanup = [sample(final=True), sample()]
        cases["early_cleanup"] = (
            early_cleanup,
            summary(len(early_cleanup)),
            "final_sample_has_cleanup_markers",
        )

        missing_memory = [sample(), sample(final=True)]
        missing_memory[0]["memory_current"] = None
        cases["missing_memory"] = (
            missing_memory,
            summary(len(missing_memory)),
            "memory_violations",
        )

        for name, (samples, retained_summary, field) in cases.items():
            with self.subTest(name=name):
                result = window.evaluate_resource_gate(samples, retained_summary)
                self.assertEqual(result["status"], "FAIL_RESOURCE_GATE")
                if field == "final_sample_has_cleanup_markers":
                    self.assertFalse(result[field])
                else:
                    self.assertTrue(result[field])


class ReviewedWindowIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def args(self, root):
        bundle = root / "bundle"
        bundle.mkdir()
        (bundle / "inputs.json").write_text(
            json.dumps(
                {
                    "base_profile": {"group_pages": 5},
                    "fixtures": [
                        {"id": "07", "original_pages": list(range(1, 16))}
                    ],
                }
            )
        )
        state = root / "state"
        state.mkdir()
        (state / "config.json").write_text(
            json.dumps({"parser_budgets": window.PARSER_BUDGETS})
        )
        return SimpleNamespace(bundle=bundle, state=state, name="reviewed")

    async def fake_lifecycle(
        self, args, *, resource_failure=False, retained_adjacent_pid=False
    ):
        trial = args.state / args.name
        trial.mkdir()
        accepted = accepted_matrix(retained_adjacent_pid=retained_adjacent_pid)
        for mode in window.MODES:
            target = trial / f"{mode}-07"
            target.mkdir()
            __import__("consumer").check_reference({}, {}, target)
            (target / "accepted.json").write_text(json.dumps(accepted[mode]))
        __import__("q04_runtime").write(
            trial / "fresh-index.json", {"07": str(trial / "fresh-07")}
        )
        __import__("q04_runtime").write(
            trial / "phase-complete.json", {"status": "premature"}
        )
        measurement = args.state / (args.name + "-measurement")
        measurement.mkdir()
        samples = [sample(), sample(final=True)]
        if resource_failure:
            samples[0]["memory_current"] = window.MAX_CGROUP_BYTES + 1
        (measurement / "resource-attribution.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in samples)
        )
        (measurement / "resource-attribution-summary.json").write_text(
            json.dumps(summary(len(samples)))
        )

    def reviewed_checker(self, _args, calls):
        def check(_document, _reference, out):
            calls.append(out.name)
            return "reference-sha"

        return check

    async def test_fresh_index_is_promoted_only_after_resource_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory))
            reviewed = {
                "artifact_sha256": {
                    "equivalence_bundle": "equivalence",
                    "parser_budgets": "budgets",
                }
            }
            async def accepted(value):
                await self.fake_lifecycle(value)

            with mock.patch.object(
                window, "validate_reviewed_inputs", return_value=reviewed
            ), mock.patch.object(
                window, "_reviewed_reference_checker", self.reviewed_checker
            ), mock.patch.object(
                window,
                "run_lifecycle_window",
                new=accepted,
            ):
                await window.run_window(args)

            trial = args.state / args.name
            self.assertTrue((trial / "fresh-index.pending.json").is_file())
            self.assertTrue((trial / "fresh-index.json").is_file())
            self.assertTrue((trial / "runtime-phase-complete.pending.json").is_file())
            contract = json.loads((trial / "reviewed-window-contract.json").read_text())
            self.assertEqual(contract["resource_gate"]["status"], "PASS")
            self.assertEqual(
                contract["parser_recycle_contract"]["fresh_parser_recycles"],
                [1, 2, 3],
            )
            self.assertTrue(contract["fresh_index_integrated"])

    async def test_resource_failure_retains_pending_index_without_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory))
            reviewed = {
                "artifact_sha256": {
                    "equivalence_bundle": "equivalence",
                    "parser_budgets": "budgets",
                }
            }
            async def rejected(value):
                await self.fake_lifecycle(value, resource_failure=True)

            with mock.patch.object(
                window, "validate_reviewed_inputs", return_value=reviewed
            ), mock.patch.object(
                window, "_reviewed_reference_checker", self.reviewed_checker
            ), mock.patch.object(
                window,
                "run_lifecycle_window",
                new=rejected,
            ):
                with self.assertRaisesRegex(ValueError, "resource gate failed"):
                    await window.run_window(args)

            trial = args.state / args.name
            self.assertTrue((trial / "fresh-index.pending.json").is_file())
            self.assertFalse((trial / "fresh-index.json").exists())
            failure = json.loads((trial / "reviewed-window-failure.json").read_text())
            self.assertFalse(failure["fresh_index_integrated"])
            self.assertFalse(failure["automatic_retry"])

    async def test_retained_parser_pid_fails_before_index_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory))
            reviewed = {
                "artifact_sha256": {
                    "equivalence_bundle": "equivalence",
                    "parser_budgets": "budgets",
                }
            }

            async def rejected(value):
                await self.fake_lifecycle(value, retained_adjacent_pid=True)

            with mock.patch.object(
                window, "validate_reviewed_inputs", return_value=reviewed
            ), mock.patch.object(
                window, "_reviewed_reference_checker", self.reviewed_checker
            ), mock.patch.object(
                window, "run_lifecycle_window", new=rejected
            ):
                with self.assertRaisesRegex(
                    ValueError, "parser PID was reused across adjacent groups"
                ):
                    await window.run_window(args)

            trial = args.state / args.name
            self.assertFalse((trial / "fresh-index.json").exists())
            failure = json.loads((trial / "reviewed-window-failure.json").read_text())
            self.assertEqual(failure["status"], "FAIL_PARSER_RECYCLE_CONTRACT")
            self.assertFalse(failure["automatic_retry"])


class ReviewedRunnerOfflineTests(unittest.TestCase):
    def test_fixture_local_consumer_accepts_only_the_bound_retained_graph(self):
        args = runner._validation_args()
        calls = []
        checker = window._reviewed_reference_checker(args, calls)
        reference = json.loads((BUNDLE / "references/07.json").read_text())
        actual = json.loads(
            Path(
                "/private/tmp/q04-yolo-lifecycle-20260919-a/retained-document.json"
            ).read_text()
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            graph_sha = checker(actual, reference, output)
            record = json.loads(
                (output / "source-reviewed-equivalence.json").read_text()
            )
        self.assertEqual(
            graph_sha,
            "b270e1818bdeecf5f88cc83766c8ab3fa1e89a1586fb0cacbfbf049614a8c276",
        )
        self.assertEqual(record["status"], "PASS_FIXTURE_LOCAL_REVIEWED_EQUIVALENCE")
        self.assertFalse(record["historical_reference_mutated"])
        self.assertFalse(record["general_normalization"])

        changed = copy.deepcopy(actual)
        changed["furniture"]["name"] = "unreviewed-change"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaisesRegex(AssertionError, "candidate_graph_sha256"):
                checker(changed, reference, output)
            failure = json.loads(
                (output / "source-reviewed-equivalence-failure.json").read_text()
            )
        self.assertEqual(failure["status"], "FAIL_REVIEWED_EQUIVALENCE")
        self.assertFalse(failure["automatic_retry"])

    def test_manifest_rebuilds_exactly_and_keeps_policy_local(self):
        committed = json.loads(runner.INTEGRATION_MANIFEST.read_text())
        rebuilt = manifest_builder.build(REPO, BUNDLE)
        self.assertEqual(rebuilt, committed)
        self.assertEqual(
            committed["status"], "HISTORICAL_FAILED_RECONCILED_OFFLINE"
        )
        self.assertFalse(committed["runtime_authorized"])
        self.assertFalse(committed["production_default_changed"])
        self.assertEqual(committed["parser_policy"]["after_max_requests"], 1)
        self.assertFalse(committed["failure_policy"]["other_fixture_policy_inherited"])
        policy = committed["authorization_scope"]["process_attribution_policy"]
        self.assertTrue(policy["raw_incomplete_preserved"])
        self.assertFalse(policy["pss_substitution_allowed"])
        self.assertTrue(
            policy["classified_exit_applies_to_cgroup_qualification_only"]
        )
        self.assertEqual(
            committed["authorization_scope_sha256"],
            runner.authorization_scope_sha256(),
        )

    def test_offline_manifest_binds_entrypoint_budget_oracle_and_scope(self):
        record = runner.offline_validation_record()
        self.assertEqual(record["status"], "PASS offline only")
        self.assertFalse(record["runtime_authorized"])
        self.assertEqual(record["parser_budgets"], window.PARSER_BUDGETS)
        self.assertEqual(record["modes"], window.MODES)
        command = runner.build_runtime_command("q04-offline-reviewed-candidate")
        self.assertIn("--signal=INT --kill-after=180s 825s", command)
        self.assertIn("yolo_reviewed_window.py", command)
        self.assertIn("--authorization-scope-sha256", command)
        self.assertIn("test ! -e", command)

    def test_inherited_launcher_and_control_inputs_are_hash_and_git_bound(self):
        sources = runner.staged_sources()
        inherited = {
            "run_yolo_lifecycle_a.py": HERE
            / "sentinel/run_yolo_lifecycle_a.py",
            "capacity-candidates.json": HERE
            / "diagnosis/evidence/capacity-candidates.json",
            "remote_probe.py": HERE / "preflight/remote_probe.py",
        }
        for name, path in inherited.items():
            self.assertEqual(sources[name], path)

        retained = json.loads(runner.OFFLINE_MANIFEST.read_text())
        for name in inherited:
            self.assertEqual(
                retained["staged_sources"][name], runner._sha(sources[name])
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in inherited:
                with self.subTest(name=name):
                    changed = root / name
                    changed.write_bytes(sources[name].read_bytes() + b"\nmutated\n")
                    mutated = dict(sources)
                    mutated[name] = changed
                    with self.assertRaisesRegex(RuntimeError, "staged source changed"):
                        runner.reviewed_source_hashes(mutated)

    def test_reviewed_inputs_reject_other_fixture_budget_or_scope(self):
        args = runner._validation_args()
        bundle = json.loads((BUNDLE / "inputs.json").read_text())
        config = {
            "parser_budgets": window.PARSER_BUDGETS,
            "profiles": {"07": {"method": bundle["base_profile"]["method"]}},
        }
        changed_fixture = copy.copy(args)
        changed_fixture.fixture = "08"
        with self.assertRaisesRegex(ValueError, "fixture-07 only"):
            window.validate_reviewed_inputs(changed_fixture, config, bundle)

        changed_budget = copy.deepcopy(config)
        changed_budget["parser_budgets"]["max_requests"] = 20
        with self.assertRaisesRegex(ValueError, "parser budget identity changed"):
            window.validate_reviewed_inputs(args, changed_budget, bundle)

        changed_scope = copy.copy(args)
        changed_scope.authorization_scope_sha256 = "0" * 64
        with self.assertRaisesRegex(ValueError, "authorization scope identity changed"):
            window.validate_reviewed_inputs(changed_scope, config, bundle)

    def test_launcher_refuses_missing_or_mismatched_single_run_scope(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.main([])
            with self.assertRaises(SystemExit):
                runner.main(
                    [
                        "--execute",
                        "--owner",
                        "offline",
                        "--approval-reference",
                        "not-authorized",
                        "--authorization-scope-sha256",
                        "0" * 64,
                    ]
                )

    def test_consumed_historical_launcher_refuses_formerly_valid_scope(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.main(
                    [
                        "--execute",
                        "--owner",
                        "offline",
                        "--approval-reference",
                        "historical-only",
                        "--authorization-scope-sha256",
                        runner.authorization_scope_sha256(),
                    ]
                )

    def test_runtime_default_remains_20_and_adoption_is_new_state_only(self):
        runtime = (HERE / "q04_runtime.py").read_text()
        self.assertIn("'max_requests': 20", runtime)
        plan = (runner.INTEGRATION_ROOT / "RUN-PLAN.md").read_text()
        self.assertIn("window-local resource hypothesis", plan)
        self.assertIn("must not be copied", plan)
        self.assertEqual(window.BASELINE_PARSER_BUDGETS["max_requests"], 20)
        self.assertEqual(window.PARSER_BUDGETS["max_requests"], 1)

    def test_budget_adoption_changes_only_new_state_and_records_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "state").mkdir()
            (root / "runner-yolo-reviewed-b").mkdir()
            before = {
                "run_id": "q04-new-identity",
                "parser_budgets": window.BASELINE_PARSER_BUDGETS,
                "unchanged": {"group_size": 5, "concurrency": 1},
            }
            (root / "state/config.json").write_text(json.dumps(before))
            budget_path = root / "runner-yolo-reviewed-b/parser-budgets.json"
            budget_path.write_text(json.dumps(window.PARSER_BUDGETS))
            output = subprocess.check_output(
                [
                    sys.executable,
                    "-c",
                    runner.build_budget_adoption_program(root=str(root)),
                ]
            )
            record = json.loads(output)
            after = json.loads((root / "state/config.json").read_text())

        self.assertEqual(after["run_id"], before["run_id"])
        self.assertEqual(after["unchanged"], before["unchanged"])
        self.assertEqual(after["parser_budgets"], window.PARSER_BUDGETS)
        self.assertEqual(record["before"], window.BASELINE_PARSER_BUDGETS)
        self.assertEqual(record["after"], window.PARSER_BUDGETS)
        self.assertFalse(record["production_default_changed"])

    def test_initialized_state_probe_binds_new_budget_identity(self):
        bundle = json.loads((BUNDLE / "inputs.json").read_text())
        profile_keys = sorted(
            {row["id"] for row in bundle["fixtures"]}
            | {"native-evidence", "native-method"}
        )
        capacity = runner.lifecycle.build_capacity(
            started_at=1000,
            owner="offline",
            approval_reference="offline-only",
        )
        initialized = {
            "run_id": "q04-reviewed-new",
            "prefix": runner.PREFIX,
            "bundle": runner.REMOTE + "/inputs",
            "bundle_sha256": runner.lifecycle.EXPECTED_BUNDLE_SHA256,
            "state_sha256": "fixed-state",
            "producer": bundle["producer"],
            "profile_method": bundle["base_profile"]["method"],
            "profile_id": bundle["base_profile"]["id"],
            "profile_release": "q04-reviewed-release",
            "config_keys": sorted(
                {
                    "run_id", "profiles", "producer", "bundle", "state",
                    "temporal", "endpoint", "bucket", "prefix", "window",
                    "model_cache", "python", "pod_namespace", "trial_seconds",
                    "workflow_queue", "queues", "limits", "parser_budgets",
                    "drain_seconds", "bundle_sha256",
                }
            ),
            "profile_keys": profile_keys,
            "queue_keys": profile_keys,
            "window_keys": sorted(capacity),
            "parser_budgets": window.PARSER_BUDGETS,
            "budget_adoption": {
                "candidate": "q04-yolo-reviewed-v1",
                "before": window.BASELINE_PARSER_BUDGETS,
                "after": window.PARSER_BUDGETS,
                "parser_budgets_sha256": runner.integration_manifest()["artifacts"][
                    "parser_budgets"
                ],
            },
            "budget_adoption_sha256": "fixed-record",
        }
        runner.validate_initialized_state(initialized, bundle)

        changed = copy.deepcopy(initialized)
        changed["parser_budgets"]["max_requests"] = 20
        with self.assertRaisesRegex(RuntimeError, "candidate parser budgets changed"):
            runner.validate_initialized_state(changed, bundle)


if __name__ == "__main__":
    unittest.main()
