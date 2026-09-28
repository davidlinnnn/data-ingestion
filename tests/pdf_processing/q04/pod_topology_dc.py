"""Fresh DC identity; unchanged DB production source, bundle and reviewed oracle."""
import pod_topology_db as previous

base = previous.base
base.PHASE = 't09a-bounds-dc'
base.DEPLOYMENT = base.PHASE + '-activities'
base.RUN_LABEL = base.PHASE
base.WORKFLOW_QUEUE = base.PHASE + '-workflows'
base.ACTIVITY_QUEUE = base.PHASE + '-08'
base.OBJECT_PREFIX = 't09a/bounds-20260928-dc/'
base.EVIDENCE_PVC = 't09a-bounds-dc-evidence-20260928'
base.EVIDENCE_DIRECTORY_NAME = 't09a-bounds-20260928-dc'
base.POD_ONLY_FILES += (
    'tests/pdf_processing/q04/pod_topology_dc.py',
    'tests/pdf_processing/q04/pod_preflight_dc.py',
    'tests/pdf_processing/q04/pod_workload_dc.py',
    'tests/pdf_processing/q04/pod_remote_evidence_dc.py',
    'tests/pdf_processing/t09a_bounds/normal-topology-dc/RUNTIME-INTEGRATION-MANIFEST.json',
)
base.HARNESS_FILES = {name: base.ROOT / name
                      for name in sorted(set(base.FROZEN_TEST_FILES + base.POD_ONLY_FILES))}

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
