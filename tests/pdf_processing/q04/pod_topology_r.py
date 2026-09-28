"""Render Q's inactive Pod topology with R's warm identity."""

import importlib.util
import json
from pathlib import Path
import sys


_spec = importlib.util.spec_from_file_location("q04_pod_topology_r_engine", Path(__file__).with_name("pod_topology_p.py"))
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base
_spec.loader.exec_module(base)


base.PHASE = "q04-pod-cgroup-r"
base.DEPLOYMENT = base.PHASE + "-activities"
base.RUN_LABEL = base.PHASE
base.WORKFLOW_QUEUE = base.PHASE + "-workflows"
base.ACTIVITY_QUEUE = base.PHASE + "-08"
base.OBJECT_PREFIX = "q04/warm-pod-cgroup-20260921-r/"
base.EVIDENCE_PVC = "q04-pod-cgroup-r-evidence-20260921-r"
base.EVIDENCE_DIRECTORY_NAME = "q04-warm-pod-cgroup-20260921-r"
base.PRODUCER_MANIFEST = base.Q04 / "candidate/warm-lifecycle-q/MANIFEST.json"
base.FROZEN_TEST_FILES = tuple(
    json.loads(base.PRODUCER_MANIFEST.read_text())["test_files"]
)
base.POD_ONLY_FILES = tuple(dict.fromkeys(base.POD_ONLY_FILES + (
    "tests/pdf_processing/q04/candidate/warm_pod_window_r.py",
    "tests/pdf_processing/q04/candidate/yolo-equivalence-v2/ADOPTION.json",
    "tests/pdf_processing/q04/pod_workload_r.py",
    "tests/pdf_processing/q04/pod_preflight_r.py",
    "tests/pdf_processing/q04/pod_remote_evidence_r.py",
    "tests/pdf_processing/q04/pod_topology_r.py",
    "tests/pdf_processing/q04/pod-topology-v17/RUNTIME-INTEGRATION-MANIFEST.json",
)))
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
