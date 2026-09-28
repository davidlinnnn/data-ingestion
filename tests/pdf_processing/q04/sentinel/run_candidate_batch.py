"""Run the reviewed six-fixture candidate matrix serially and stop on failure."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from sentinel import run_yolo_lifecycle_a as engine
from sentinel.run_candidate_matrix_phase import (
    MANIFEST,
    REPO,
    load_manifest,
    require_reviewed_git_state,
)


BATCH_OUT = Path("/private/tmp/q04-candidate-batch-20260919-a")
PROJECT_PYTHON = Path(
    "/Users/david/work/data-ingestion/docs/prototypes/"
    "pdf-checkpoint-prototype/.venv/bin/python"
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def build_phase_argv(phase, *, owner, approval_reference):
    if phase["fixture"] == "07":
        script = REPO / "tests/pdf_processing/q04/sentinel/run_yolo_lifecycle_a.py"
        extra = []
    else:
        script = REPO / "tests/pdf_processing/q04/sentinel/run_candidate_matrix_phase.py"
        extra = ["--phase-key", phase["key"]]
    return [
        str(PROJECT_PYTHON), str(script), *extra, "--execute",
        "--owner", owner, "--approval-reference", approval_reference,
    ]


def fixed_environment():
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(REPO), str(REPO / "src"), str(REPO / "tests/pdf_processing/q04"))
    )
    return environment


def read_state(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def validate_phase_result(phase):
    state_path = Path(phase["local_output"]) / "lease-state.json"
    state = read_state(state_path)
    require(state is not None, phase["key"] + " final lease state is absent")
    require(state.get("phase") == "complete", phase["key"] + " did not complete")
    require(state.get("errors") == [], phase["key"] + " retained errors")
    require(state.get("acceptance_passed") is True,
            phase["key"] + " acceptance did not pass")
    require(state.get("cleanup_verified") is True,
            phase["key"] + " cleanup was not verified")
    require(state.get("services_held_closed") is True,
            phase["key"] + " changed held Deployments")
    require(state.get("reservation_released") is True,
            phase["key"] + " reservation was not released")
    return state


def stop_with_cleanup(process, cleanup_grace_seconds):
    cooperative_seconds = min(30, cleanup_grace_seconds)
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGINT)
    try:
        return process.wait(timeout=cooperative_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        raise TimeoutError("phase cleanup grace expired after outer stop")


def kubectl_python(program, *, timeout):
    return subprocess.check_output(
        engine.BASE
        + [
            "-n", engine.NS, "exec", "-i", "coordinator", "--", "env",
            "PYTHONDONTWRITEBYTECODE=1", engine.PYTHON, "-",
        ],
        input=program.encode(), timeout=timeout,
    )


def reservation_release_program(phase, identity):
    return """import fcntl,json,os,signal,time
from pathlib import Path
reservation=Path(RESERVATION);release=Path(RELEASE);expected=EXPECTED
def ticks(pid):
 path=Path('/proc')/str(pid)/'stat'
 if not path.exists():return None
 value=path.read_text();return int(value[value.rfind(')')+1:].split()[19])
if not reservation.exists():raise RuntimeError('owned reservation evidence absent')
observed=json.loads(reservation.read_text())
if observed!=expected:raise RuntimeError('reservation identity mismatch')
if not release.exists():release.open('x').write('release')
pid=expected['pid'];deadline=time.monotonic()+30
while ticks(pid)==expected['start_ticks'] and time.monotonic()<deadline:time.sleep(.2)
if ticks(pid)==expected['start_ticks']:
 os.kill(pid,signal.SIGTERM);deadline=time.monotonic()+5
 while ticks(pid)==expected['start_ticks'] and time.monotonic()<deadline:time.sleep(.1)
if ticks(pid)==expected['start_ticks']:
 os.kill(pid,signal.SIGKILL);deadline=time.monotonic()+5
 while ticks(pid)==expected['start_ticks'] and time.monotonic()<deadline:time.sleep(.1)
if ticks(pid)==expected['start_ticks']:raise RuntimeError('owned reservation process survived')
reservation.unlink(missing_ok=True);release.unlink(missing_ok=True)
with open('/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
print(json.dumps({'reservation_released':True,'identity':expected},sort_keys=True))
""".replace("RESERVATION", repr(phase["reservation"])).replace(
        "RELEASE", repr(phase["release"])
    ).replace("EXPECTED", repr(identity))


def owned_remote_guard_program(phase, token, retained_identity, *, emit):
    program = """import json
from pathlib import Path
root=Path(ROOT);expected_claim={'phase':PHASE,'token':TOKEN}
claim_path=root/'setup-claim.json'
if not claim_path.exists():raise RuntimeError('owned setup claim absent')
claim=json.loads(claim_path.read_text())
if claim!=expected_claim:raise RuntimeError('setup claim identity mismatch')
reservation=Path(RESERVATION)
identity=None if not reservation.exists() else json.loads(reservation.read_text())
if identity is not None:
 if identity.get('token')!=TOKEN:raise RuntimeError('reservation token mismatch')
 if identity.get('phase')!=PHASE:raise RuntimeError('reservation phase mismatch')
 if identity.get('coordinator_uid')!=COORDINATOR_UID:raise RuntimeError('reservation coordinator identity mismatch')
 if RETAINED is not None and identity!=RETAINED:raise RuntimeError('retained reservation identity mismatch')
elif RETAINED is not None:raise RuntimeError('retained reservation disappeared')
EMIT
""".replace("EMIT", (
        "print(json.dumps({'claim':claim,'reservation':identity},sort_keys=True))"
        if emit else ""
    )).replace("ROOT", repr(phase["remote_root"])).replace(
        "PHASE", repr(phase["phase"])
    ).replace("TOKEN", repr(token)).replace(
        "RESERVATION", repr(phase["reservation"])
    ).replace("COORDINATOR_UID", repr(engine.COORDINATOR_UID)).replace(
        "RETAINED", repr(retained_identity)
    )
    return program


def validate_owned_remote(phase, token, retained_identity):
    """Fence the setup claim and reservation before any remote mutation."""
    program = owned_remote_guard_program(
        phase, token, retained_identity, emit=True
    )
    result = json.loads(kubectl_python(program, timeout=15))
    require(result["claim"] == {"phase": phase["phase"], "token": token},
            "setup claim identity mismatch")
    identity = result["reservation"]
    if identity is None:
        return None
    require(identity.get("token") == token, "reservation token mismatch")
    require(identity.get("phase") == phase["phase"], "reservation phase mismatch")
    require(identity.get("coordinator_uid") == engine.COORDINATOR_UID,
            "reservation coordinator identity mismatch")
    return identity


def verify_qualification_lock_free():
    program = """import fcntl,json
with open('/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 print(json.dumps({'qualification_lock_free':True}))
"""
    result = json.loads(kubectl_python(program, timeout=15))
    require(result == {"qualification_lock_free": True},
            "qualification lock remains held")
    return result


def emergency_cleanup(phase, reviewed_cleanup_sha256):
    """Clean only the active phase and release only its recorded reservation."""
    state = read_state(Path(phase["local_output"]) / "lease-state.json") or {}
    require(state.get("remote_claimed") is True, "phase has no claimed remote root")
    token = state.get("reservation_token")
    require(token, "owned reservation token unavailable")
    identity = validate_owned_remote(
        phase, token, state.get("reservation_identity")
    )
    cleanup_path = REPO / "tests/pdf_processing/q04/sentinel/cleanup.py"
    cleanup_source = cleanup_path.read_bytes()
    require(
        hashlib.sha256(cleanup_source).hexdigest() == reviewed_cleanup_sha256,
        "reviewed emergency cleanup source changed",
    )
    driver_name = (
        "yolo_candidate_window.py"
        if phase["fixture"] == "07"
        else "candidate_matrix_window.py"
    )
    controller_scripts = (
        "q04/q04_runtime.py",
        Path(phase["runner_dir"]).name + "/" + driver_name,
    )
    cleanup_program = owned_remote_guard_program(
        phase, token, state.get("reservation_identity"), emit=False
    ) + cleanup_source.decode() + "\nasyncio.run(main(" + repr(
        phase["remote_root"]
    ) + ", controller_scripts=" + repr(controller_scripts) + ", current_phase=" + repr(
        phase["phase"]
    ) + "))\n"
    errors = []
    cleanup = None
    try:
        cleanup = json.loads(kubectl_python(cleanup_program, timeout=180))
        if cleanup.get("errors"):
            errors.append({"cleanup": cleanup["errors"]})
    except BaseException as error:
        errors.append({"cleanup": str(error)})
    released = {"reservation_released": True, "identity": None}
    if identity is not None:
        try:
            released = json.loads(
                kubectl_python(reservation_release_program(phase, identity), timeout=40)
            )
        except BaseException as error:
            errors.append({"reservation": str(error)})
    else:
        try:
            released["lock"] = verify_qualification_lock_free()
        except BaseException as error:
            errors.append({"reservation": str(error)})
    evidence = {"cleanup": cleanup, "reservation": released, "errors": errors}
    (BATCH_OUT / ("emergency-cleanup-" + phase["key"] + ".json")).write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    )
    require(not errors, "identity-fenced emergency cleanup failed")
    return evidence


def phase_is_settled(phase):
    state = read_state(Path(phase["local_output"]) / "lease-state.json") or {}
    if state.get("remote_claimed") is not True:
        return True
    return (
        state.get("cleanup_verified") is True
        and state.get("reservation_released") is True
        and state.get("services_held_closed") is True
    )


def settle_phase_process(process, phase, reviewed_cleanup_sha256):
    stop_error = None
    if process.poll() is None:
        try:
            stop_with_cleanup(process, phase["outer_cleanup_grace_seconds"])
        except BaseException as error:
            stop_error = error
    if not phase_is_settled(phase):
        emergency_cleanup(phase, reviewed_cleanup_sha256)
    if stop_error is not None:
        raise stop_error


def run_phase(
    phase, *, owner, approval_reference, reviewed_cleanup_sha256,
    monotonic=time.monotonic,
):
    output = Path(phase["local_output"])
    require(not output.exists(), phase["key"] + " local output already exists")
    argv = build_phase_argv(
        phase, owner=owner, approval_reference=approval_reference
    )
    process = subprocess.Popen(
        argv, cwd=REPO, env=fixed_environment(), start_new_session=True
    )
    prelease_deadline = monotonic() + phase["prelease_seconds"]
    lease_deadline = None
    state_path = output / "lease-state.json"
    try:
        while process.poll() is None:
            state = read_state(state_path)
            if state and "started_monotonic" in state:
                observed = float(state["started_monotonic"])
                lease_deadline = observed + phase["window_seconds"]
            now = monotonic()
            if lease_deadline is None and now >= prelease_deadline:
                raise TimeoutError(phase["key"] + " prelease deadline expired")
            if lease_deadline is not None and now >= lease_deadline:
                raise TimeoutError(phase["key"] + " wall-clock lease expired")
            time.sleep(0.5)
        require(process.returncode == 0, phase["key"] + " failed; batch stopped")
        return validate_phase_result(phase)
    except BaseException:
        settle_phase_process(process, phase, reviewed_cleanup_sha256)
        raise


def save_batch_state(state):
    (BATCH_OUT / "batch-state.json").write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n"
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
    manifest = load_manifest(MANIFEST)
    require_reviewed_git_state(manifest)
    require(not BATCH_OUT.exists(), "batch output identity already exists")
    BATCH_OUT.mkdir()
    state = {
        "phase": "running", "manifest": str(MANIFEST), "completed": [],
        "failed": None, "automatic_retry": False,
        "started": time.time(), "runtime_authorized_by_manifest": False,
    }
    save_batch_state(state)
    try:
        reviewed_cleanup_sha256 = manifest["runner_source_sha256"][
            "tests/pdf_processing/q04/sentinel/cleanup.py"
        ]
        for phase in manifest["phases"]:
            result = run_phase(
                phase, owner=args.owner, approval_reference=args.approval_reference,
                reviewed_cleanup_sha256=reviewed_cleanup_sha256,
            )
            state["completed"].append(
                {"key": phase["key"], "fixture": phase["fixture"],
                 "finished": result["finished"]}
            )
            save_batch_state(state)
    except BaseException as error:
        state["phase"] = "stopped"
        state["failed"] = {"type": type(error).__name__, "reason": str(error)}
        state["finished"] = time.time()
        save_batch_state(state)
        raise
    state["phase"] = "complete"
    state["finished"] = time.time()
    save_batch_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
