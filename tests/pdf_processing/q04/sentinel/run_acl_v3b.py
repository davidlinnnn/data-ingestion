"""Post-Docker-restart 25-minute ACL fixture 09 runner with outer admission v3-b."""

import argparse
import fcntl
import hashlib
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
REMOTE = "/tmp/q04-keynote-18be1b3-20260916-b"
PREFIX = "q04/keynote-18be1b3-20260916-b/"
PHASE = "acl-window-v3-b"
OUT = Path("/private/tmp/q04-acl-window-20260917-v3-b")
CAPACITY = REMOTE + "/capacity-acl-window-v3-b.json"
RESERVATION = REMOTE + "/reservation-acl-window-v3-b.json"
RELEASE = REMOTE + "/release-reservation-acl-window-v3-b"
ADMISSION_EVIDENCE = REMOTE + "/pre-admission-acl-window-v3-b.jsonl"
ADMISSION_RESULT = REMOTE + "/admission-acl-window-v3-b.json"
RUNNER_DIR = REMOTE + "/runner-acl-window-v3-b"
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
    "b729891aa381ae25eef6ec2fbceefcdb43703d441762eafbb388627792833297"
)
EXPECTED_STATE_SHA256 = (
    "6f83b29e73357e6576643948f18f0be2d461ae7285e433f2c810c5f8d4aca5b7"
)
RUN_ID = "q04-7b4f958ff3ac4e2da5b54dcaa66914b9"
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
    "fixture": "09",
    "modes": ["fresh", "restored", "replay"],
}


def build_probe_expectation(bundle):
    """Bind the read-only probe to the restored Q04 producer and bundle."""
    return {
        "profile": bundle["base_profile"],
        "producer": bundle["producer"],
        "run_root": REMOTE,
        "prefix": PREFIX,
        "producer_roots": [
            "/app/pdf_processing",
            REMOTE + "/code/src/pdf_processing",
        ],
        "profile_path": REMOTE + "/inputs/inputs.json",
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
    """Pin the reviewed restored bundle and complete frozen config."""
    if (
        frozen.get("bundle_sha256_config") != EXPECTED_BUNDLE_SHA256
        or frozen.get("bundle_sha256_actual") != EXPECTED_BUNDLE_SHA256
    ):
        raise ValueError("frozen bundle hash changed")
    if frozen.get("state_sha256") != EXPECTED_STATE_SHA256:
        raise ValueError("frozen state hash changed")
    if not frozen.get("producer_matches") or not frozen.get("profile_matches"):
        raise ValueError("frozen producer or profile changed")
    if not frozen.get("keynote_complete"):
        raise ValueError("frozen Keynote evidence is incomplete")


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
    ]


def build_runtime_command(
    *,
    remote=REMOTE,
    capacity=CAPACITY,
    python=PYTHON,
    timeout_program="timeout",
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
            + " --phase matrix --fixture 09"
            + ' --bundle "$R/inputs" --state "$R/state"'
            + " --capacity "
            + shlex.quote(capacity)
            + " --name acl-window-v3-b --trial-seconds 180 --capacity-approved",
        )
    )
    return "\n".join(
        (
            "set -euC",
            "export R=" + shlex.quote(remote),
            "export PYTHONDONTWRITEBYTECODE=1 PYTHONSAFEPATH=1 "
            "HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4",
            'export PYTHONPATH="$R/runner-acl-window-v3-b:$R/code/src:'
            '$R/code/tests/pdf_processing/q04:$R/code/tests/pdf_processing/q02:'
            '$R/code/tests/pdf_processing/q03"',
            'export PDF_QUALIFICATION_LOCK="$R/acl-window-v3-b.driver.lock"',
            'cd "$R/code"',
            'test ! -e "$R/state/acl-window-v3-b"',
            shlex.quote(timeout_program)
            + " --signal=INT --kill-after=180s 825s sh -eu -c "
            + shlex.quote(inner)
            + ' > "$R/logs/acl-window-v3-b.log" 2>&1',
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
    bundle = json.loads(Path("/private/tmp/q04-inputs-local-v5/inputs.json").read_text())
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
    frozen_producer = REMOTE + "/code/src/pdf_processing"
    assert not inventory["producer_differences"][frozen_producer]
    assert inventory["retained_profile"]["method_matches"]
    assert inventory["retained_profile"]["path"] == REMOTE + "/inputs/inputs.json"
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
 'producer_matches':config['producer']==bundle['producer'],'profile_matches':config['profiles']['09']['method']==bundle['base_profile']['method'],
 'state_sha256':sha(root/'state/config.json'),'keynote_complete':(root/'state/keynote-window-2/phase-complete.json').exists(),
 'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'pid1_start_ticks':start_ticks(1),
 'vm_oom_kill':fields('/proc/vmstat')['oom_kill'],'cgroup_oom_kill':events['oom_kill'],
 'qualification_lock_held':lock_held,
 'phase_absent':not (root/'state/PHASE').exists(),'capacity_absent':not Path(CAPACITY).exists(),
 'log_absent':not (root/'logs/PHASE.log').exists(),'reservation_absent':not Path(RESERVATION).exists(),
 'release_absent':not Path(RELEASE).exists(),'admission_absent':not Path(ADMISSION).exists(),
 'admission_result_absent':not Path(ADMISSION_RESULT).exists(),
 'runner_absent':not Path(RUNNER).exists()}
print(json.dumps(value))
""".replace("ROOT", repr(REMOTE)).replace("PHASE", PHASE).replace(
        "CAPACITY", repr(CAPACITY)
    ).replace("RESERVATION", repr(RESERVATION)).replace("RELEASE", repr(RELEASE)).replace(
        "ADMISSION_RESULT", repr(ADMISSION_RESULT)
    ).replace("ADMISSION", repr(ADMISSION_EVIDENCE)).replace(
        "RUNNER", repr(RUNNER_DIR)
    )
    frozen = json.loads(remote(script, timeout=120))
    (OUT / "frozen-precheck.json").write_text(json.dumps(frozen, indent=2) + "\n")
    assert frozen["run_id"] == RUN_ID and frozen["prefix"] == PREFIX
    assert frozen["bundle"] == REMOTE + "/inputs"
    validate_frozen_artifacts(frozen)
    validate_remote_baseline(frozen)
    for field in (
        "phase_absent",
        "capacity_absent",
        "log_absent",
        "reservation_absent",
        "release_absent",
        "admission_absent",
        "admission_result_absent",
        "runner_absent",
    ):
        assert frozen[field], field
    return frozen


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
                "--exclude=./state/keynote-window-2",
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
    frozen = None
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a+") as local_lock:
        fcntl.flock(local_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = deployment_snapshot()
        (OUT / "held-services-before.json").write_text(json.dumps(before, indent=2) + "\n")
        assert_candidate_pods_absent()
        t09a_health("health-before.json")
        frozen = frozen_precheck()
        reservation_token = uuid.uuid4().hex
        holder_script = """import fcntl,json,os
from pathlib import Path
def start_ticks(pid):
 text=Path('/proc')/str(pid)/'stat';value=text.read_text();fields=value[value.rfind(')')+1:].split();return int(fields[19])
with open('/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 pid=os.getpid()
 lock_identity=os.fstat(lock.fileno())
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
            BASE
            + ["-n", NS, "exec", "-i", "coordinator", "--", "env", "PYTHONDONTWRITEBYTECODE=1", PYTHON, "-"],
            stdin=subprocess.PIPE,
            stdout=holder_log,
            stderr=subprocess.STDOUT,
        )
        assert holder.stdin is not None
        holder.stdin.write(holder_script.encode())
        holder.stdin.close()
        try:
            for _ in range(30):
                assert holder.poll() is None, "reservation holder failed"
                if remote("from pathlib import Path\nprint(Path(" + repr(RESERVATION) + ").exists())\n").strip() == b"True":
                    acquired = True
                    break
                time.sleep(0.2)
            assert acquired
            runner_manifest = stage_admission_runner()
            (OUT / "runner-manifest.json").write_text(
                json.dumps(runner_manifest, indent=2, sort_keys=True) + "\n"
            )
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
                minimum_work_seconds=WORKLOAD_SECONDS,
                cleanup_seconds=CLEANUP_SECONDS,
                expected_vm_oom_kill=EXPECTED_VM_OOM_KILL,
                frozen_state_sha256=frozen["state_sha256"],
                runner_manifest=runner_manifest,
            )
            STATE["phase"] = "admission"
            save()
            admission_argv = build_admission_argv(reservation_token)
            admission_program = (
                "import runpy,sys\n"
                + "sys.path[:0]="
                + repr(
                    [
                        RUNNER_DIR,
                        REMOTE + "/code/src",
                        REMOTE + "/code/tests/pdf_processing/q04",
                    ]
                )
                + "\nsys.argv="
                + repr(admission_argv)
                + "\nrunpy.run_path(sys.argv[0],run_name='__main__')\n"
            )

            def admit():
                result = json.loads(remote(admission_program, timeout=200))
                (OUT / "admission-v3.json").write_text(
                    json.dumps(result, indent=2, sort_keys=True) + "\n"
                )
                return result

            def launch():
                STATE["phase"] = "running-acl"
                save()
                require_launch_budget(lease_ends_monotonic)
                if holder.poll() is not None:
                    raise RuntimeError("reservation transport lost before runtime launch")
                return subprocess.Popen(
                    BASE
                    + [
                        "-n",
                        NS,
                        "exec",
                        "coordinator",
                        "--",
                        "sh",
                        "-c",
                        build_runtime_command(),
                    ],
                    stdout=(OUT / "runtime-transport.log").open("x"),
                    stderr=subprocess.STDOUT,
                )

            admission_result, driver = launch_after_admission(
                admit,
                launch,
                lease_ends_monotonic=lease_ends_monotonic,
            )
            STATE["outer_admission"] = admission_result
            while driver.poll() is None:
                assert holder.poll() is None, "reservation transport lost"
                if time.monotonic() >= lease_ends_monotonic - CLEANUP_SECONDS:
                    driver.send_signal(signal.SIGINT)
                    try:
                        driver.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        driver.terminate()
                    raise TimeoutError("work window ended; enter cleanup")
                time.sleep(1)
            STATE["runtime_returncode"] = driver.returncode
            assert driver.returncode == 0, "ACL driver failed; retain logs, no retry"
            STATE["sentinel_passed"] = True
        except BaseException as error:
            STATE["errors"].append({"type": type(error).__name__, "reason": str(error)})
            STATE["phase"] = "failed"
            save()
        finally:
            if acquired:
                STATE["phase"] = "cleanup"
                save()
                try:
                    cleanup_script = (REPO / "tests/pdf_processing/q04/sentinel/cleanup.py").read_text()
                    cleanup_raw = remote(
                        cleanup_script + "\nasyncio.run(main(" + repr(REMOTE) + "))\n", timeout=180
                    )
                    (OUT / "cleanup.json").write_bytes(cleanup_raw)
                    cleanup_result = json.loads(cleanup_raw)
                    STATE["cleanup_verified"] = not cleanup_result["errors"]
                    if cleanup_result["errors"]:
                        STATE["errors"].append({"cleanup_required_intervention": cleanup_result["errors"]})
                        STATE["sentinel_passed"] = False
                except BaseException as error:
                    STATE["errors"].append({"cleanup": str(error)})
                    STATE["cleanup_verified"] = False
                    save()
                try:
                    post = json.loads(
                        remote(
                            "import hashlib,json\nfrom pathlib import Path\nr=Path("
                            + repr(REMOTE)
                            + ")\nsha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()\nprint(json.dumps({'state_sha256':sha(r/'state/config.json'),'phase_complete':(r/'state/"
                            + PHASE
                            + "/phase-complete.json').exists()}))\n"
                        )
                    )
                    assert post["state_sha256"] == frozen["state_sha256"]
                    (OUT / "frozen-postcheck.json").write_text(json.dumps(post, indent=2) + "\n")
                    STATE["frozen_state_unchanged"] = True
                except BaseException as error:
                    STATE["errors"].append({"frozen-postcheck": str(error)})
                try:
                    capture()
                    STATE["evidence_captured"] = True
                    STATE["evidence_sha256"] = hashlib.sha256((OUT / "remote-evidence.tar").read_bytes()).hexdigest()
                    STATE["evidence_bytes"] = (OUT / "remote-evidence.tar").stat().st_size
                except BaseException as error:
                    STATE["errors"].append({"capture": str(error)})
                    save()
                try:
                    after = deployment_snapshot()
                    assert_candidate_pods_absent()
                    (OUT / "held-services-after.json").write_text(json.dumps(after, indent=2) + "\n")
                    t09a_health("health-after.json")
                    STATE["services_held_closed"] = True
                except BaseException as error:
                    STATE["errors"].append({"held-service-verification": str(error)})
                    STATE["services_held_closed"] = False
                    save()
                try:
                    write_remote(RELEASE, b"complete\n")
                    holder.wait(timeout=10)
                    assert holder.returncode == 0
                    STATE["reservation_released"] = True
                except BaseException as error:
                    STATE["errors"].append({"reservation-release": str(error)})
                STATE["finished"] = time.time()
                STATE["phase"] = "complete" if not STATE["errors"] else "needs-review"
                save()
        if holder_log is not None:
            holder_log.close()
    return 0 if not STATE["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
