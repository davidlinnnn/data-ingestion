"""One authorized ACL fixture 09 window reusing the accepted frozen Q04 run."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


REPO = Path(__file__).resolve().parents[4]
OUT = Path("/private/tmp/q04-acl-window-20260916-c")
REMOTE = "/tmp/q04-keynote-18be1b3-20260916-b"
PREFIX = "q04/keynote-18be1b3-20260916-b/"
PHASE = "acl-window-3"
CAPACITY = REMOTE + "/capacity-acl-20260916-c.json"
RESERVATION = REMOTE + "/reservation-acl-window-3.json"
RELEASE = REMOTE + "/release-reservation-acl-window-3"
PYTHON = "/experiment/.venv/bin/python"
NS = "pdf-t09a-validation"
CONTEXT = "kind-internal-a2a-vs6-local"
COORDINATOR_UID = "39c4bf45-45ae-4646-8d7b-ec47b2c61785"
RUN_ID = "q04-7b4f958ff3ac4e2da5b54dcaa66914b9"
BASE = ["kubectl", "--context", CONTEXT, "--request-timeout=15s"]
TARGET = int(4.5 * 1024**3)
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
    uid = k(NS, "get", "pod", "coordinator", "-o", "jsonpath={.metadata.uid}").decode()
    assert uid == COORDINATOR_UID
    runtime_probe = (REPO / "tests/pdf_processing/q04/preflight/remote_probe.py").read_text()
    bundle = json.loads(Path("/private/tmp/q04-inputs-local-v5/inputs.json").read_text())
    expected = {
        "profile": bundle["base_profile"],
        "producer": bundle["producer"],
        "run_root": REMOTE,
        "prefix": PREFIX,
    }
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
    script = """import hashlib,json,sys
from pathlib import Path
root=Path(ROOT)
sys.path[:0]=[str(root/'code/src'),str(root/'code/tests/pdf_processing/q04'),str(root/'code/tests/pdf_processing/q02'),str(root/'code/tests/pdf_processing/q03')]
from prepare import verify_bundle
bundle=verify_bundle(root/'inputs')
config=json.loads((root/'state/config.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
value={'run_id':config['run_id'],'prefix':config['prefix'],'bundle':config['bundle'],
 'bundle_sha256_config':config['bundle_sha256'],'bundle_sha256_actual':sha(root/'inputs/inputs.json'),
 'producer_matches':config['producer']==bundle['producer'],'profile_matches':config['profiles']['09']['method']==bundle['base_profile']['method'],
 'state_sha256':sha(root/'state/config.json'),'keynote_complete':(root/'state/keynote-window-2/phase-complete.json').exists(),
 'phase_absent':not (root/'state/PHASE').exists(),'capacity_absent':not Path(CAPACITY).exists(),
 'log_absent':not (root/'logs/PHASE.log').exists(),'reservation_absent':not Path(RESERVATION).exists(),
 'release_absent':not Path(RELEASE).exists()}
print(json.dumps(value))
""".replace("ROOT", repr(REMOTE)).replace("PHASE", PHASE).replace(
        "CAPACITY", repr(CAPACITY)
    ).replace("RESERVATION", repr(RESERVATION)).replace("RELEASE", repr(RELEASE))
    frozen = json.loads(remote(script, timeout=120))
    (OUT / "frozen-precheck.json").write_text(json.dumps(frozen, indent=2) + "\n")
    assert frozen["run_id"] == RUN_ID and frozen["prefix"] == PREFIX
    assert frozen["bundle"] == REMOTE + "/inputs"
    assert frozen["bundle_sha256_config"] == frozen["bundle_sha256_actual"]
    assert frozen["producer_matches"] and frozen["profile_matches"]
    assert frozen["keynote_complete"]
    for field in ("phase_absent", "capacity_absent", "log_absent", "reservation_absent", "release_absent"):
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


def main():
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
        holder_script = """import fcntl,json,time,os,psutil
from pathlib import Path
root=Path(ROOT)
with open('/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 Path(RESERVATION).open('x').write(json.dumps({'pid':os.getpid(),'created':psutil.Process().create_time(),'acquired':time.time()}))
 while not Path(RELEASE).exists():time.sleep(.5)
""".replace("ROOT", repr(REMOTE)).replace("RESERVATION", repr(RESERVATION)).replace(
            "RELEASE", repr(RELEASE)
        )
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
            start = time.time()
            capacity = json.loads(
                (REPO / "tests/pdf_processing/q04/preflight/capacity.draft.json").read_text()
            )
            capacity.update(
                status="AUTHORIZED",
                owner="Q04 capacity/cleanup owner in task 01a0aa2d-e84d-71c2-9bed-42ff7d40b114",
                approval_reference="Direct user authorization on 2026-09-16: one 20-minute process-mode ACL fixture 09 fresh/restored/replay window; main-held 32 Deployments remain closed; 4.5GiB outer admission; no retry; final 5 minutes cleanup",
                starts_at=start,
                ends_at=start + 1200,
            )
            (OUT / "capacity.json").write_text(json.dumps(capacity, indent=2) + "\n")
            write_remote(CAPACITY, json.dumps(capacity).encode())
            STATE.update(
                started=start,
                ends_at=start + 1200,
                work_ends_at=start + 900,
                reservation=True,
                outer_admission_available_bytes=TARGET,
                frozen_state_sha256=frozen["state_sha256"],
            )
            STATE["phase"] = "admission"
            save()
            admission = """import sys,json,time
from pathlib import Path
sys.path[:0]=[ROOT+'/code/src',ROOT+'/code/tests/pdf_processing/q04']
from telemetry import sample,check_sample
from contracts import validate_window
limits=json.loads(Path(CAPACITY).read_text());rows=[];initial=sample()
assert initial['vm_oom_kill']==28,'OOM baseline changed'
with Path(ADMISSION).open('x') as stream:
 for i in range(61):
  row=sample();rows.append(row);stream.write(json.dumps(row)+'\\n');stream.flush();validate_window(limits,time.time());check_sample(row,initial,limits)
  assert row['available']>=TARGET and row['psi_full_avg10']==0,'4.5GiB capacity admission rejected'
  if i<60:time.sleep(1)
print(json.dumps({'minimum_available':min(r['available'] for r in rows),'maximum_cgroup':max(r['memory_current'] for r in rows),'maximum_psi':max(r['psi_full_avg10'] for r in rows),'oom_values':sorted(set(r['vm_oom_kill'] for r in rows)),'samples':len(rows)}))
""".replace("ROOT", repr(REMOTE)).replace("CAPACITY", repr(CAPACITY)).replace(
                "ADMISSION", repr(REMOTE + "/pre-admission-acl-4.5gib.jsonl")
            ).replace("TARGET", str(TARGET))
            admission_result = json.loads(remote(admission, timeout=80))
            (OUT / "admission-4.5gib.json").write_text(
                json.dumps(admission_result, indent=2) + "\n"
            )
            STATE["phase"] = "running-acl"
            save()
            command = """set -euC
R=ROOT
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4
export PYTHONPATH="$R/code/src:$R/code/tests/pdf_processing/q04:$R/code/tests/pdf_processing/q02:$R/code/tests/pdf_processing/q03"
export PDF_QUALIFICATION_LOCK="$R/acl-window-3.driver.lock"
cd "$R/code"
test ! -e "$R/state/acl-window-3"
/experiment/.venv/bin/python -c "from prepare import verify_bundle;from pathlib import Path;verify_bundle(Path('$R/inputs'))"
timeout --signal=INT --kill-after=180s 825s /experiment/.venv/bin/python tests/pdf_processing/q04/q04_runtime.py --phase matrix --fixture 09 --bundle "$R/inputs" --state "$R/state" --capacity CAPACITY --name acl-window-3 --trial-seconds 180 --capacity-approved > "$R/logs/acl-window-3.log" 2>&1
""".replace("ROOT", REMOTE).replace("CAPACITY", CAPACITY)
            driver = subprocess.Popen(
                BASE + ["-n", NS, "exec", "coordinator", "--", "sh", "-c", command],
                stdout=(OUT / "runtime-transport.log").open("x"),
                stderr=subprocess.STDOUT,
            )
            while driver.poll() is None:
                assert holder.poll() is None, "reservation transport lost"
                if time.time() >= start + 900:
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
