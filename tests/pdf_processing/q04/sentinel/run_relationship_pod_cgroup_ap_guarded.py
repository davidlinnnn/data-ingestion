"""Run AP once with an owned, read-only kind-node PSI observer."""

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

from sentinel import run_relationship_pod_cgroup_ap as runner

base, run_ap, OUT, RUN_IDENTITY = runner.base, runner.main, runner.OUT, runner.RUN_IDENTITY


NODE = base.NODE
PROBE = Path(__file__).with_name("node_pressure_attribution.py")
PROBE_OUT = Path(str(OUT) + "-node-pressure.jsonl")
PROBE_ERR = Path(str(OUT) + "-node-pressure.stderr.log")
PROBE_CLEANUP = Path(str(OUT) + "-node-pressure-cleanup.json")
PROBE_SECONDS = base.WINDOW_SECONDS + base.OUTER_OBSERVATION_SECONDS + base.CLEANUP_SECONDS


OWNER_PROGRAM = """import json,os,pathlib,signal,sys
run_id,action,pid,ticks=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4])
expected=['-','--seconds',sys.argv[5],'--interval','0.25','--run-id',run_id]
matches=[]
for path in pathlib.Path('/proc').iterdir():
 if not path.name.isdigit(): continue
 try:
  argv=(path/'cmdline').read_bytes().rstrip(b'\\0').decode().split('\\0')
  if len(argv)<2 or pathlib.Path(argv[0]).name!='python3' or argv[1:]!=expected: continue
  start=int((path/'stat').read_text().rsplit(') ',1)[1].split()[19])
  matches.append((int(path.name),start))
 except (FileNotFoundError,ProcessLookupError): pass
if len(matches)>1: raise RuntimeError('ambiguous node observer identity')
if pid:
 if matches and matches!=[(pid,ticks)]: raise RuntimeError('node observer identity changed')
if action=='stop' and matches: os.kill(matches[0][0],signal.SIGTERM)
if action=='verify' and matches: raise RuntimeError('node observer remains active')
print(json.dumps({'matches':matches,'action':action}))
"""


def owned_probe_command(seconds=PROBE_SECONDS, run_id=RUN_IDENTITY):
    return ["docker", "exec", "-i", NODE, "python3", "-", "--seconds",
            str(seconds), "--interval", "0.25", "--run-id", run_id]


def owner(action, identity=None):
    identity = identity or {}
    command = ["docker", "exec", NODE, "python3", "-c", OWNER_PROGRAM,
               RUN_IDENTITY, action, str(identity.get("pid", 0)),
               str(identity.get("start_ticks", 0)), str(PROBE_SECONDS)]
    return json.loads(subprocess.check_output(command, text=True, timeout=20))


def start_probe():
    if any(path.exists() for path in (PROBE_OUT, PROBE_ERR, PROBE_CLEANUP, OUT)):
        raise ValueError("AP identity or node observer output already used")
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
                        or identity.get("cgroup_count", 0) < 1
                        or identity.get("pid", 0) < 1
                        or identity.get("start_ticks", 0) < 1):
                    raise ValueError("node observer start identity invalid")
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
        return run_ap(argv)
    base.offline_check()
    if (not args.owner or not args.approval_reference
            or args.authorization_scope_sha256 != base.authorization_scope_sha256()):
        raise ValueError("AP execution authorization scope changed")
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
        result = run_ap(argv)
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
