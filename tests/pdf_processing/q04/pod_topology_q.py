"""Render P's inactive Pod topology with Q's unique identity and source set."""

import json

import pod_topology_p as base


base.PHASE = "q04-pod-cgroup-q"
base.DEPLOYMENT = base.PHASE + "-activities"
base.RUN_LABEL = base.PHASE
base.WORKFLOW_QUEUE = base.PHASE + "-workflows"
base.ACTIVITY_QUEUE = base.PHASE + "-08"
base.OBJECT_PREFIX = "q04/aima-pod-cgroup-20260920-q/"
base.EVIDENCE_PVC = "q04-pod-cgroup-q-evidence-20260920-q"
base.EVIDENCE_DIRECTORY_NAME = "q04-aima-pod-cgroup-20260920-q"
base.PRODUCER_MANIFEST = base.Q04 / "candidate/warm-lifecycle-q/MANIFEST.json"
base.FROZEN_TEST_FILES = tuple(
    json.loads(base.PRODUCER_MANIFEST.read_text())["test_files"]
)
base.POD_ONLY_FILES = tuple(
    dict.fromkeys(
        base.POD_ONLY_FILES
        + (
            "tests/pdf_processing/q04/candidate/aima_pod_window_q.py",
            "tests/pdf_processing/q04/sentinel/aima_attribution_telemetry_q.py",
            "tests/pdf_processing/q04/pod_workload_q.py",
            "tests/pdf_processing/q04/pod_preflight_q.py",
            "tests/pdf_processing/q04/pod_remote_evidence_q.py",
            "tests/pdf_processing/q04/pod_topology_q.py",
            "tests/pdf_processing/q04/pod-topology-v16/RUNTIME-INTEGRATION-MANIFEST.json",
        )
    )
)
base.HARNESS_FILES = {
    name: base.ROOT / name
    for name in sorted(set(base.FROZEN_TEST_FILES + base.POD_ONLY_FILES))
}

PHASE = base.PHASE
DEPLOYMENT = base.DEPLOYMENT
RUN_LABEL = base.RUN_LABEL
WORKFLOW_QUEUE = base.WORKFLOW_QUEUE
ACTIVITY_QUEUE = base.ACTIVITY_QUEUE
OBJECT_PREFIX = base.OBJECT_PREFIX
EVIDENCE_PVC = base.EVIDENCE_PVC
EVIDENCE_DIRECTORY_NAME = base.EVIDENCE_DIRECTORY_NAME
NAMESPACE = base.NAMESPACE
NODE = base.NODE
source_manifest = base.source_manifest
kubernetes_list = base.kubernetes_list
validate = base.validate
render = base.render
