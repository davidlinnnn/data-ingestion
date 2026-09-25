"""Run AV once with an owned, read-only host-cgroup PSI observer."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

Q04 = Path(__file__).resolve().parent.parent
if str(Q04) not in sys.path:
    sys.path.insert(0, str(Q04))

from sentinel import run_process_drain_pod_cgroup_aw as runner

base, run_av, OUT, RUN_IDENTITY = runner.base, runner.main, runner.OUT, runner.RUN_IDENTITY


PROBE = Path(__file__).with_name("node_pressure_attribution.py")
PROBE_OUT = Path(str(OUT) + "-node-pressure.jsonl")
PROBE_ERR = Path(str(OUT) + "-node-pressure.stderr.log")
PROBE_CLEANUP = Path(str(OUT) + "-node-pressure-cleanup.json")
PROBE_CID = Path(str(OUT) + "-node-pressure.cid")
PROBE_NAME = "q04-host-pressure-aw-20260925"
PROBE_IMAGE = "sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48"
PROBE_SECONDS = base.WINDOW_SECONDS + base.OUTER_OBSERVATION_SECONDS + base.CLEANUP_SECONDS


def owned_probe_command(seconds=PROBE_SECONDS, run_id=RUN_IDENTITY):
    return ["docker", "run", "--rm", "--pull=never", "--network=none",
            "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--cgroupns=host", "--name", PROBE_NAME,
            "--label", "q04.run-id=" + run_id, "--cidfile", str(PROBE_CID),
            "--entrypoint=python3", "-i", PROBE_IMAGE, "-", "--seconds",
            str(seconds), "--interval", "0.25", "--run-id", run_id]


def inspect_probe(cid):
    return subprocess.run(
        ["docker", "inspect", cid, "--format",
         '{{.Id}} {{.HostConfig.CgroupnsMode}} {{index .Config.Labels "q04.run-id"}}'],
        capture_output=True, text=True, timeout=20)


def definitely_absent(check, ident):
    return check.returncode != 0 and f"no such object: {ident}" in check.stderr.lower()


def owner(action, identity=None):
    if PROBE_CID.exists():
        cid = PROBE_CID.read_text().strip()
    else:
        named = inspect_probe(PROBE_NAME)
        if named.returncode:
            if action == "verify" and definitely_absent(named, PROBE_NAME):
                return {"absent": True}
            raise RuntimeError("host observer container ID unavailable")
        cid = named.stdout.split()[0]
    if identity and identity.get("container_id") != cid:
        raise RuntimeError("host observer container identity changed")
    check = inspect_probe(cid)
    if action == "verify":
        if check.returncode == 0:
            raise RuntimeError("host observer remains active")
        if not definitely_absent(check, cid):
            raise RuntimeError("host observer absence unverified: docker inspect failed")
        return {"container_id": cid, "absent": True}
    if action != "stop":
        raise ValueError("unknown host observer action")
    if check.returncode:
        if not definitely_absent(check, cid):
            raise RuntimeError("host observer stop unverified: docker inspect failed")
        return {"container_id": cid, "already_absent": True}
    if check.stdout.strip() != f"{cid} host {RUN_IDENTITY}":
        raise RuntimeError("host observer scope or identity changed")
    subprocess.check_call(["docker", "stop", "--signal=TERM", cid],
                          stdout=subprocess.DEVNULL, timeout=20)
    return {"container_id": cid, "stop_sent": True}


def start_probe():
    if any(path.exists() for path in (PROBE_OUT, PROBE_ERR, PROBE_CLEANUP, PROBE_CID, OUT)):
        raise ValueError("AV identity or host observer output already used")
    with PROBE.open("rb") as source, PROBE_OUT.open("x") as output, PROBE_ERR.open("x") as errors:
        process = subprocess.Popen(owned_probe_command(PROBE_SECONDS, RUN_IDENTITY), stdin=source,
                                   stdout=output, stderr=errors)
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            lines = PROBE_OUT.read_text().splitlines()
            if lines:
                identity = json.loads(lines[0])
                if (identity.get("kind") != "start" or identity.get("run_id") != RUN_IDENTITY
                        or identity.get("cgroup_count", 0) < 100
                        or identity.get("pid") != 1
                        or identity.get("start_ticks", 0) < 1):
                    raise ValueError("host observer start identity invalid")
                if not PROBE_CID.exists():
                    raise ValueError("host observer container ID missing")
                identity["container_id"] = PROBE_CID.read_text().strip()
                check = inspect_probe(identity["container_id"])
                if (check.returncode or check.stdout.strip() !=
                        f"{identity['container_id']} host {RUN_IDENTITY}"):
                    raise ValueError("host observer scope or identity invalid")
                return process, identity
            if process.poll() is not None:
                raise RuntimeError("node observer exited before start identity")
            time.sleep(.05)
        raise TimeoutError("node observer start identity missing")
    except BaseException:
        stop_probe(process, None, require_end=False)
        raise


def stop_probe(process, identity, *, require_end=True):
    outcome = {}
    def attempt(name, operation):
        try:
            outcome[name] = {"ok": True, "value": operation()}
        except BaseException as error:
            outcome[name] = {"ok": False, "type": type(error).__name__,
                             "reason": str(error)}

    def settle_transport():
        try:
            return {"exit_code": process.wait(timeout=20), "forced": False}
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            raise RuntimeError("node observer transport required forced stop")

    attempt("remote_stop", lambda: owner("stop", identity))
    attempt("transport", settle_transport)
    attempt("remote_absence", lambda: owner("verify", identity))
    def terminal():
        lines = PROBE_OUT.read_text().splitlines()
        end = json.loads(lines[-1]) if lines else None
        if require_end and (not end or end.get("kind") != "end"
                            or end.get("time", 0) < identity["time"]):
            raise ValueError("node observer terminal marker missing")
        samples = [json.loads(line) for line in lines[1:-1]]
        if require_end and (not samples or any(
                sample.get("kind") != "sample"
                or sample["ended_at"] - sample["started_at"] > 1
                or sample["node_full_delta_us"] < 0
                for sample in samples)
                or samples[0]["started_at"] != identity["time"]
                or samples[-1]["ended_at"] != end["time"]
                or any(later["started_at"] != earlier["ended_at"]
                       for earlier, later in zip(samples, samples[1:]))):
            raise ValueError("node observer sample coverage incomplete")
        return {"end": end, "samples": len(samples),
                "max_gap_seconds": max((sample["ended_at"] - sample["started_at"]
                                        for sample in samples), default=None)}
    attempt("terminal", terminal)
    outcome["complete"] = (
        all(item["ok"] for item in outcome.values())
        and outcome["transport"]["value"]["exit_code"] == 0
    )
    PROBE_CLEANUP.write_text(json.dumps(outcome, indent=2) + "\n")
    if not outcome["complete"]:
        raise RuntimeError("node observer cleanup or terminal evidence incomplete")
    return outcome


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = base.parser().parse_args(argv)
    if not args.execute:
        return run_av(argv)
    base.offline_check()
    if (not args.owner or not args.approval_reference
            or args.authorization_scope_sha256 != base.authorization_scope_sha256()):
        raise ValueError("AV execution authorization scope changed")
    process = None
    identity = None
    stop_monitor = threading.Event()
    primary = None
    result = 1
    try:
        process, identity = start_probe()
        def monitor():
            while not stop_monitor.wait(.2):
                if process.poll() is not None:
                    os.kill(os.getpid(), signal.SIGINT)
                    return
        threading.Thread(target=monitor, daemon=True).start()
        result = run_av(argv)
    except BaseException as error:
        primary = error
    finally:
        stop_monitor.set()
        if process is not None:
            try:
                stop_probe(process, identity)
            except BaseException as error:
                if primary is None:
                    primary = error
                else:
                    primary = RuntimeError(f"{primary!r}; node observer cleanup: {error!r}")
    if primary is not None:
        raise primary
    return result


if __name__ == "__main__":
    raise SystemExit(main())
