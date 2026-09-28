"""25-minute YOLO fixture 07 matrix runner with isolated live init."""

import argparse
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import signal
import shlex
import subprocess
import sys
import time
import uuid

Q04_DIR = Path(__file__).resolve().parent.parent
if str(Q04_DIR) not in sys.path:
    sys.path.insert(0, str(Q04_DIR))

from sentinel.acl_admission import (
    CLEANUP_SECONDS,
    CONTINUOUS_SECONDS,
    EXPECTED_CGROUP_OOM_KILL,
    OBSERVATION_SECONDS,
    PER_CASE_AVAILABLE_BYTES,
    TARGET_AVAILABLE_BYTES,
    WINDOW_SECONDS,
    WORKLOAD_SECONDS,
)


REPO = Path(__file__).resolve().parents[4]
REMOTE = "/tmp/q04-yolo-matrix-20260918-a"
PREFIX = "q04/yolo-matrix-20260918-a/"
SOURCE_REMOTE = "/tmp/q04-option-a-20260918-c"
SOURCE_PREFIX = "q04/option-a-20260918-c/"
LOCAL_BUNDLE = Path("/private/tmp/q04-inputs-option-a-v7")
MODEL_CACHE = "/experiment/PROTOTYPE-wipe-me/hf"
PHASE = "yolo-matrix-a"
OUT = Path("/private/tmp/q04-yolo-matrix-20260918-a")
CAPACITY = REMOTE + "/capacity-yolo-matrix-a.json"
RESERVATION = REMOTE + "/reservation-yolo-matrix-a.json"
RELEASE = REMOTE + "/release-reservation-yolo-matrix-a"
ADMISSION_EVIDENCE = REMOTE + "/pre-admission-yolo-matrix-a.jsonl"
ADMISSION_RESULT = REMOTE + "/admission-yolo-matrix-a.json"
RUNNER_DIR = REMOTE + "/runner-yolo-matrix-a"
DRIVER_LOCK = REMOTE + f"/{PHASE}.driver.lock"
PYTHON = "/experiment/.venv/bin/python"
NS = "pdf-t09a-validation"
CONTEXT = "kind-internal-a2a-vs6-local"
COORDINATOR_UID = "39c4bf45-45ae-4646-8d7b-ec47b2c61785"
COORDINATOR_CONTAINER_ID = (
    "containerd://75d02af07009f1d7152d6a68958cee5f43508ec1dd0ae327142a42db5e429ca5"
)
COORDINATOR_RESTART_COUNT = 1
COORDINATOR_STARTED_AT = "2026-09-17T13:46:12Z"
EXPECTED_BOOT_ID = "c01b81ac-b0fd-4ce6-8cda-f0da74b9bbd3"
EXPECTED_PID1_START_TICKS = 733
EXPECTED_VM_OOM_KILL = 0
EXPECTED_BUNDLE_SHA256 = (
    "9e46ad75379dffed05c5e25ec36b22fdf0d680e30e7d2b298d5ac355d0e039f2"
)
EXPECTED_RUNTIME_SHA256 = (
    "5fc631f0076001b75815901d610b974b99db52a50d2eb9b8a3b735ab3d109471"
)
EXPECTED_REFERENCE_07_SHA256 = (
    "a3ac9eb345949cdc83423ba1ae38c794400e8f4f89061056c1102517b6a1e6a1"
)
EXPECTED_QUALITY_ORACLE_SHA256 = (
    "781191056965a38c332697b3cbeb1b58b3488647263b4afd8fa8323a7fc13c92"
)
EXPECTED_TABLE_ORACLE_SHA256 = (
    "310f8693ce20c484422a6080cbcbd2bd6431d0209e558376d61d76b0d44b003d"
)
SOURCE_STATE_SHA256 = "2a3264316e0a859b2a490b3724af09c2df16959b35d9c8116b02e078f50f0636"
SOURCE_RUN_ID = "q04-41aad36cffde419b95f92ba48b8abf26"
MAX_CGROUP_BYTES = 4_294_967_296
BASE = ["kubectl", "--context", CONTEXT, "--request-timeout=15s"]
TARGET = TARGET_AVAILABLE_BYTES
CANDIDATES = json.loads(
    (REPO / "tests/pdf_processing/q04/diagnosis/evidence/capacity-candidates.json").read_text()
)["deployments"]
assert len(CANDIDATES) == 32
STATE = {
    "phase": "preparing",
    "errors": [],
    "services_expected_closed": 32,
    "services_restored": False,
    "retry_count": 0,
    "fixture": "07",
    "modes": ["fresh", "restored", "replay"],
}


def build_probe_expectation(bundle):
    """Bind the read-only probe to the preserved original Q04 state."""
    return {
        "profile": bundle["base_profile"],
        "producer": bundle["producer"],
        "run_root": SOURCE_REMOTE,
        "prefix": SOURCE_PREFIX,
        "producer_roots": [
            "/app/pdf_processing",
            SOURCE_REMOTE + "/code/src/pdf_processing",
        ],
        "profile_path": SOURCE_REMOTE + "/inputs/inputs.json",
    }


def validate_old_request_binding(
    accepted, final, registration_key, operation, artifact_sha256, prefix
):
    """Validate the retained result using its actual v2 provenance schema."""
    request = accepted["request"]
    accepted_profile = accepted["profile"]
    source = final["source"]
    result_profile = final["provenance"]["profile"]
    if source["request_id"] != request["request_id"]:
        raise ValueError("retained result request changed")
    if request["profile"] != accepted_profile["id"]:
        raise ValueError("accepted request profile does not match accepted provenance")
    if source["profile"] != request["profile"]:
        raise ValueError("retained result source profile changed")
    if result_profile["id"] != accepted_profile["id"]:
        raise ValueError("retained result provenance profile changed")
    if result_profile["release"] != accepted_profile["release"]:
        raise ValueError("retained result provenance release changed")
    source_key = source["artifact"]["key"]
    if not source_key.startswith(prefix + "sources/"):
        raise ValueError("retained result source escaped original prefix")
    if final["status"] != "complete":
        raise ValueError("retained result is not complete")
    return {
        "registration_key": registration_key,
        "operation": operation,
        "request_id": source["request_id"],
        "source_key": source_key,
        "profile_id": result_profile["id"],
        "profile_release": result_profile["release"],
        "artifact_sha256": artifact_sha256,
        "status": final["status"],
    }


def build_old_request_binding_program(*, root=SOURCE_REMOTE, prefix=SOURCE_PREFIX):
    """Build the read-only retained-store probe sent to the coordinator."""
    return """import boto3,hashlib,json
from pathlib import Path
VALIDATOR
root=Path(ROOT)
accepted=json.loads((root/'state/acl-option-a-window-c/fresh-09/accepted.json').read_text())
s3=boto3.client('s3',endpoint_url='http://objects:9000')
prefix=PREFIX
found=[]
for item in s3.list_objects_v2(Bucket='t09a',Prefix=prefix+'registered/').get('Contents',[]):
 manifest=json.loads(s3.get_object(Bucket='t09a',Key=item['Key'])['Body'].read())
 for file in manifest['files']:
  if file['name']!='processing-result.json':continue
  raw=s3.get_object(Bucket='t09a',Key=file['key'])['Body'].read()
  assert hashlib.sha256(raw).hexdigest()==file['sha256'] and len(raw)==file['bytes']
  final=json.loads(raw)
  if final['source']['request_id']==accepted['request']['request_id']:
   found.append(validate_old_request_binding(
    accepted,final,item['Key'],manifest['operation'],file['sha256'],prefix))
assert len(found)==1
print(json.dumps(found[0]))
""".replace("VALIDATOR", inspect.getsource(validate_old_request_binding)).replace(
        "ROOT", repr(root)
    ).replace("PREFIX", repr(prefix))


def build_staging_probe_program(*, root=REMOTE):
    """Build the exact post-copy staging probe."""
    return """import hashlib,json,sys
from pathlib import Path
root=Path(ROOT)
sys.path[:0]=[str(root/'code/src'),str(root/'code/tests/pdf_processing/q04'),str(root/'code/tests/pdf_processing/q02'),str(root/'code/tests/pdf_processing/q03')]
from prepare import verify_bundle
bundle=verify_bundle(root/'inputs')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps({'bundle_sha256':sha(root/'inputs/inputs.json'),
 'runtime_sha256':sha(root/'code/tests/pdf_processing/q04/q04_runtime.py'),
 'reference_07_sha256':sha(root/'inputs/references/07.json'),
 'quality_oracle_sha256':sha(root/'inputs/oracles/quality-oracle.json'),
 'table_oracle_sha256':sha(root/'inputs/oracles/07-table-full-audit.json'),
 'method':bundle['base_profile']['method'],'producer':bundle['producer']}))
""".replace("ROOT", repr(root))


def validate_staged_runtime(staged, bundle):
    """Fail closed on every staged YOLO artifact and interface field."""
    expected_keys = {
        "bundle_sha256",
        "runtime_sha256",
        "reference_07_sha256",
        "quality_oracle_sha256",
        "table_oracle_sha256",
        "method",
        "producer",
    }
    if set(staged) != expected_keys:
        raise ValueError("staging probe schema changed")
    expected_hashes = {
        "bundle_sha256": EXPECTED_BUNDLE_SHA256,
        "runtime_sha256": EXPECTED_RUNTIME_SHA256,
        "reference_07_sha256": EXPECTED_REFERENCE_07_SHA256,
        "quality_oracle_sha256": EXPECTED_QUALITY_ORACLE_SHA256,
        "table_oracle_sha256": EXPECTED_TABLE_ORACLE_SHA256,
    }
    for field, expected in expected_hashes.items():
        if staged[field] != expected:
            raise ValueError(field + " changed")
    if staged["method"] != bundle["base_profile"]["method"]:
        raise ValueError("staged method changed")
    if staged["producer"] != bundle["producer"]:
        raise ValueError("staged producer changed")


def build_initialized_state_probe_program(*, root=REMOTE):
    """Build the exact post-init state schema probe."""
    return """import hashlib,json
from pathlib import Path
root=Path(ROOT)
config=json.loads((root/'state/config.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps({'run_id':config['run_id'],'prefix':config['prefix'],
 'bundle':config['bundle'],'bundle_sha256':config['bundle_sha256'],
 'state_sha256':sha(root/'state/config.json'),'producer':config['producer'],
 'profile_method':config['profiles']['07']['method'],
 'profile_id':config['profiles']['07']['id'],
 'profile_release':config['profiles']['07']['release'],
 'config_keys':sorted(config),'profile_keys':sorted(config['profiles']),
 'queue_keys':sorted(config['queues']),'window_keys':sorted(config['window'])}))
""".replace("ROOT", repr(root))


def validate_initialized_state(
    initialized,
    bundle,
    *,
    remote_root=REMOTE,
    prefix=PREFIX,
    source_run_id=SOURCE_RUN_ID,
    bundle_sha256=EXPECTED_BUNDLE_SHA256,
):
    """Validate the actual q04_runtime init config interface."""
    expected_keys = {
        "run_id",
        "prefix",
        "bundle",
        "bundle_sha256",
        "state_sha256",
        "producer",
        "profile_method",
        "profile_id",
        "profile_release",
        "config_keys",
        "profile_keys",
        "queue_keys",
        "window_keys",
    }
    if set(initialized) != expected_keys:
        raise ValueError("initialized state probe schema changed")
    expected_config_keys = {
        "run_id", "profiles", "producer", "bundle", "state", "temporal",
        "endpoint", "bucket", "prefix", "window", "model_cache", "python",
        "pod_namespace", "trial_seconds", "workflow_queue", "queues", "limits",
        "parser_budgets", "drain_seconds", "bundle_sha256",
    }
    if set(initialized["config_keys"]) != expected_config_keys:
        raise ValueError("q04 init config fields changed")
    expected_profiles = {row["id"] for row in bundle["fixtures"]} | {
        "native-evidence", "native-method"
    }
    if set(initialized["profile_keys"]) != expected_profiles:
        raise ValueError("q04 init profile keys changed")
    if initialized["queue_keys"] != initialized["profile_keys"]:
        raise ValueError("q04 init queue/profile keys differ")
    required_window = {
        "status", "owner", "approval_reference", "starts_at", "ends_at",
        "proposed_window_seconds", "admission_seconds",
        "admission_available_bytes", "cleanup_seconds", "max_cgroup_bytes",
    }
    if not required_window.issubset(initialized["window_keys"]):
        raise ValueError("q04 init window fields missing")
    if not initialized["run_id"].startswith("q04-"):
        raise ValueError("new run id format changed")
    if initialized["run_id"] == source_run_id:
        raise ValueError("source run id reused")
    if initialized["prefix"] != prefix:
        raise ValueError("initialized prefix changed")
    if initialized["bundle"] != remote_root + "/inputs":
        raise ValueError("initialized bundle path changed")
    if initialized["bundle_sha256"] != bundle_sha256:
        raise ValueError("initialized bundle hash changed")
    if initialized["producer"] != bundle["producer"]:
        raise ValueError("initialized producer changed")
    if initialized["profile_method"] != bundle["base_profile"]["method"]:
        raise ValueError("initialized profile method changed")
    if initialized["profile_id"] != bundle["base_profile"]["id"]:
        raise ValueError("initialized profile id changed")
    if not initialized["profile_release"].startswith("q04-"):
        raise ValueError("initialized profile release format changed")


def remote_absence_paths():
    """Return every new identity that must not predate staging."""
    return {
        "root_absent": REMOTE,
        "phase_absent": REMOTE + "/state/" + PHASE,
        "capacity_absent": CAPACITY,
        "log_absent": REMOTE + "/logs/" + PHASE + ".log",
        "reservation_absent": RESERVATION,
        "release_absent": RELEASE,
        "admission_absent": ADMISSION_EVIDENCE,
        "admission_result_absent": ADMISSION_RESULT,
        "runner_absent": RUNNER_DIR,
        "driver_lock_absent": DRIVER_LOCK,
    }


def validate_coordinator_identity(pod):
    """Fence the exact post-restart container before reading frozen state."""
    if pod["metadata"]["uid"] != COORDINATOR_UID:
        raise ValueError("coordinator UID changed")
    statuses = [
        row
        for row in pod["status"].get("containerStatuses", [])
        if row.get("name") == "coordinator"
    ]
    if len(statuses) != 1:
        raise ValueError("coordinator container status unavailable")
    status = statuses[0]
    if status.get("containerID") != COORDINATOR_CONTAINER_ID:
        raise ValueError("coordinator container ID changed")
    if status.get("restartCount") != COORDINATOR_RESTART_COUNT:
        raise ValueError("coordinator restart count changed")
    if not status.get("ready"):
        raise ValueError("coordinator container is not ready")
    started_at = status.get("state", {}).get("running", {}).get("startedAt")
    if started_at != COORDINATOR_STARTED_AT:
        raise ValueError("coordinator container start time changed")
    return {
        "pod_uid": pod["metadata"]["uid"],
        "container_id": status["containerID"],
        "restart_count": status["restartCount"],
        "started_at": started_at,
    }


def validate_remote_baseline(baseline):
    """Reject reuse after another VM/container lifetime or OOM event."""
    if baseline.get("boot_id") != EXPECTED_BOOT_ID:
        raise ValueError("boot id changed")
    if baseline.get("pid1_start_ticks") != EXPECTED_PID1_START_TICKS:
        raise ValueError("PID 1 start ticks changed")
    if baseline.get("vm_oom_kill") != EXPECTED_VM_OOM_KILL:
        raise ValueError("vm oom kill baseline changed")
    if baseline.get("cgroup_oom_kill") != EXPECTED_CGROUP_OOM_KILL:
        raise ValueError("cgroup oom kill baseline changed")
    if baseline.get("qualification_lock_held") is not False:
        raise ValueError("qualification lock is held")


def validate_frozen_artifacts(frozen):
    """Pin the accepted Option A bundle/state without adopting it in place."""
    if (
        frozen.get("bundle_sha256_config")
        != EXPECTED_BUNDLE_SHA256
        or frozen.get("bundle_sha256_actual")
        != EXPECTED_BUNDLE_SHA256
    ):
        raise ValueError("source frozen bundle hash changed")
    if frozen.get("state_sha256") != SOURCE_STATE_SHA256:
        raise ValueError("source frozen state hash changed")
    if not frozen.get("producer_matches") or not frozen.get("profile_matches"):
        raise ValueError("frozen producer or profile changed")
    if not frozen.get("accepted_phase_complete"):
        raise ValueError("frozen ACL Option A evidence is incomplete")


def build_capacity(*, started_at, owner, approval_reference):
    """Create the immutable lease consumed by outer and per-case admission."""
    if not owner or not approval_reference:
        raise ValueError("capacity owner and approval reference are required")
    capacity = json.loads(
        (REPO / "tests/pdf_processing/q04/preflight/capacity.draft.json").read_text()
    )
    capacity.update(
        status="AUTHORIZED",
        owner=owner,
        approval_reference=approval_reference,
        starts_at=started_at,
        ends_at=started_at + WINDOW_SECONDS,
        proposed_window_seconds=WINDOW_SECONDS,
        admission_seconds=CONTINUOUS_SECONDS,
        admission_available_bytes=PER_CASE_AVAILABLE_BYTES,
        outer_observation_seconds=OBSERVATION_SECONDS,
        outer_continuous_seconds=CONTINUOUS_SECONDS,
        outer_admission_available_bytes=TARGET_AVAILABLE_BYTES,
        minimum_work_seconds=WORKLOAD_SECONDS,
        cleanup_seconds=CLEANUP_SECONDS,
        expected_vm_oom_kill=EXPECTED_VM_OOM_KILL,
        expected_cgroup_oom_kill=EXPECTED_CGROUP_OOM_KILL,
        max_cgroup_bytes=MAX_CGROUP_BYTES,
    )
    return capacity


def build_admission_argv(reservation_token):
    return [
        RUNNER_DIR + "/acl_admission.py",
        "--capacity",
        CAPACITY,
        "--reservation",
        RESERVATION,
        "--release",
        RELEASE,
        "--evidence",
        ADMISSION_EVIDENCE,
        "--result",
        ADMISSION_RESULT,
        "--coordinator-uid",
        COORDINATOR_UID,
        "--phase",
        PHASE,
        "--reservation-token",
        reservation_token,
        "--expected-vm-oom-kill",
        str(EXPECTED_VM_OOM_KILL),
        "--expected-max-cgroup-bytes",
        str(MAX_CGROUP_BYTES),
    ]


def build_runtime_command(
    *,
    remote=REMOTE,
    capacity=CAPACITY,
    python=PYTHON,
    timeout_program="timeout",
    driver_lock=DRIVER_LOCK,
):
    """Render the two-shell runtime command without interpolated source quoting."""
    verify = (
        "import os;from pathlib import Path;from prepare import verify_bundle;"
        "verify_bundle(Path(os.environ['R'])/'inputs')"
    )
    inner = "\n".join(
        (
            f"{shlex.quote(python)} -c {shlex.quote(verify)}",
            "exec "
            + shlex.quote(python)
            + " tests/pdf_processing/q04/q04_runtime.py"
            + " --phase matrix --fixture 07"
            + ' --bundle "$R/inputs" --state "$R/state"'
            + " --capacity "
            + shlex.quote(capacity)
            + " --name yolo-matrix-a --trial-seconds 180 --capacity-approved",
        )
    )
    return "\n".join(
        (
            "set -euC",
            "export R=" + shlex.quote(remote),
            "export PYTHONDONTWRITEBYTECODE=1 PYTHONSAFEPATH=1 "
            "HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4",
            'export PYTHONPATH="$R/runner-yolo-matrix-a:$R/code/src:'
            '$R/code/tests/pdf_processing/q04:$R/code/tests/pdf_processing/q02:'
            '$R/code/tests/pdf_processing/q03"',
            "export PDF_QUALIFICATION_LOCK=" + shlex.quote(driver_lock),
            'cd "$R/code"',
            'test ! -e "$R/state/yolo-matrix-a"',
            'test ! -e "$PDF_QUALIFICATION_LOCK"',
            shlex.quote(timeout_program)
            + " --signal=INT --kill-after=180s 825s sh -eu -c "
            + shlex.quote(inner)
            + ' > "$R/logs/yolo-matrix-a.log" 2>&1',
            "",
        )
    )


def require_launch_budget(lease_ends_monotonic, monotonic=time.monotonic):
    if lease_ends_monotonic - monotonic() < WORKLOAD_SECONDS + CLEANUP_SECONDS:
        raise RuntimeError("insufficient workload and cleanup reserve at runtime launch")


def launch_after_admission(
    admit,
    launch,
    *,
    lease_ends_monotonic,
    monotonic=time.monotonic,
):
    """Keep runtime construction unreachable until outer admission returns PASS."""
    summary = admit()
    if not isinstance(summary, dict) or summary.get("passed") is not True:
        raise RuntimeError("outer admission did not return PASS")
    require_launch_budget(lease_ends_monotonic, monotonic)
    return summary, launch()


def save():
    (OUT / "lease-state.json").write_text(json.dumps(STATE, indent=2) + "\n")
    print(
        json.dumps(
            {"time": time.time(), "phase": STATE["phase"], "errors": STATE["errors"]}
        ),
        flush=True,
    )


def k(namespace, *args, timeout=30, **kwargs):
    return subprocess.check_output(
        BASE + ["-n", namespace, *args], timeout=timeout, **kwargs
    )


def remote(script, timeout=60):
    return k(
        NS,
        "exec",
        "-i",
        "coordinator",
        "--",
        "env",
        "PYTHONDONTWRITEBYTECODE=1",
        PYTHON,
        "-",
        input=script.encode(),
        timeout=timeout,
    )


def write_remote(path, data):
    remote(
        "from pathlib import Path\n"
        + "Path(" + repr(path) + ").open('xb').write(" + repr(data) + ")\n"
    )


def staged_sources():
    return {
        "outer_admission.py": REPO / "tests/pdf_processing/q04/outer_admission.py",
        "acl_admission.py": REPO
        / "tests/pdf_processing/q04/sentinel/acl_admission.py",
        "telemetry.py": REPO / "tests/pdf_processing/q04/telemetry.py",
        "cleanup.py": REPO / "tests/pdf_processing/q04/sentinel/cleanup.py",
        "run_yolo_matrix_a.py": Path(__file__),
    }


def stage_admission_runner():
    sources = staged_sources()
    remote("from pathlib import Path\nPath(" + repr(RUNNER_DIR) + ").mkdir()\n")
    manifest = {}
    for name, source in sources.items():
        payload = source.read_bytes()
        write_remote(RUNNER_DIR + "/" + name, payload)
        manifest[name] = hashlib.sha256(payload).hexdigest()
    remote_manifest = json.loads(
        remote(
            "import hashlib,json\n"
            + "from pathlib import Path\n"
            + "root=Path("
            + repr(RUNNER_DIR)
            + ")\n"
            + "print(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() "
            + "for p in root.iterdir() if p.is_file()},sort_keys=True))\n"
        )
    )
    if remote_manifest != manifest:
        raise ValueError("staged admission runner digest mismatch")
    return manifest


def deployment_snapshot():
    result = []
    for expected in CANDIDATES:
        obj = json.loads(
            k(expected["namespace"], "get", "deployment", expected["name"], "-o", "json")
        )
        row = {
            "namespace": expected["namespace"],
            "name": expected["name"],
            "expected_uid": expected["uid"],
            "uid": obj["metadata"]["uid"],
            "resource_version": obj["metadata"]["resourceVersion"],
            "replicas": obj["spec"].get("replicas", 1),
            "ready": obj["status"].get("readyReplicas", 0),
        }
        assert row["uid"] == row["expected_uid"], "Deployment UID changed"
        assert row["replicas"] == 0 and row["ready"] == 0, "paused service resumed"
        result.append(row)
    return result


def assert_candidate_pods_absent():
    pods = json.loads(k(NS, "get", "pods", "-A", "-o", "json"))["items"]
    live = []
    for pod in pods:
        namespace = pod["metadata"]["namespace"]
        name = pod["metadata"]["name"]
        if any(
            namespace == row["namespace"] and name.startswith(row["name"] + "-")
            for row in CANDIDATES
        ):
            live.append({"namespace": namespace, "pod": name})
    assert not live, ("paused service Pods remain", live)


def t09a_health(label):
    script = """import asyncio,json,urllib.request
from temporalio.client import Client
async def main():
 c=await Client.connect('temporal:7233')
 value={'time':__import__('time').time(),'healthy':await c.service_client.check_health(),
  'running':[w.id async for w in c.list_workflows(query='ExecutionStatus="Running"')],
  'objects':urllib.request.urlopen('http://objects:9000/minio/health/ready',timeout=5).status}
 print(json.dumps(value))
asyncio.run(main())
"""
    value = json.loads(remote(script, timeout=30))
    assert value["healthy"] and not value["running"] and value["objects"] == 200
    (OUT / label).write_text(json.dumps(value, indent=2) + "\n")
    return value


def frozen_precheck():
    pod = json.loads(k(NS, "get", "pod", "coordinator", "-o", "json"))
    coordinator = validate_coordinator_identity(pod)
    (OUT / "coordinator-identity.json").write_text(
        json.dumps(coordinator, indent=2, sort_keys=True) + "\n"
    )
    runtime_probe = (REPO / "tests/pdf_processing/q04/preflight/remote_probe.py").read_text()
    bundle = json.loads((LOCAL_BUNDLE / "inputs.json").read_text())
    expected = build_probe_expectation(bundle)
    inventory = json.loads(
        remote(
            runtime_probe
            + "\nprint(json.dumps(inventory(json.loads("
            + repr(json.dumps(expected))
            + "))))\n",
            timeout=120,
        )
    )
    (OUT / "runtime-precheck.json").write_text(json.dumps(inventory, indent=2) + "\n")
    assert inventory["python_matches"] and inventory["platform_matches"]
    assert not inventory["package_differences"] and not inventory["model_differences"]
    assert not inventory["processes"] and inventory["proposed_path_exists"]
    frozen_producer = SOURCE_REMOTE + "/code/src/pdf_processing"
    assert not inventory["producer_differences"][frozen_producer]
    assert inventory["retained_profile"]["method_matches"]
    assert inventory["retained_profile"]["path"] == SOURCE_REMOTE + "/inputs/inputs.json"
    script = """import hashlib,json,os,sys
from pathlib import Path
root=Path(ROOT)
sys.path[:0]=[str(root/'code/src'),str(root/'code/tests/pdf_processing/q04'),str(root/'code/tests/pdf_processing/q02'),str(root/'code/tests/pdf_processing/q03')]
from prepare import verify_bundle
bundle=verify_bundle(root/'inputs')
config=json.loads((root/'state/config.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def fields(path):return {s.split()[0].rstrip(':'):int(s.split()[1]) for s in Path(path).read_text().splitlines()}
def start_ticks(pid):
 text=(Path('/proc')/str(pid)/'stat').read_text();return int(text[text.rfind(')')+1:].split()[19])
lock=Path('/tmp/data-ingestion-pdf-qualification.lock')
lock_held=False
if lock.exists():
 identity=lock.stat();needle=f'{os.major(identity.st_dev):02x}:{os.minor(identity.st_dev):02x}:{identity.st_ino}'
 lock_held=any(needle in line for line in Path('/proc/locks').read_text().splitlines())
events=fields('/sys/fs/cgroup/memory.events')
value={'run_id':config['run_id'],'prefix':config['prefix'],'bundle':config['bundle'],
 'bundle_sha256_config':config['bundle_sha256'],'bundle_sha256_actual':sha(root/'inputs/inputs.json'),
 'producer_matches':config['producer']==bundle['producer'],'profile_matches':config['profiles']['07']['method']==bundle['base_profile']['method'],
 'state_sha256':sha(root/'state/config.json'),'accepted_phase_complete':(root/'state/acl-option-a-window-c/phase-complete.json').exists(),
 'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'pid1_start_ticks':start_ticks(1),
 'vm_oom_kill':fields('/proc/vmstat')['oom_kill'],'cgroup_oom_kill':events['oom_kill'],
 'qualification_lock_held':lock_held}
value.update({name:not Path(path).exists() for name,path in ABSENCE_PATHS.items()})
print(json.dumps(value))
""".replace("ROOT", repr(SOURCE_REMOTE)).replace(
        "ABSENCE_PATHS", repr(remote_absence_paths())
    )
    frozen = json.loads(remote(script, timeout=120))
    (OUT / "frozen-precheck.json").write_text(json.dumps(frozen, indent=2) + "\n")
    assert frozen["run_id"] == SOURCE_RUN_ID and frozen["prefix"] == SOURCE_PREFIX
    assert frozen["bundle"] == SOURCE_REMOTE + "/inputs"
    validate_frozen_artifacts(frozen)
    validate_remote_baseline(frozen)
    for field in remote_absence_paths():
        assert frozen[field], field
    old_binding_program = build_old_request_binding_program()
    old_binding = json.loads(remote(old_binding_program, timeout=60))
    (OUT / "old-request-binding.json").write_text(
        json.dumps(old_binding, indent=2, sort_keys=True) + "\n"
    )
    frozen["old_request_binding"] = old_binding
    return frozen


def copy_to_remote(source, destination):
    """Copy one local path into a new remote identity."""
    subprocess.run(
        BASE + ["-n", NS, "cp", str(source), "coordinator:" + destination],
        check=True,
        timeout=120,
        stdout=(OUT / (Path(destination).name + "-copy.log")).open("x"),
        stderr=subprocess.STDOUT,
    )


def claim_remote_root(token):
    """Atomically claim the new identity before the coordinator lock handoff."""
    payload = json.dumps({"phase": PHASE, "token": token}, sort_keys=True).encode()
    remote(
        "from pathlib import Path\n"
        + "root=Path(" + repr(REMOTE) + ")\n"
        + "root.mkdir()\n"
        + "(root/'setup-claim.json').open('xb').write(" + repr(payload) + ")\n"
    )


def stage_runtime_tree():
    """Clone the preserved harness, then bind the current ownership fix/bundle."""
    remote(
        "import shutil\nfrom pathlib import Path\n"
        + "source=Path(" + repr(SOURCE_REMOTE) + ")\n"
        + "target=Path(" + repr(REMOTE) + ")\n"
        + "assert source.is_dir() and target.is_dir()\n"
        + "assert not (target/'code').exists() and not (target/'inputs').exists()\n"
        + "shutil.copytree(source/'code',target/'code')\n"
        + "(target/'state').mkdir()\n(target/'logs').mkdir()\n",
        timeout=120,
    )
    copy_to_remote(LOCAL_BUNDLE, REMOTE + "/inputs")
    copy_to_remote(
        REPO / "tests/pdf_processing/q04/q04_runtime.py",
        REMOTE + "/code/tests/pdf_processing/q04/q04_runtime.py",
    )
    verify_program = build_staging_probe_program()
    staged = json.loads(remote(verify_program, timeout=120))
    local_bundle = json.loads((LOCAL_BUNDLE / "inputs.json").read_text())
    validate_staged_runtime(staged, local_bundle)
    (OUT / "runtime-staging.json").write_text(
        json.dumps(staged, indent=2, sort_keys=True) + "\n"
    )
    return staged


def run_live_init():
    """Create the new run ID/state and upload only new-prefix source objects."""
    command = " ".join(
        (
            "set -eu",
            "&& export PYTHONDONTWRITEBYTECODE=1 PYTHONSAFEPATH=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1",
            "&& export PDF_QUALIFICATION_LOCK=" + shlex.quote(REMOTE + "/init.driver.lock"),
            "&& export PYTHONPATH=" + shlex.quote(
                REMOTE + "/code/src:"
                + REMOTE + "/code/tests/pdf_processing/q04:"
                + REMOTE + "/code/tests/pdf_processing/q02:"
                + REMOTE + "/code/tests/pdf_processing/q03"
            ),
            "&& cd " + shlex.quote(REMOTE + "/code"),
            "&& timeout --signal=INT --kill-after=30s 180s " + shlex.quote(PYTHON),
            "tests/pdf_processing/q04/q04_runtime.py --phase init",
            "--bundle " + shlex.quote(REMOTE + "/inputs"),
            "--state " + shlex.quote(REMOTE + "/state"),
            "--capacity " + shlex.quote(CAPACITY),
            "--temporal temporal:7233 --endpoint http://objects:9000 --bucket t09a",
            "--prefix " + shlex.quote(PREFIX),
            "--model-cache " + shlex.quote(MODEL_CACHE),
            "--trial-seconds 180 --capacity-approved",
        )
    )
    output = k(NS, "exec", "coordinator", "--", "sh", "-c", command, timeout=210)
    (OUT / "init.log").write_bytes(output)
    initialized = json.loads(remote(build_initialized_state_probe_program()))
    bundle = json.loads((LOCAL_BUNDLE / "inputs.json").read_text())
    validate_initialized_state(initialized, bundle)
    (OUT / "state-init.json").write_text(
        json.dumps(initialized, indent=2, sort_keys=True) + "\n"
    )
    return initialized


def capture():
    with (OUT / "remote-evidence.tar").open("xb") as output:
        subprocess.run(
            BASE
            + [
                "-n",
                NS,
                "exec",
                "coordinator",
                "--",
                "tar",
                "-C",
                REMOTE,
                "--exclude=./code",
                "--exclude=./inputs",
                "--exclude=./state/acl-option-a-window-c",
                "-cf",
                "-",
                ".",
            ],
            stdout=output,
            stderr=(OUT / "capture.log").open("x"),
            check=True,
            timeout=60,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--owner")
    parser.add_argument("--approval-reference")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("runtime execution requires explicit --execute")
    if not args.owner or not args.approval_reference:
        parser.error("--owner and --approval-reference are required")
    OUT.mkdir()
    holder = None
    holder_log = None
    acquired = False
    claimed = False
    initialized = None
    frozen = None
    runner_manifest = None
    reservation_token = uuid.uuid4().hex
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a+") as local_lock:
        fcntl.flock(local_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            before = deployment_snapshot()
            (OUT / "held-services-before.json").write_text(
                json.dumps(before, indent=2) + "\n"
            )
            assert_candidate_pods_absent()
            t09a_health("health-before.json")
            frozen = frozen_precheck()
            claim_remote_root(reservation_token)
            claimed = True

            holder_script = """import fcntl,json,os
from pathlib import Path
def start_ticks(pid):
 text=Path('/proc')/str(pid)/'stat';value=text.read_text();fields=value[value.rfind(')')+1:].split();return int(fields[19])
with open('/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 pid=os.getpid();lock_identity=os.fstat(lock.fileno())
 record={'coordinator_uid':COORDINATOR_UID,'hostname':Path('/etc/hostname').read_text().strip(),
  'pid':pid,'start_ticks':start_ticks(pid),'lock_device_major':os.major(lock_identity.st_dev),
  'lock_device_minor':os.minor(lock_identity.st_dev),'lock_inode':lock_identity.st_ino,
  'token':TOKEN,'phase':PHASE}
 Path(RESERVATION).open('x').write(json.dumps(record,sort_keys=True))
 while not Path(RELEASE).exists():__import__('time').sleep(.5)
""".replace("COORDINATOR_UID", repr(COORDINATOR_UID)).replace(
                "TOKEN", repr(reservation_token)
            ).replace("PHASE", repr(PHASE)).replace(
                "RESERVATION", repr(RESERVATION)
            ).replace("RELEASE", repr(RELEASE))
            holder_log = (OUT / "reservation.log").open("x")
            holder = subprocess.Popen(
                BASE + ["-n", NS, "exec", "-i", "coordinator", "--", "env", "PYTHONDONTWRITEBYTECODE=1", PYTHON, "-"],
                stdin=subprocess.PIPE,
                stdout=holder_log,
                stderr=subprocess.STDOUT,
            )
            assert holder.stdin is not None
            holder.stdin.write(holder_script.encode())
            holder.stdin.close()
            for _ in range(30):
                assert holder.poll() is None, "reservation holder failed"
                exists = remote(
                    "from pathlib import Path\nprint(Path("
                    + repr(RESERVATION)
                    + ").exists())\n"
                ).strip()
                if exists == b"True":
                    acquired = True
                    break
                time.sleep(0.2)
            assert acquired, "reservation was not acquired"

            start = time.time()
            started_monotonic = time.monotonic()
            lease_ends_monotonic = started_monotonic + WINDOW_SECONDS
            capacity = build_capacity(
                started_at=start,
                owner=args.owner,
                approval_reference=args.approval_reference,
            )
            (OUT / "capacity.json").write_text(json.dumps(capacity, indent=2) + "\n")
            write_remote(CAPACITY, json.dumps(capacity).encode())
            STATE.update(
                started=start,
                ends_at=capacity["ends_at"],
                started_monotonic=started_monotonic,
                ends_monotonic=lease_ends_monotonic,
                work_ends_at=capacity["ends_at"] - CLEANUP_SECONDS,
                reservation=True,
                outer_admission_available_bytes=TARGET,
                outer_observation_seconds=OBSERVATION_SECONDS,
                outer_continuous_seconds=CONTINUOUS_SECONDS,
                per_case_available_bytes=PER_CASE_AVAILABLE_BYTES,
                max_cgroup_bytes=MAX_CGROUP_BYTES,
                minimum_work_seconds=WORKLOAD_SECONDS,
                cleanup_seconds=CLEANUP_SECONDS,
                expected_vm_oom_kill=EXPECTED_VM_OOM_KILL,
                source_state_sha256=frozen["state_sha256"],
                old_request_binding=frozen["old_request_binding"],
                prefix=PREFIX,
            )
            STATE["phase"] = "staging"
            save()
            staged = stage_runtime_tree()
            runner_manifest = stage_admission_runner()
            (OUT / "runner-manifest.json").write_text(
                json.dumps(runner_manifest, indent=2, sort_keys=True) + "\n"
            )
            initialized = run_live_init()
            STATE.update(
                frozen_state_sha256=initialized["state_sha256"],
                run_id=initialized["run_id"],
                runtime_staging=staged,
                runner_manifest=runner_manifest,
            )
            STATE["phase"] = "admission"
            save()

            admission_argv = build_admission_argv(reservation_token)
            admission_program = (
                "import runpy,sys\n"
                + "sys.path[:0]="
                + repr([RUNNER_DIR, REMOTE + "/code/src", REMOTE + "/code/tests/pdf_processing/q04"])
                + "\nsys.argv="
                + repr(admission_argv)
                + "\nrunpy.run_path(sys.argv[0],run_name='__main__')\n"
            )

            def admit():
                result = json.loads(remote(admission_program, timeout=200))
                (OUT / "admission.json").write_text(
                    json.dumps(result, indent=2, sort_keys=True) + "\n"
                )
                return result

            def launch():
                STATE["phase"] = "running-yolo"
                save()
                require_launch_budget(lease_ends_monotonic)
                if holder is None or holder.poll() is not None:
                    raise RuntimeError("reservation transport lost before runtime launch")
                return subprocess.Popen(
                    BASE + ["-n", NS, "exec", "coordinator", "--", "sh", "-c", build_runtime_command()],
                    stdout=(OUT / "runtime-transport.log").open("x"),
                    stderr=subprocess.STDOUT,
                )

            admission_result, driver = launch_after_admission(
                admit, launch, lease_ends_monotonic=lease_ends_monotonic
            )
            STATE["outer_admission"] = admission_result
            while driver.poll() is None:
                assert holder is not None and holder.poll() is None, "reservation transport lost"
                if time.monotonic() >= lease_ends_monotonic - CLEANUP_SECONDS:
                    driver.send_signal(signal.SIGINT)
                    try:
                        driver.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        driver.terminate()
                    raise TimeoutError("work window ended; enter cleanup")
                time.sleep(1)
            STATE["runtime_returncode"] = driver.returncode
            assert driver.returncode == 0, "YOLO driver failed; retain logs, no retry"
            STATE["matrix_passed"] = True
        except BaseException as error:
            STATE["errors"].append({"type": type(error).__name__, "reason": str(error)})
            STATE["phase"] = "failed"
            save()
        finally:
            STATE["phase"] = "cleanup"
            save()
            if claimed:
                try:
                    cleanup_path = REPO / "tests/pdf_processing/q04/sentinel/cleanup.py"
                    cleanup_raw_source = cleanup_path.read_bytes()
                    if runner_manifest is not None:
                        assert hashlib.sha256(cleanup_raw_source).hexdigest() == runner_manifest["cleanup.py"]
                    cleanup_raw = remote(
                        cleanup_raw_source.decode()
                        + "\nasyncio.run(main("
                        + repr(REMOTE)
                        + ", current_phase="
                        + repr(PHASE)
                        + "))\n",
                        timeout=180,
                    )
                    (OUT / "cleanup.json").write_bytes(cleanup_raw)
                    cleanup_result = json.loads(cleanup_raw)
                    STATE["cleanup_verified"] = not cleanup_result["errors"]
                    if cleanup_result["errors"]:
                        STATE["errors"].append({"cleanup_required_intervention": cleanup_result["errors"]})
                        STATE["matrix_passed"] = False
                except BaseException as error:
                    STATE["errors"].append({"cleanup": str(error)})
                    STATE["cleanup_verified"] = False
                if initialized is not None:
                    try:
                        post = json.loads(remote(
                            "import hashlib,json\nfrom pathlib import Path\n"
                            + "new=Path(" + repr(REMOTE) + ");old=Path(" + repr(SOURCE_REMOTE) + ")\n"
                            + "sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()\n"
                            + "print(json.dumps({'state_sha256':sha(new/'state/config.json'),"
                            + "'source_state_sha256':sha(old/'state/config.json'),"
                            + "'phase_complete':(new/'state/" + PHASE + "/phase-complete.json').exists()}))\n"
                        ))
                        assert post["state_sha256"] == initialized["state_sha256"]
                        assert post["source_state_sha256"] == SOURCE_STATE_SHA256
                        (OUT / "frozen-postcheck.json").write_text(json.dumps(post, indent=2) + "\n")
                        STATE["frozen_state_unchanged"] = True
                        STATE["source_state_unchanged"] = True
                    except BaseException as error:
                        STATE["errors"].append({"frozen-postcheck": str(error)})
                try:
                    capture()
                    STATE["evidence_captured"] = True
                    STATE["evidence_sha256"] = hashlib.sha256((OUT / "remote-evidence.tar").read_bytes()).hexdigest()
                    STATE["evidence_bytes"] = (OUT / "remote-evidence.tar").stat().st_size
                except BaseException as error:
                    STATE["errors"].append({"capture": str(error)})
            try:
                after = deployment_snapshot()
                assert_candidate_pods_absent()
                (OUT / "held-services-after.json").write_text(json.dumps(after, indent=2) + "\n")
                t09a_health("health-after.json")
                STATE["services_held_closed"] = True
            except BaseException as error:
                STATE["errors"].append({"held-service-verification": str(error)})
                STATE["services_held_closed"] = False
            if acquired:
                try:
                    write_remote(RELEASE, b"complete\n")
                    assert holder is not None
                    holder.wait(timeout=10)
                    assert holder.returncode == 0
                    STATE["reservation_released"] = True
                except BaseException as error:
                    STATE["errors"].append({"reservation-release": str(error)})
            elif holder is not None and holder.poll() is None:
                holder.terminate()
                try:
                    holder.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    holder.kill()
            if holder_log is not None:
                holder_log.close()
            STATE["finished"] = time.time()
            STATE["phase"] = "complete" if not STATE["errors"] else "needs-review"
            save()
    return 0 if not STATE["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
