"""Inactive topology for the distinct #44 mixed-warm object-bound trial."""

import json
from pathlib import Path

import pod_topology_ah as previous


base = previous.base
base.PHASE = "t09a-bounds-bi"
base.DEPLOYMENT = base.PHASE + "-activities"
base.RUN_LABEL = base.PHASE
base.WORKFLOW_QUEUE = base.PHASE + "-workflows"
base.ACTIVITY_QUEUE = base.PHASE + "-08"
base.OBJECT_PREFIX = "t09a/bounds-20260926-bi/"
base.EVIDENCE_PVC = "t09a-bounds-bi-evidence-20260926"
base.EVIDENCE_DIRECTORY_NAME = "t09a-bounds-20260926-bi"
base.PRODUCER_MANIFEST = base.ROOT / "tests/pdf_processing/t09a_bounds/BI-MANIFEST.json"
base.FROZEN_TEST_FILES = tuple(json.loads(base.PRODUCER_MANIFEST.read_text())["test_files"])
base.POD_ONLY_FILES = tuple(dict.fromkeys(base.POD_ONLY_FILES + (
    "tests/pdf_processing/q04/pod_topology_bi.py",
    "tests/pdf_processing/q04/pod_preflight_bi.py",
    "tests/pdf_processing/q04/pod_workload_bi.py",
    "tests/pdf_processing/q04/candidate/warm_v3_reference_bi.py",
    "tests/pdf_processing/q04/candidate/warm_pod_window_bi.py",
    "tests/pdf_processing/t09a_bounds/BI-MANIFEST.json",
    "tests/pdf_processing/t09a_bounds/RUNTIME-INTEGRATION-MANIFEST.json",
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
