"""Render inactive, run-owned coordinator and replaceable Activity Deployments."""

import copy
import importlib.util
import json
from pathlib import Path
import sys

import pod_topology_be as be


_spec = importlib.util.spec_from_file_location(
    'q04_pod_topology_bh_engine', Path(__file__).with_name('pod_topology_p.py'))
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base
_spec.loader.exec_module(base)

base.PHASE = 'q04-pod-cgroup-bh'
base.DEPLOYMENT = base.PHASE + '-activities'
base.RUN_LABEL = base.PHASE
base.WORKFLOW_QUEUE = base.PHASE + '-workflows'
base.ACTIVITY_QUEUE = base.PHASE + '-native'
base.OBJECT_PREFIX = 'q04/pod-loss-pod-cgroup-20260926-bh/'
base.EVIDENCE_PVC = 'q04-pod-cgroup-bh-evidence-20260926-bh'
base.EVIDENCE_DIRECTORY_NAME = 'q04-pod-loss-pod-cgroup-20260926-bh'
base.PRODUCER_MANIFEST = base.Q04 / 'candidate/warm-continuation-v3-ah/MANIFEST.json'
base.FROZEN_TEST_FILES = tuple(json.loads(base.PRODUCER_MANIFEST.read_text())['test_files'])
base.POD_ONLY_FILES = tuple(dict.fromkeys(be.base.POD_ONLY_FILES + (
    'tests/pdf_processing/q04/candidate/pod_loss_window_bh.py',
    'tests/pdf_processing/q04/pod_loss_bridge_bh.py',
    'tests/pdf_processing/q04/pod_workload_bh.py',
    'tests/pdf_processing/q04/pod_activity_supervisor_bh.py',
    'tests/pdf_processing/q04/pod_preflight_bh.py',
    'tests/pdf_processing/q04/pod_topology_bh.py',
    'tests/pdf_processing/q04/pod-topology-v59/RUNTIME-INTEGRATION-MANIFEST.json',
)))
base.HARNESS_FILES = {name: base.ROOT / name
                      for name in sorted(set(base.FROZEN_TEST_FILES + base.POD_ONLY_FILES))}

PHASE = base.PHASE
DEPLOYMENT = base.DEPLOYMENT
COORDINATOR_DEPLOYMENT = base.PHASE + '-coordinator'
RUN_LABEL = base.RUN_LABEL
WORKFLOW_QUEUE = base.WORKFLOW_QUEUE
ACTIVITY_QUEUE = base.ACTIVITY_QUEUE
EVIDENCE_PVC = base.EVIDENCE_PVC
EVIDENCE_DIRECTORY_NAME = base.EVIDENCE_DIRECTORY_NAME
NAMESPACE = base.NAMESPACE
NODE = base.NODE
IMAGE = base.IMAGE
source_manifest = base.source_manifest


def kubernetes_list():
    value = base.kubernetes_list()
    coordinator = copy.deepcopy(value['items'][3])
    coordinator['metadata']['name'] = COORDINATOR_DEPLOYMENT
    selector = RUN_LABEL + '-coordinator'
    coordinator['spec']['selector']['matchLabels']['q04-run'] = selector
    coordinator['spec']['template']['metadata']['labels']['q04-run'] = selector
    container = coordinator['spec']['template']['spec']['containers'][0]
    container['name'] = 'coordinator'
    container['resources'] = {
        'requests': {'cpu': '100m', 'memory': '1Gi', 'ephemeral-storage': '1Gi'},
        'limits': {'cpu': '2', 'memory': '2Gi', 'ephemeral-storage': '2Gi'},
    }
    value['items'].append(coordinator)
    return value


def validate(value):
    if value != kubernetes_list():
        raise ValueError('split-Pod topology differs from frozen builder')
    base.validate({**value, 'items': value['items'][:4]})
    coordinator = value['items'][4]
    if (coordinator['spec']['replicas'] != 0
            or coordinator['spec']['template']['spec']['nodeSelector']
            != value['items'][3]['spec']['template']['spec']['nodeSelector']
            or coordinator['spec']['template']['spec']['volumes']
            != value['items'][3]['spec']['template']['spec']['volumes']):
        raise ValueError('coordinator must be inactive on worker node with same PVC')
    return {'status': 'PASS_OFFLINE_ONLY', 'runtime_authorized': False,
            'activity_deployment': DEPLOYMENT,
            'coordinator_deployment': COORDINATOR_DEPLOYMENT,
            'evidence_pvc': EVIDENCE_PVC}


def render(output: Path, sources: Path) -> None:
    topology = kubernetes_list()
    validate(topology)
    output.write_text(json.dumps(topology, indent=2) + '\n')
    sources.write_text(json.dumps(source_manifest(), indent=2, sort_keys=True) + '\n')
