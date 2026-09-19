"""Run one authorized fixture-07 matrix in the reviewed worker Pod cgroup.

Import and ``--offline-check`` are local-only.  ``--execute`` is the sole path
that may upload the private ConfigMaps, create Kubernetes objects, or start the
Pod-local supervisor.  It is intentionally single-use and never retries.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time
import uuid

Q04 = Path(__file__).resolve().parent.parent
REPO = Q04.parents[2]
if str(Q04) not in sys.path:
    sys.path.insert(0, str(Q04))

import pod_topology
from outer_admission import OuterAdmissionPolicy, observe_capacity
from pod_remote_evidence import (
    FINAL_REQUIRED,
    IncrementalEvidenceMirror,
    PodEvidenceIdentity,
    pull_once,
)
from sentinel import run_yolo_lifecycle_a as lifecycle


PHASE = "yolo-pod-cgroup-a"
RUN_IDENTITY = "q04-yolo-pod-cgroup-20260919-a"
PREFIX = "q04/yolo-pod-cgroup-20260919-a/"
OUT = Path("/private/tmp/q04-yolo-pod-cgroup-20260919-a")
CONTROL = "/q04-control"
BUNDLE = Path("/private/tmp/q04-inputs-yolo-lifecycle-v1")
WINDOW_SECONDS = 1500
OUTER_OBSERVATION_SECONDS = 180
CONTINUOUS_SECONDS = 60
WORKLOAD_SECONDS = 825
CLEANUP_SECONDS = 300
OUTER_AVAILABLE_BYTES = 4_831_838_208
PER_CASE_AVAILABLE_BYTES = 3_221_225_472
VM_RUNTIME_FLOOR_BYTES = 1_610_612_736
CGROUP_GUARD_BYTES = 4_294_967_296
HARD_LIMIT_BYTES = 5_368_709_120
SAMPLE_INTERVAL_SECONDS = 0.25
TRANSPORT_INTERVAL_SECONDS = 2.0
TRANSPORT_GAP_SECONDS = 5.0
CONTEXT = "kind-internal-a2a-vs6-local"
NAMESPACE = pod_topology.NAMESPACE
DEPLOYMENT = pod_topology.DEPLOYMENT
RUN_LABEL = pod_topology.RUN_LABEL
NODE = pod_topology.NODE
WORKER_YAML = Q04 / "pod-topology-v1/WORKER.yaml"
OFFLINE_MANIFEST = Q04 / "pod-topology-v1/RUNNER-MANIFEST.json"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def authorization_scope() -> dict:
    return {
        "phase": PHASE,
        "run_identity": RUN_IDENTITY,
        "fixture": "07",
        "modes": ["fresh", "restored", "replay"],
        "automatic_retry": False,
        "window_seconds": WINDOW_SECONDS,
        "outer_observation_seconds": OUTER_OBSERVATION_SECONDS,
        "outer_continuous_seconds": CONTINUOUS_SECONDS,
        "outer_available_bytes": OUTER_AVAILABLE_BYTES,
        "per_case_available_bytes": PER_CASE_AVAILABLE_BYTES,
        "workload_seconds": WORKLOAD_SECONDS,
        "cleanup_seconds": CLEANUP_SECONDS,
        "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
        "transport_interval_seconds": TRANSPORT_INTERVAL_SECONDS,
        "cgroup_guard_bytes": CGROUP_GUARD_BYTES,
        "container_hard_limit_bytes": HARD_LIMIT_BYTES,
        "vm_runtime_floor_bytes": VM_RUNTIME_FLOOR_BYTES,
        "deployment": DEPLOYMENT,
        "deployment_initial_replicas": 0,
        "held_deployments_restored": False,
    }


def authorization_scope_sha256() -> str:
    return sha256(canonical(authorization_scope()))


def build_capacity(*, starts_at: float, owner: str, approval_reference: str) -> dict:
    if not owner or not approval_reference:
        raise ValueError("capacity owner and approval reference required")
    return {
        "status": "AUTHORIZED",
        "phase": PHASE,
        "owner": owner,
        "approval_reference": approval_reference,
        "starts_at": starts_at,
        "ends_at": starts_at + WINDOW_SECONDS,
        "proposed_window_seconds": WINDOW_SECONDS,
        "outer_observation_seconds": OUTER_OBSERVATION_SECONDS,
        "outer_continuous_seconds": CONTINUOUS_SECONDS,
        "outer_admission_available_bytes": OUTER_AVAILABLE_BYTES,
        "admission_seconds": CONTINUOUS_SECONDS,
        "admission_available_bytes": PER_CASE_AVAILABLE_BYTES,
        "minimum_work_seconds": WORKLOAD_SECONDS,
        "cleanup_seconds": CLEANUP_SECONDS,
        "min_available_bytes": VM_RUNTIME_FLOOR_BYTES,
        "max_cgroup_bytes": CGROUP_GUARD_BYTES,
        "container_hard_limit_bytes": HARD_LIMIT_BYTES,
        "max_full_psi": 0,
        "max_sample_gap_seconds": 1,
        "max_replacement_seconds": 120,
        "expected_vm_oom_kill": 0,
        "expected_cgroup_oom_kill": 0,
        "automatic_retry": False,
        "authorization_scope_sha256": authorization_scope_sha256(),
    }


def workload_argv() -> list[str]:
    return [
        "/experiment/.venv/bin/python",
        "/workspace/tests/pdf_processing/q04/pod_workload.py",
        "--prefix", PREFIX,
        "--authorization-scope-sha256", authorization_scope_sha256(),
        "--workload-seconds", str(WORKLOAD_SECONDS),
        "--pod-temporal", "temporal:7233",
        "--pod-objects", "http://objects:9000",
    ]


def exact_command() -> str:
    return shlex.join(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--execute",
            "--owner", "main-session",
            "--approval-reference",
            "Separate explicit main-session authorization for q04-yolo-pod-cgroup-20260919-a",
            "--authorization-scope-sha256", authorization_scope_sha256(),
        ]
    )


def scale_patch(uid: str, resource_version: str, before: int, after: int) -> list[dict]:
    return [
        {"op": "test", "path": "/metadata/uid", "value": uid},
        {
            "op": "test",
            "path": "/metadata/resourceVersion",
            "value": resource_version,
        },
        {"op": "test", "path": "/spec/replicas", "value": before},
        {"op": "replace", "path": "/spec/replicas", "value": after},
    ]


def pod_delete_options(uid: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "DeleteOptions",
        "gracePeriodSeconds": 0,
        "preconditions": {"uid": uid},
    }


def validate_pod(pod: dict) -> dict:
    if pod["metadata"]["labels"].get("q04-run") != RUN_LABEL:
        raise ValueError("Pod run label changed")
    if pod["spec"].get("nodeName") != NODE:
        raise ValueError("Pod node changed")
    statuses = pod["status"].get("containerStatuses", [])
    if len(statuses) != 1 or not statuses[0].get("ready"):
        raise ValueError("exactly one ready worker container required")
    if statuses[0].get("restartCount") != 0:
        raise ValueError("worker Pod restarted")
    if pod["spec"]["containers"][0]["image"] != pod_topology.IMAGE:
        raise ValueError("worker image reference changed")
    if statuses[0]["imageID"] != pod_topology.IMAGE_CONTENT_ID:
        raise ValueError("worker image digest changed")
    return {
        "pod_name": pod["metadata"]["name"],
        "pod_uid": pod["metadata"]["uid"],
        "resource_version": pod["metadata"]["resourceVersion"],
        "container_id": statuses[0]["containerID"],
        "image_id": statuses[0]["imageID"],
        "restart_count": statuses[0]["restartCount"],
        "node": pod["spec"]["nodeName"],
    }


def build_offline_manifest() -> dict:
    paths = {
        "runner": Path(__file__),
        "pod_workload": Q04 / "pod_workload.py",
        "pod_init": Q04 / "pod_init.py",
        "remote_evidence": Q04 / "pod_remote_evidence.py",
        "topology_builder": Q04 / "pod_topology.py",
        "worker_yaml": WORKER_YAML,
        "source_manifest": Q04 / "pod-topology-v1/SOURCE-MANIFEST.json",
        "run_plan": Q04 / "pod-topology-v1/RUN-PLAN.md",
        "readme": Q04 / "pod-topology-v1/README.md",
        "base_current_tests": Q04 / "pod-topology-v1/BASE-CURRENT-TESTS.md",
        "integration_manifest": Q04 / "pod-topology-v1/INTEGRATION-MANIFEST.json",
        "durable_evidence_feasibility": Q04 / "pod-topology-v1/DURABLE-EVIDENCE-FEASIBILITY.md",
        "server_dry_run_scope": Q04 / "pod-topology-v1/SERVER-DRY-RUN-SCOPE.md",
        "outer_admission": Q04 / "outer_admission.py",
        "held_deployment_identity": Q04 / "sentinel/run_yolo_lifecycle_a.py",
    }
    return {
        "schema_version": 1,
        "identity": {
            "phase": PHASE,
            "run_identity": RUN_IDENTITY,
            "prefix": PREFIX,
            "output": str(OUT),
            "deployment": DEPLOYMENT,
        },
        "authorization_scope": authorization_scope(),
        "authorization_scope_sha256": authorization_scope_sha256(),
        "sources": {name: sha256(path.read_bytes()) for name, path in paths.items()},
        "bundle_inputs_sha256": sha256((BUNDLE / "inputs.json").read_bytes()),
        "workload_argv": workload_argv(),
        "exact_single_run_command": exact_command(),
        "runtime_authorized": False,
        "runtime_readiness": "NOT_RUNTIME_READY",
        "runtime_blocker": "durable evidence path not implemented",
        "private_configmap_upload_requires_approval": True,
        "cluster_mutation_requires_approval": True,
        "server_side_dry_run_forbidden": True,
    }


def offline_check() -> dict:
    manifest = build_offline_manifest()
    if json.loads(OFFLINE_MANIFEST.read_text()) != manifest:
        raise ValueError("runner manifest differs from executable plan")
    topology = json.loads(WORKER_YAML.read_text())
    pod_topology.validate(topology)
    if topology["items"][2]["spec"]["replicas"] != 0:
        raise ValueError("committed topology is active")
    if workload_argv()[workload_argv().index("--workload-seconds") + 1] != "825":
        raise ValueError("workload budget changed")
    return {
        "status": "PASS_OFFLINE_ONLY",
        "authorization_scope_sha256": authorization_scope_sha256(),
        "exact_single_run_command": exact_command(),
        "runtime_authorized": False,
        "runtime_readiness": "NOT_RUNTIME_READY",
    }


class Kubectl:
    """Small command adapter used by the runner and replaced by local tests."""

    base = ["kubectl", "--context", CONTEXT, "--request-timeout=15s", "-n", NAMESPACE]

    def run(self, args, *, input=None, text=True, timeout=30):
        return subprocess.check_output(
            self.base + list(args), input=input, text=text, timeout=timeout
        )

    def json(self, *args, timeout=30):
        return json.loads(self.run([*args, "-o", "json"], timeout=timeout))

    def exec_python(self, pod: str, program: str, timeout=30) -> str:
        return self.run(
            ["exec", pod, "--", "/experiment/.venv/bin/python", "-c", program],
            timeout=timeout,
        )


def sample_program() -> str:
    return """import json,time
from pathlib import Path
def fields(path):return {x.split()[0].rstrip(':'):int(x.split()[1]) for x in Path(path).read_text().splitlines()}
full=next(x for x in Path('/proc/pressure/memory').read_text().splitlines() if x.startswith('full '))
pressure=dict(x.split('=') for x in full.split()[1:])
print(json.dumps({'time':time.time(),'available':fields('/proc/meminfo')['MemAvailable']*1024,
 'vm_oom_kill':fields('/proc/vmstat')['oom_kill'],'memory_current':int(Path('/sys/fs/cgroup/memory.current').read_text()),
 'memory_events':fields('/sys/fs/cgroup/memory.events'),'psi_full_avg10':float(pressure['avg10'])}))
"""


def _fields(raw: str) -> dict[str, int]:
    return {
        line.split()[0].rstrip(":"): int(line.split()[1])
        for line in raw.splitlines()
        if len(line.split()) >= 2 and line.split()[1].isdigit()
    }


def node_vm_sample(*, deadline: float | None = None) -> dict:
    """Read the Docker VM/node view before a worker cgroup exists."""
    def cat(path):
        timeout = 10 if deadline is None else remaining_timeout(
            deadline, 10, "node VM telemetry"
        )
        return subprocess.check_output(
            ["docker", "exec", NODE, "cat", path], text=True, timeout=timeout
        )

    meminfo = _fields(cat("/proc/meminfo"))
    vmstat = _fields(cat("/proc/vmstat"))
    full = next(
        row for row in cat("/proc/pressure/memory").splitlines()
        if row.startswith("full ")
    )
    pressure = dict(field.split("=") for field in full.split()[1:])
    return {
        "time": time.time(),
        "available": meminfo["MemAvailable"] * 1024,
        "psi_full_avg10": float(pressure["avg10"]),
        "vm_oom_kill": vmstat["oom_kill"],
        # The worker Pod must not exist during outer admission. Its future cgroup
        # therefore has no current charge or OOM event yet.
        "memory_current": 0,
        "memory_events": {"oom_kill": 0},
    }


def verify_outer_identity(kube: Kubectl, *, deadline: float | None = None) -> None:
    timeout = 30 if deadline is None else remaining_timeout(deadline, 30, "node identity")
    node = kube.json("get", "node", NODE, timeout=timeout)
    if node["metadata"]["uid"] != "b33ff221-3443-4b27-83bd-01ce69d0bb01":
        raise ValueError("node UID changed")
    boot = node["status"]["nodeInfo"]["bootID"]
    if boot != "c01b81ac-b0fd-4ce6-8cda-f0da74b9bbd3":
        raise ValueError("node boot identity changed")
    timeout = 30 if deadline is None else remaining_timeout(deadline, 30, "Pod absence")
    pods = kube.json("get", "pods", "-l", "q04-run=" + RUN_LABEL, timeout=timeout)["items"]
    if pods:
        raise ValueError("owned worker Pod already exists")
    verify_held_deployments(kube, deadline=deadline)


def verify_held_deployments(kube: Kubectl, *, deadline: float | None = None) -> None:
    timeout = 30 if deadline is None else remaining_timeout(deadline, 30, "held Deployments")
    deployments = kube.json("get", "deployments", "-A", timeout=timeout)["items"]
    observed = {
        (item["metadata"]["namespace"], item["metadata"]["name"]): item
        for item in deployments
    }
    for expected in lifecycle.CANDIDATES:
        item = observed[(expected["namespace"], expected["name"])]
        if item["metadata"]["uid"] != expected["uid"]:
            raise ValueError("held Deployment UID changed")
        if item["spec"].get("replicas", 1) != 0 or item["status"].get("readyReplicas", 0) != 0:
            raise ValueError("held Deployment resumed")


def verify_live_pod_identity(
    kube: Kubectl, identity: dict, *, deadline: float | None = None
) -> None:
    timeout = 30 if deadline is None else remaining_timeout(deadline, 30, "live Pod identity")
    pod = kube.json("get", "pod", identity["pod_name"], timeout=timeout)
    current = validate_pod(pod)
    if (
        current["pod_uid"] != identity["pod_uid"]
        or current["container_id"] != identity["container_id"]
    ):
        raise ValueError("worker Pod/container identity changed")
    verify_held_deployments(kube, deadline=deadline)


def t09a_health(
    kube: Kubectl,
    output: Path,
    *,
    require_idle: bool,
    deadline: float | None = None,
) -> dict:
    health_program = """import asyncio,json,urllib.request
from temporalio.client import Client
async def main():
 c=await Client.connect('temporal:7233')
 print(json.dumps({'healthy':await c.service_client.check_health(),
  'running':[w.id async for w in c.list_workflows(query='ExecutionStatus="Running"')],
  'objects':urllib.request.urlopen('http://objects:9000/minio/health/ready',timeout=5).status}))
asyncio.run(main())
"""
    timeout = 30 if deadline is None else remaining_timeout(deadline, 30, "T09a health")
    value = json.loads(kube.exec_python("coordinator", health_program, timeout=timeout))
    if not (
        value["healthy"]
        and (not require_idle or not value["running"])
        and value["objects"] == 200
    ):
        raise ValueError("T09a is not idle and healthy")
    output.write_text(json.dumps(value, indent=2) + "\n")
    return value


def run_outer_admission(kube: Kubectl, capacity: dict) -> dict:
    t09a_health(
        kube, OUT / "pod-cgroup-health-before-admission.json", require_idle=True
    )
    stream = (OUT / "pre-admission.jsonl").open("x", buffering=1)
    policy = OuterAdmissionPolicy(
        available_bytes=OUTER_AVAILABLE_BYTES,
        continuous_seconds=CONTINUOUS_SECONDS,
        observation_seconds=OUTER_OBSERVATION_SECONDS,
        sample_interval_seconds=1,
        max_sample_gap_seconds=2,
        max_cgroup_bytes=CGROUP_GUARD_BYTES,
        expected_vm_oom_kill=capacity["expected_vm_oom_kill"],
        expected_cgroup_oom_kill=0,
        minimum_work_seconds=WORKLOAD_SECONDS,
        cleanup_seconds=CLEANUP_SECONDS,
    )
    try:
        result = observe_capacity(
            policy,
            lease_ends_at=capacity["ends_at"],
            sample=node_vm_sample,
            verify_identity=lambda: verify_outer_identity(kube),
            record=lambda row: stream.write(json.dumps(row, sort_keys=True) + "\n"),
        )
    finally:
        stream.close()
    t09a_health(
        kube, OUT / "pod-cgroup-health-after-admission.json", require_idle=True
    )
    (OUT / "admission.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def verify_runtime_sample(row: dict, baseline_oom: int) -> None:
    if row["available"] < VM_RUNTIME_FLOOR_BYTES:
        raise ValueError("VM runtime memory floor breached")
    if row["psi_full_avg10"] != 0:
        raise ValueError("VM PSI guard breached")
    if row["vm_oom_kill"] != baseline_oom:
        raise ValueError("VM OOM counter changed")
    events = row["memory_events"]
    if any(events.get(name, 0) != 0 for name in ("oom", "oom_kill", "oom_group_kill")):
        raise ValueError("worker cgroup OOM counter changed")
    if row["memory_current"] > CGROUP_GUARD_BYTES:
        raise ValueError("4 GiB qualification guard breached")


def stop_owned_supervisor_program(graceful_seconds: float) -> str:
    return """import json,os,signal,time
from pathlib import Path
path=Path('/q04-control/supervisor-ownership.json')
if not path.exists(): print(json.dumps({'identity_published':False}));raise SystemExit(0)
owner=json.loads(path.read_text());pid=owner['pid']
raw=(Path('/proc')/str(pid)/'stat').read_text();ticks=int(raw[raw.rfind(')')+1:].split()[19])
if ticks!=owner['start_ticks']: raise ValueError('supervisor PID identity changed')
os.kill(pid,signal.SIGINT)
deadline=time.monotonic()+GRACE
while (Path('/proc')/str(pid)).exists() and time.monotonic()<deadline: time.sleep(.2)
print(json.dumps({'identity_published':True,'pid':pid,'start_ticks':ticks,
 'absent':not (Path('/proc')/str(pid)).exists()}))
""".replace("GRACE", repr(graceful_seconds))


def terminal_cleanup_program() -> str:
    return """import json
from pathlib import Path
root=Path('/q04-control');owner=json.loads((root/'supervisor-ownership.json').read_text())
cleanup=json.loads((root/'cleanup-complete.json').read_text())
absent=not (Path('/proc')/str(owner['pid'])).exists()
complete=all(cleanup.get(k) is True for k in ('worker_absent','owned_children_absent','scratch_absent'))
print(json.dumps({'pid':owner['pid'],'start_ticks':owner['start_ticks'],
 'supervisor_absent':absent,'cleanup_complete':complete}))
"""


def force_stop_supervisor_program() -> str:
    return """import json,os,shutil,signal,time,psutil
from pathlib import Path
root=Path('/q04-control');owner=json.loads((root/'supervisor-ownership.json').read_text());pid=owner['pid']
proc=Path('/proc')/str(pid);stat=proc/'stat';supervisor=psutil.Process(pid);owned=supervisor.children(recursive=True)
raw=stat.read_text();ticks=int(raw[raw.rfind(')')+1:].split()[19])
if ticks!=owner['start_ticks']: raise ValueError('supervisor PID identity changed')
groups=set()
for child in owned:
 try: groups.add(os.getpgid(child.pid))
 except ProcessLookupError: pass
owned_path=root/'ownership.json'
if owned_path.exists():
 execution=json.loads(owned_path.read_text());epid=execution['pid'];eproc=Path('/proc')/str(epid)
 if (eproc/'stat').exists():
  raw=(eproc/'stat').read_text();ticks=int(raw[raw.rfind(')')+1:].split()[19])
  if ticks!=execution['start_ticks']: raise ValueError('measurement PID identity changed')
  process=psutil.Process(epid);owned=list({p.pid:p for p in owned+process.children(recursive=True)}.values())
  if os.getpgid(epid)!=epid: raise ValueError('measurement process group changed')
  groups.add(epid);os.killpg(epid,signal.SIGKILL)
for child in reversed(owned):
 try:
  group=os.getpgid(child.pid)
  if group==child.pid: os.killpg(group,signal.SIGKILL)
  else: child.kill()
 except (ProcessLookupError,psutil.NoSuchProcess): pass
if owned: psutil.wait_procs(owned,timeout=10)
if stat.exists():
 os.kill(pid,signal.SIGKILL)
 deadline=time.monotonic()+10
 while proc.exists() and time.monotonic()<deadline: time.sleep(.05)
unknown=[];remaining=[]
for candidate in Path('/proc').iterdir():
 if not candidate.name.isdigit(): continue
 try:
  row=(candidate/'stat').read_text();pgrp=int(row[row.rfind(')')+1:].split()[2])
  if pgrp in groups: remaining.append(int(candidate.name))
 except FileNotFoundError: pass
 except (PermissionError,ValueError,IndexError) as error: unknown.append([candidate.name,type(error).__name__])
owned_absent=not remaining and not unknown and all(not (Path('/proc')/str(p.pid)).exists() for p in owned)
config=json.loads((root/'state/config.json').read_text());scratches=[]
if config.get('pod_namespace'): scratches=[Path('/scratch')/config['run_id']]
else: scratches=[path/'scratch' for path in (root/'state/yolo-pod-cgroup-a').glob('worker-*')]
if owned_absent and not proc.exists():
 for scratch in scratches: shutil.rmtree(scratch,ignore_errors=True)
scratch_absent=all(not path.exists() for path in scratches)
print(json.dumps({'pid':pid,'start_ticks':owner['start_ticks'],'absent':not proc.exists(),
 'owned_group_absent':owned_absent,'remaining_group_pids':remaining,'proc_scan_unknown':unknown,
 'scratch_paths':[str(path) for path in scratches],'scratch_absent':scratch_absent}))
"""


def archive_fingerprint_program() -> str:
    return """import hashlib,json
from pathlib import Path
root=Path('/q04-control');rows=[]
for path in sorted(root.rglob('*')):
 if not path.is_file(): continue
 name=path.relative_to(root).as_posix()
 if name=='inputs' or name.startswith('inputs/') or name=='workload.log': continue
 raw=path.read_bytes();rows.append([name,len(raw),hashlib.sha256(raw).hexdigest()])
print(json.dumps(rows,separators=(',',':')))
"""


def verify_local_archive(path: Path, remote_rows: list[list]) -> None:
    expected = {name: (size, digest) for name, size, digest in remote_rows}
    observed = {}
    with tarfile.open(path, "r") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            name = member.name.removeprefix("./")
            if name == "workload.log" or name == "inputs" or name.startswith("inputs/"):
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("archive file body missing")
            raw = stream.read()
            if name in observed:
                raise ValueError("duplicate archive evidence path")
            observed[name] = (len(raw), sha256(raw))
    if observed != expected:
        raise ValueError("local archive differs from stable remote fingerprint")


def remaining_timeout(deadline: float, maximum: float, action: str) -> float:
    remaining = deadline - time.time()
    if remaining <= 0:
        raise TimeoutError(f"lease expired before {action}")
    return max(0.001, min(maximum, remaining))


def transport_receipt_expired(future, submitted_at: float | None, now: float) -> bool:
    return (
        future is not None
        and submitted_at is not None
        and now - submitted_at > TRANSPORT_GAP_SECONDS
    )


def create_owned_objects(kube: Kubectl, items: list[dict], owned: list[dict]) -> list[dict]:
    """Atomically create each object and record only server-returned ownership."""
    created = []
    for item in items:
        obj = json.loads(kube.run(
            ["create", "-f", "-", "-o", "json"],
            input=json.dumps(item),
            timeout=30,
        ))
        owned.append({
            "kind": item["kind"],
            "name": item["metadata"]["name"],
            "uid": obj["metadata"]["uid"],
        })
        created.append(obj)
    return created


def cleanup_deployment_and_pod(
    kube: Kubectl,
    deployment: dict,
    pod_identity: dict | None,
    *,
    deadline: float,
) -> dict:
    result = {}
    current = kube.json(
        "get", "deployment", DEPLOYMENT,
        timeout=remaining_timeout(deadline, 30, "Deployment cleanup identity"),
    )
    before = current["spec"].get("replicas", 0)
    patch = scale_patch(
        deployment["metadata"]["uid"],
        current["metadata"]["resourceVersion"],
        before,
        0,
    )
    kube.run(
        ["patch", "deployment", DEPLOYMENT, "--type=json", "-p", json.dumps(patch)],
        timeout=remaining_timeout(deadline, 30, "scale-to-zero"),
    )
    result["deployment_scaled_zero"] = True
    if pod_identity is None:
        return result
    current_pod = kube.run(
        [
            "get", "pod", pod_identity["pod_name"],
            "--ignore-not-found", "-o", "name",
        ],
        timeout=remaining_timeout(deadline, 15, "Pod cleanup identity"),
    ).strip()
    if current_pod:
        kube.run(
            [
                "delete", "--raw",
                f"/api/v1/namespaces/{NAMESPACE}/pods/{pod_identity['pod_name']}",
                "-f", "-",
            ],
            input=json.dumps(pod_delete_options(pod_identity["pod_uid"])),
            timeout=remaining_timeout(deadline, 30, "Pod UID-fenced delete"),
        )
        result["pod_delete_uid_precondition_sent"] = True
    while kube.run(
        ["get", "pod", pod_identity["pod_name"], "--ignore-not-found", "-o", "name"],
        timeout=remaining_timeout(deadline, 15, "Pod absence check"),
    ).strip():
        if time.time() >= deadline:
            raise TimeoutError("owned Pod did not terminate")
        time.sleep(1)
    raw = subprocess.check_output(
        [
            "docker", "exec", NODE, "crictl", "ps", "--state", "Running",
            "--label", "io.kubernetes.pod.uid=" + pod_identity["pod_uid"],
            "-o", "json",
        ],
        text=True,
        timeout=remaining_timeout(deadline, 20, "container absence check"),
    )
    if json.loads(raw)["containers"]:
        raise ValueError("old Pod runtime remains")
    for volume in ("scratch", "control", "tmp"):
        subprocess.run(
            [
                "docker", "exec", NODE, "test", "!", "-e",
                f"/var/lib/kubelet/pods/{pod_identity['pod_uid']}/volumes/kubernetes.io~empty-dir/{volume}",
            ],
            check=True,
            timeout=remaining_timeout(deadline, 20, "emptyDir absence check"),
        )
    result["old_runtime_absent"] = True
    result["emptydirs_absent"] = True
    return result


def delete_owned_objects(
    kube: Kubectl, owned_objects: list[dict], *, deadline: float
) -> dict:
    deleted = []
    errors = {}
    for obj in reversed(owned_objects):
        resource = {"Deployment": "deployments", "ConfigMap": "configmaps"}[
            obj["kind"]
        ]
        body = json.dumps({
            "apiVersion": "v1",
            "kind": "DeleteOptions",
            "preconditions": {"uid": obj["uid"]},
        })
        try:
            kube.run(
                [
                    "delete", "--raw",
                    f"/apis/apps/v1/namespaces/{NAMESPACE}/{resource}/{obj['name']}"
                    if obj["kind"] == "Deployment"
                    else f"/api/v1/namespaces/{NAMESPACE}/{resource}/{obj['name']}",
                    "-f", "-",
                ],
                input=body,
                timeout=remaining_timeout(deadline, 30, "owned object deletion"),
            )
            deleted.append(obj)
        except BaseException as error:
            errors[obj["kind"] + "/" + obj["name"]] = repr(error)
    return {"deleted": deleted, "errors": errors}


def execute_window(args, kube=None) -> dict:
    """Execute exactly once; callers must provide the explicit reviewed digest."""
    offline_check()
    if args.authorization_scope_sha256 != authorization_scope_sha256():
        raise ValueError("authorization scope digest changed")
    kube = kube or Kubectl()
    OUT.mkdir(exist_ok=False)
    capacity = build_capacity(
        starts_at=time.time(), owner=args.owner, approval_reference=args.approval_reference
    )
    (OUT / "capacity.json").write_text(json.dumps(capacity, indent=2) + "\n")
    deployment = None
    owned_objects = []
    pod_identity = None
    workload = None
    vm_stream = None
    mirror = None
    transport_pool = None
    transport_future = None
    transport_submitted_at = None
    evidence_captured = False
    primary_error = None
    baseline_oom = None
    try:
        admission = run_outer_admission(kube, capacity)
        if admission["minimum_available"] < OUTER_AVAILABLE_BYTES:
            raise ValueError("outer admission threshold changed")
        rendered = json.loads(WORKER_YAML.read_text())
        created_specs = create_owned_objects(kube, rendered["items"], owned_objects)
        (OUT / "created-object-specs.json").write_text(
            json.dumps(created_specs, indent=2) + "\n"
        )
        deployment = kube.json("get", "deployment", DEPLOYMENT)
        if deployment["spec"].get("replicas") != 0:
            raise ValueError("new Deployment was not inactive")
        patch = scale_patch(
            deployment["metadata"]["uid"],
            deployment["metadata"]["resourceVersion"],
            0,
            1,
        )
        kube.run(
            ["patch", "deployment", DEPLOYMENT, "--type=json", "-p", json.dumps(patch)]
        )
        deadline = time.monotonic() + 120
        while True:
            pods = kube.json("get", "pods", "-l", "q04-run=" + RUN_LABEL)["items"]
            ready = [p for p in pods if p.get("status", {}).get("phase") == "Running"]
            if len(ready) == 1:
                try:
                    pod_identity = validate_pod(ready[0])
                    (OUT / "created-pod-spec.json").write_text(
                        json.dumps(ready[0], indent=2) + "\n"
                    )
                    break
                except ValueError:
                    pass
            if time.monotonic() >= deadline:
                raise TimeoutError("worker Pod readiness expired")
            time.sleep(1)
        pod = pod_identity["pod_name"]
        preflight = kube.exec_python(
            pod,
            "from pathlib import Path;import json,sys;sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
            "from pod_workload import no_inference_preflight;"
            "print(json.dumps(no_inference_preflight(Path('/workspace'),Path('/q04-control'),Path('/experiment/PROTOTYPE-wipe-me/hf'))))",
        )
        (OUT / "pod-no-inference-preflight.json").write_text(preflight)
        subprocess.run(
            kube.base + ["cp", str(BUNDLE), pod + ":" + CONTROL + "/inputs"],
            check=True,
            timeout=180,
            stdout=(OUT / "bundle-copy.log").open("x"),
            stderr=subprocess.STDOUT,
        )
        capacity_raw = (OUT / "capacity.json").read_bytes()
        stage_capacity = (
            "from pathlib import Path;import sys;"
            "Path('/q04-control/capacity.json').open('xb').write(sys.stdin.buffer.read())"
        )
        kube.run(
            ["exec", "-i", pod, "--", "/experiment/.venv/bin/python", "-c", stage_capacity],
            input=capacity_raw.decode(),
        )
        if time.time() + WORKLOAD_SECONDS + CLEANUP_SECONDS > capacity["ends_at"]:
            raise ValueError("insufficient fixed lease for workload and cleanup")
        evidence_deadline = capacity["ends_at"] - 120
        workload = subprocess.Popen(
            kube.base + ["exec", pod, "--", *workload_argv()],
            stdout=(OUT / "workload-transport.log").open("x"),
            stderr=subprocess.STDOUT,
        )
        vm_stream = (OUT / "vm-controller.jsonl").open("x", buffering=1)
        started = time.monotonic()
        workload_deadline = min(
            capacity["ends_at"] - CLEANUP_SECONDS,
            time.time() + WORKLOAD_SECONDS,
        )
        baseline_oom = capacity["expected_vm_oom_kill"]
        next_transport = started
        next_identity = started
        vm_rows = []
        while workload.poll() is None:
            row = json.loads(kube.exec_python(
                pod, sample_program(),
                timeout=remaining_timeout(workload_deadline, 30, "VM telemetry sample"),
            ))
            verify_runtime_sample(row, baseline_oom)
            if vm_rows:
                gap = row["time"] - vm_rows[-1]["time"]
                if gap <= 0 or gap > 1:
                    raise ValueError("controller VM telemetry gap exceeded")
            vm_rows.append(row)
            vm_stream.write(json.dumps(row, sort_keys=True) + "\n")
            if time.monotonic() >= next_identity:
                verify_live_pod_identity(
                    kube, pod_identity, deadline=workload_deadline
                )
                next_identity = time.monotonic() + TRANSPORT_INTERVAL_SECONDS
            if mirror is None:
                try:
                    owner = json.loads(
                        kube.exec_python(
                            pod,
                            "from pathlib import Path;import json;"
                            "s=json.loads(Path('/q04-control/supervisor-ownership.json').read_text());"
                            "w=json.loads(Path('/q04-control/ownership.json').read_text());"
                            "print(json.dumps({'pid':s['pid'],'start_ticks':s['start_ticks'],"
                            "'config_sha256':w['config_sha256']}))",
                        )
                    )
                    identity = PodEvidenceIdentity(
                        pod_uid=pod_identity["pod_uid"],
                        container_id=pod_identity["container_id"],
                        worker_pid=owner["pid"],
                        worker_start_ticks=owner["start_ticks"],
                        config_sha256=owner["config_sha256"],
                    )
                    kube.run(
                        ["exec", "-i", pod, "--", "/experiment/.venv/bin/python", "-c",
                         "from pathlib import Path;import sys;Path('/q04-control/transport-identity.json').open('x').write(sys.stdin.read())"],
                        input=json.dumps(identity.__dict__, sort_keys=True),
                    )
                    mirror = IncrementalEvidenceMirror(
                        OUT / "evidence", identity,
                        maximum_transport_gap_seconds=TRANSPORT_GAP_SECONDS,
                    )
                    transport_pool = ThreadPoolExecutor(max_workers=1)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    pass
            if transport_receipt_expired(
                transport_future, transport_submitted_at, time.monotonic()
            ):
                raise TimeoutError("evidence transport receipt gap exceeded")
            if transport_future is not None and transport_future.done():
                transport_future.result()
                transport_future = None
                transport_submitted_at = None
            if mirror is not None and transport_future is None and time.monotonic() >= next_transport:
                transport_future = transport_pool.submit(
                    pull_once, mirror, CONTROL,
                    lambda program: kube.exec_python(pod, program),
                    now=time.monotonic,
                )
                transport_submitted_at = time.monotonic()
                next_transport = time.monotonic() + TRANSPORT_INTERVAL_SECONDS
            if time.time() >= workload_deadline:
                raise TimeoutError("Pod workload budget expired")
            time.sleep(SAMPLE_INTERVAL_SECONDS)
        vm_stream.close()
        if not vm_rows:
            raise ValueError("controller VM telemetry never started")
        (OUT / "vm-controller-summary.json").write_text(
            json.dumps(
                {
                    "samples": len(vm_rows),
                    "maximum_gap_seconds": max(
                        (b["time"] - a["time"] for a, b in zip(vm_rows, vm_rows[1:])),
                        default=0,
                    ),
                    "minimum_available_bytes": min(row["available"] for row in vm_rows),
                    "maximum_cgroup_bytes": max(row["memory_current"] for row in vm_rows),
                    "pod_uid": pod_identity["pod_uid"],
                    "container_id": pod_identity["container_id"],
                },
                indent=2,
            )
            + "\n"
        )
        if workload.returncode != 0:
            raise RuntimeError("Pod workload failed; no retry")
        if mirror is None:
            raise ValueError("worker ownership/evidence identity was never published")
        if transport_future is not None:
            transport_future.result(
                timeout=remaining_timeout(evidence_deadline, 30, "final transport")
            )
            transport_future = None
        while not set(FINAL_REQUIRED).issubset(mirror.complete):
            remaining_timeout(evidence_deadline, 30, "complete evidence drain")
            pull_once(
                mirror, CONTROL,
                lambda program: kube.exec_python(
                    pod, program,
                    timeout=remaining_timeout(
                        evidence_deadline, 30, "complete evidence drain"
                    ),
                ),
                now=time.monotonic,
            )
        result = mirror.finalize(require_success=True)
        (OUT / "transport-ledger.json").write_text(
            json.dumps({"records": mirror.records, "result": result}, indent=2) + "\n"
        )
        terminal = json.loads(kube.exec_python(
            pod, terminal_cleanup_program(),
            timeout=remaining_timeout(evidence_deadline, 30, "terminal cleanup proof"),
        ))
        if not (terminal["supervisor_absent"] and terminal["cleanup_complete"]):
            raise ValueError("supervisor or cleanup remained after successful workload")
        before_archive = kube.exec_python(
            pod, archive_fingerprint_program(),
            timeout=remaining_timeout(evidence_deadline, 30, "archive fingerprint"),
        )
        mirror.verify_archive_fingerprint(json.loads(before_archive))
        with (OUT / "pod-control-evidence.tar").open("xb") as output:
            subprocess.run(
                kube.base + ["exec", pod, "--", "tar", "cf", "-", "-C", CONTROL, "."],
                check=True,
                timeout=remaining_timeout(evidence_deadline, 120, "success evidence export"),
                stdout=output,
                stderr=(OUT / "evidence-tar.log").open("x"),
            )
        after_archive = kube.exec_python(
            pod, archive_fingerprint_program(),
            timeout=remaining_timeout(evidence_deadline, 30, "archive stability proof"),
        )
        if before_archive != after_archive:
            raise ValueError("evidence changed during archive export")
        verify_local_archive(
            OUT / "pod-control-evidence.tar", json.loads(before_archive)
        )
        evidence_captured = True
        return result
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup = {"primary_error": None if primary_error is None else repr(primary_error)}
        cleanup_deadline = capacity["ends_at"]
        recovery_deadline = cleanup_deadline - 120
        terminal_stop_proven = False
        if vm_stream is not None and not vm_stream.closed:
            vm_stream.close()
        if workload is not None and workload.poll() is None:
            if pod_identity is not None:
                try:
                    graceful = max(0.001, remaining_timeout(
                        recovery_deadline, 165, "supervisor graceful stop"
                    ) - 15)
                    cleanup["supervisor_stop"] = json.loads(
                        kube.exec_python(
                            pod_identity["pod_name"],
                            stop_owned_supervisor_program(graceful),
                            timeout=remaining_timeout(
                                recovery_deadline, graceful + 5, "supervisor stop"
                            ),
                        )
                    )
                    if not cleanup["supervisor_stop"].get("absent"):
                        raise RuntimeError("owned supervisor did not stop")
                    terminal_stop_proven = True
                except BaseException as stop_error:
                    cleanup["supervisor_stop_error"] = repr(stop_error)
                    try:
                        cleanup["supervisor_force_stop"] = json.loads(
                            kube.exec_python(
                                pod_identity["pod_name"],
                                force_stop_supervisor_program(),
                                timeout=remaining_timeout(
                                    recovery_deadline, 15, "forced supervisor stop"
                                ),
                            )
                        )
                        terminal_stop_proven = (
                            cleanup["supervisor_force_stop"].get("absent") is True
                            and cleanup["supervisor_force_stop"].get("owned_group_absent") is True
                            and cleanup["supervisor_force_stop"].get("scratch_absent") is True
                        )
                    except BaseException as force_error:
                        cleanup["supervisor_force_stop_error"] = repr(force_error)
            workload.send_signal(2)
            try:
                workload.wait(timeout=remaining_timeout(
                    recovery_deadline, 30, "kubectl transport stop"
                ))
            except subprocess.TimeoutExpired:
                workload.kill()
                workload.wait(timeout=remaining_timeout(
                    recovery_deadline, 10, "forced kubectl transport stop"
                ))
                cleanup["forced_transport_stop"] = True
        if transport_future is not None:
            try:
                transport_future.result(timeout=remaining_timeout(
                    recovery_deadline, 30, "pending evidence transport"
                ))
            except BaseException as transport_error:
                cleanup["pending_transport_error"] = repr(transport_error)
        if transport_pool is not None:
            transport_pool.shutdown(wait=False, cancel_futures=True)
        if pod_identity is not None and not evidence_captured:
            cleanup["evidence_preserved_before_scale_down"] = False
            try:
                pod = pod_identity["pod_name"]
                terminal = json.loads(kube.exec_python(
                    pod, terminal_cleanup_program(),
                    timeout=remaining_timeout(
                        recovery_deadline, 30, "failure terminal cleanup proof"
                    ),
                ))
                if not (terminal["supervisor_absent"] and terminal["cleanup_complete"]):
                    raise ValueError("failure cleanup markers are incomplete")
                terminal_stop_proven = True
                if mirror is not None and not mirror.finalized:
                    try:
                        while "workload-exit.json" not in mirror.complete:
                            remaining_timeout(
                                recovery_deadline, 30, "failure evidence drain"
                            )
                            pull_once(
                                mirror, CONTROL,
                                lambda program: kube.exec_python(
                                    pod, program,
                                    timeout=remaining_timeout(
                                        recovery_deadline, 30,
                                        "failure evidence drain",
                                    ),
                                ),
                                now=time.monotonic,
                            )
                        failure_result = mirror.finalize(require_success=False)
                        (OUT / "transport-ledger.json").write_text(
                            json.dumps(
                                {"records": mirror.records, "result": failure_result},
                                indent=2,
                            )
                            + "\n"
                        )
                    except BaseException as transport_error:
                        cleanup["final_transport_error"] = repr(transport_error)
                before_archive = kube.exec_python(
                    pod, archive_fingerprint_program(),
                    timeout=remaining_timeout(
                        recovery_deadline, 30, "failure archive fingerprint"
                    ),
                )
                if mirror is not None:
                    mirror.verify_archive_fingerprint(json.loads(before_archive))
                with (OUT / "pod-control-failure-evidence.tar").open("xb") as output:
                    subprocess.run(
                        kube.base + ["exec", pod, "--", "tar", "cf", "-", "-C", CONTROL, "."],
                        check=True,
                        timeout=remaining_timeout(
                            recovery_deadline, 120, "failure evidence export"
                        ),
                        stdout=output,
                        stderr=(OUT / "failure-evidence-tar.log").open("x"),
                    )
                after_archive = kube.exec_python(
                    pod, archive_fingerprint_program(),
                    timeout=remaining_timeout(
                        recovery_deadline, 30, "failure archive stability proof"
                    ),
                )
                if before_archive != after_archive:
                    raise ValueError("failure evidence changed during archive export")
                verify_local_archive(
                    OUT / "pod-control-failure-evidence.tar",
                    json.loads(before_archive),
                )
                cleanup["evidence_preserved_before_scale_down"] = True
                evidence_captured = True
            except BaseException as capture_error:
                cleanup["evidence_capture_error"] = repr(capture_error)
        # Never destroy the only remaining evidence source. If export fails the
        # stopped, UID-bound Pod is retained for explicit recovery.
        cleanup_allowed = evidence_captured or pod_identity is None
        cleanup["retained_for_evidence_recovery"] = bool(
            pod_identity is not None and not evidence_captured
        )
        cleanup["terminal_stop_proven"] = terminal_stop_proven
        if pod_identity is not None:
            try:
                terminal_sample = json.loads(kube.exec_python(
                    pod_identity["pod_name"], sample_program(),
                    timeout=remaining_timeout(
                        cleanup_deadline, 15, "terminal cgroup OOM sample"
                    ),
                ))
                verify_runtime_sample(
                    terminal_sample, capacity["expected_vm_oom_kill"]
                )
                (OUT / "terminal-cgroup-sample.json").write_text(
                    json.dumps(terminal_sample, indent=2) + "\n"
                )
                cleanup["terminal_cgroup_oom_proof"] = True
            except BaseException as terminal_sample_error:
                cleanup["terminal_cgroup_oom_proof"] = False
                cleanup["terminal_cgroup_sample_error"] = repr(terminal_sample_error)
        if deployment is not None and cleanup_allowed:
            try:
                cleanup.update(
                    cleanup_deployment_and_pod(
                        kube, deployment, pod_identity, deadline=cleanup_deadline
                    )
                )
            except BaseException as runtime_cleanup_error:
                cleanup["runtime_cleanup_error"] = repr(runtime_cleanup_error)
        deletion = (
            delete_owned_objects(kube, owned_objects, deadline=cleanup_deadline)
            if cleanup_allowed
            else {"deleted": [], "errors": {"retained": "evidence recovery incomplete"}}
        )
        cleanup["owned_object_deletion"] = deletion
        cleanup["owned_objects_deleted_with_uid_preconditions"] = (
            len(deletion["deleted"]) == len(owned_objects) and not deletion["errors"]
        )
        try:
            if not cleanup_allowed:
                raise ValueError("owned Pod retained for evidence recovery")
            verify_outer_identity(kube, deadline=cleanup_deadline)
            t09a_health(
                kube, OUT / "pod-cgroup-health-after-cleanup.json",
                require_idle=True,
                deadline=cleanup_deadline,
            )
            final_vm = node_vm_sample(deadline=cleanup_deadline)
            if (
                final_vm["vm_oom_kill"] != capacity["expected_vm_oom_kill"]
                or final_vm["psi_full_avg10"] != 0
            ):
                raise ValueError("post-cleanup VM OOM/PSI guard changed")
            (OUT / "post-cleanup-vm-sample.json").write_text(
                json.dumps(final_vm, indent=2) + "\n"
            )
            cleanup["post_cleanup_vm_oom_proof"] = True
            cleanup["final_identity_and_health"] = True
        except BaseException as final_error:
            cleanup["final_identity_and_health"] = False
            cleanup["final_identity_or_health_error"] = repr(final_error)
        OUT.mkdir(exist_ok=True)
        (OUT / "outer-cleanup.json").write_text(json.dumps(cleanup, indent=2) + "\n")
        if primary_error is None and (
            cleanup.get("runtime_cleanup_error")
            or not cleanup.get("terminal_cgroup_oom_proof")
            or not cleanup.get("post_cleanup_vm_oom_proof")
            or not cleanup.get("owned_objects_deleted_with_uid_preconditions")
            or not cleanup.get("final_identity_and_health")
        ):
            raise RuntimeError("owned Pod cleanup or final health proof failed")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--offline-check", action="store_true")
    value.add_argument("--execute", action="store_true")
    value.add_argument("--owner")
    value.add_argument("--approval-reference")
    value.add_argument("--authorization-scope-sha256")
    return value


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.offline_check and not args.execute:
        print(json.dumps(offline_check(), indent=2))
        return 0
    if not args.execute:
        raise SystemExit("--execute plus a separately approved admission record required")
    if not all(
        (args.owner, args.approval_reference, args.authorization_scope_sha256)
    ):
        raise SystemExit("execution identity, approval, digest and admission are required")
    execute_window(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
