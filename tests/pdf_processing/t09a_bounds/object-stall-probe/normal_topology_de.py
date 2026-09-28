"""One short DD-setting MinIO PUT/GET diagnostic; no ingestion or retry."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / "tests/pdf_processing/t09a_bounds"))

import normal_topology_co as co
import object_policy


RUN_ID = "object-rw-de"
PREFIX = "t09a/object-probe-20260928-de/"
OUT = Path("/private/tmp/q44-object-rw-de")
TRACE_CONTAINER = "q44-object-rw-de"
REQUEST_BYTES = 8 * 1024 * 1024
REQUESTS = 4

co.RUN_ID = RUN_ID
co.OUT = OUT
co.TRACE_CONTAINER = TRACE_CONTAINER
co.runner.RUN_IDENTITY = RUN_ID
co.record = {
    "run_id": RUN_ID,
    "prefix": PREFIX,
    "mode": "candidate rollout; normal32-on; bounded PUT then GET; no ingestion",
    "automatic_retry": False,
    "restoration_errors": [],
    "operations": [],
}
co.activated = []
co.trace = co.trace_log = co.trace_owner = None


CLIENT = """import boto3,json,sys,time
from botocore.config import Config
c=boto3.client('s3',endpoint_url='http://objects:9000',config=Config(connect_timeout=3,read_timeout=5,retries={'total_max_attempts':1}))
key=sys.argv[1];size=int(sys.argv[2]);kind=sys.argv[3]
started=time.time();mono=time.monotonic()
if kind=='put':
 response=c.put_object(Bucket='t09a',Key=key,Body=b'Q'*size,IfNoneMatch='*')
 actual=size
else:
 body=c.get_object(Bucket='t09a',Key=key)['Body']
 try: actual=len(body.read())
 finally: body.close()
finished=time.time()
print(json.dumps({'kind':kind,'key':key,'bytes':actual,'started_at':started,
 'finished_at':finished,'latency_seconds':time.monotonic()-mono}))
"""


def object_operation(kind, key):
    reply = json.loads(co.object_request(CLIENT, key, str(REQUEST_BYTES), kind))
    if (reply["kind"] != kind or reply["key"] != key
            or reply["bytes"] != REQUEST_BYTES
            or not 0 < reply["latency_seconds"] < 8):
        raise ValueError("object operation response changed")
    co.record["operations"].append(reply)
    return reply


def activate_normal_topology():
    for item in co.current():
        co.activated.append({"namespace": item["metadata"]["namespace"],
            "name": item["metadata"]["name"], "uid": item["metadata"]["uid"]})
        co.patch(item, 0, 1)
        co.checked("activation")
    deadline = time.monotonic() + 180
    while True:
        co.checked("readiness")
        rows = co.current()
        if all(x["spec"]["replicas"] == 1
               and x["status"].get("readyReplicas", 0) == 1 for x in rows):
            co.record["all_ready_at"] = time.time()
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("32-Deployment readiness deadline")
        time.sleep(1)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=False)
    snapshot = None
    candidate_applied = False

    def interrupt(*_):
        raise KeyboardInterrupt("diagnostic interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    try:
        co.base.verify_held_deployments(co.kube)
        co.base.t09a_health(co.kube, OUT / "health-before.json", require_idle=True)
        snapshot = object_policy.capture(co.kube)
        co.record["object_before"] = snapshot
        object_policy.apply(co.kube, snapshot)
        candidate_applied = True
        co.identity = object_policy.await_ready(co.kube, object_policy.LIMIT_BYTES)
        co.record["candidate"] = co.identity
        co.start_trace()
        identify = """from pathlib import Path
import json,sys
rows=[]
for p in Path('/proc').glob('[0-9]*'):
 try:
  if sys.argv[1] in (p/'cgroup').read_text() and (p/'comm').read_text().strip()=='minio':
   rows.append({'pid':int(p.name),'argv':(p/'cmdline').read_bytes().decode().split('\\0')[:-1]})
 except (FileNotFoundError,ProcessLookupError): pass
print(json.dumps(rows))
"""
        co.record["server_processes"] = json.loads(subprocess.check_output(
            ["docker", "exec", TRACE_CONTAINER, "python3", "-c", identify,
             co.identity["container_id"]], text=True, timeout=10))
        if (len(co.record["server_processes"]) != 1
                or co.record["server_processes"][0]["argv"] != ["minio", "server", "/data"]):
            raise ValueError("exact MinIO server process not identified")
        co.record["baseline"] = co.sample("candidate-baseline")
        co.checked("before-activation", co.base.OUTER_AVAILABLE_BYTES)
        activate_normal_topology()
        co.checked("admission", co.base.OUTER_AVAILABLE_BYTES)
        deadline = time.monotonic() + 75
        for index in range(REQUESTS):
            if time.monotonic() >= deadline:
                raise TimeoutError("bounded object request deadline")
            key = f"{PREFIX}object-{index:02d}.bin"
            co.checked("before-put")
            object_operation("put", key)
            co.checked("after-put")
            co.checked("before-get")
            object_operation("get", key)
            co.checked("after-get")
        co.record["observed"] = co.checked("window-complete")
        co.record["status"] = "NO_PSI_IN_BOUNDED_RW"
    except BaseException as error:
        co.record["status"] = "STOPPED"
        co.record["error"] = repr(error)
    finally:
        try:
            co.stop_trace()
        except BaseException as error:
            co.record["restoration_errors"].append(repr(error))
        try:
            co.restore()
        except BaseException as error:
            co.record["restoration_errors"].append(repr(error))
        if snapshot is not None:
            try:
                co.record["object_decision"] = object_policy.finish(
                    co.kube, snapshot, qualified=False)
            except BaseException as error:
                co.record["restoration_errors"].append(repr(error))
        try:
            co.base.verify_held_deployments(co.kube)
            co.record["final_health"] = co.base.t09a_health(
                co.kube, OUT / "health-after.json", require_idle=True)
        except BaseException as error:
            co.record["restoration_errors"].append(repr(error))
        co.record["candidate_applied"] = candidate_applied
        co.record["finished_at"] = time.time()
        (OUT / "summary.json").write_text(json.dumps(co.record, indent=2) + "\n")
        print(json.dumps({key: co.record.get(key) for key in
            ("status", "error", "restoration", "restoration_errors", "object_decision")}))
    raise SystemExit(0 if co.record["status"] == "NO_PSI_IN_BOUNDED_RW"
        and not co.record["restoration_errors"] else 1)
