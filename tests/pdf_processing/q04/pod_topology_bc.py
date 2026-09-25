"""Render the inactive Pod topology for worker-process drain verification."""

import importlib.util
import json
from pathlib import Path
import sys


_spec = importlib.util.spec_from_file_location(
    "q04_pod_topology_bc_engine", Path(__file__).with_name("pod_topology_p.py")
)
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base
_spec.loader.exec_module(base)


base.PHASE = "q04-pod-cgroup-bc"
base.DEPLOYMENT = base.PHASE + "-activities"
base.RUN_LABEL = base.PHASE
base.WORKFLOW_QUEUE = base.PHASE + "-workflows"
base.ACTIVITY_QUEUE = base.PHASE + "-08"
base.OBJECT_PREFIX = "q04/process-drain-pod-cgroup-20260925-bc/"
base.EVIDENCE_PVC = "q04-pod-cgroup-bc-evidence-20260925-bc"
base.EVIDENCE_DIRECTORY_NAME = "q04-process-drain-pod-cgroup-20260925-bc"
base.PRODUCER_MANIFEST = base.Q04 / "candidate/warm-continuation-v3-ah/MANIFEST.json"
base.FROZEN_TEST_FILES = tuple(
    json.loads(base.PRODUCER_MANIFEST.read_text())["test_files"]
)
base.POD_ONLY_FILES = tuple(dict.fromkeys(base.POD_ONLY_FILES + (
    "tests/pdf_processing/q04/candidate/process_drain_window_bc.py",
    "tests/pdf_processing/q04/candidate/warm_pod_window_r.py",
    "tests/pdf_processing/q04/candidate/warm_v3_reference.py",
    "tests/pdf_processing/q04/candidate/warm-continuation-v3-ah/MANIFEST.json",
    "tests/pdf_processing/q04/diagnosis/continuation-v2/exact_oracle.py",
    "tests/pdf_processing/q04/diagnosis/continuation-v3/EXACT-ORACLE.json",
    "tests/pdf_processing/q04/pod-topology-v33/first-window-evidence/INDEPENDENT-VERIFICATION.json",
    "tests/pdf_processing/q04/pod-topology-v34/first-window-evidence/INDEPENDENT-VERIFICATION.json",
    "tests/pdf_processing/q04/candidate/yolo-equivalence-v2/ADOPTION.json",
    "tests/pdf_processing/q04/pod_workload_bc.py",
    "tests/pdf_processing/q04/pod_preflight_bc.py",
    "tests/pdf_processing/q04/pod_preflight_q.py",
    "tests/pdf_processing/q04/pod_remote_evidence_bc.py",
    "tests/pdf_processing/q04/pod_topology_bc.py",
    "tests/pdf_processing/q04/host_bc.py",
    "tests/pdf_processing/q04/worker_bc.py",
    "tests/pdf_processing/q04/pod-topology-v54/RUNTIME-INTEGRATION-MANIFEST.json",
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
IMAGE = base.IMAGE
source_manifest = base.source_manifest
kubernetes_list = base.kubernetes_list
validate = base.validate
render = base.render
