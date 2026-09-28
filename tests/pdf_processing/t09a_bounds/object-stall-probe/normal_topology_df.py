"""Replay DD's many-small-key object shape once; no ingestion or retry."""
import json
from pathlib import Path
import signal
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / "tests/pdf_processing/t09a_bounds"))

import normal_topology_de as de


co = de.co
object_policy = de.object_policy
RUN_ID = "object-small-key-df"
SOURCE = "t09a/bounds-20260928-dd/"
PREFIX = "t09a/object-probe-20260928-df/"
OUT = Path("/private/tmp/q44-object-small-key-df")
TRACE_CONTAINER = "q44-object-small-key-df"
SELECTED = 256
SELECTED_BYTES = 2737516
BATCH = 16

co.RUN_ID = RUN_ID
co.OUT = OUT
co.TRACE_CONTAINER = TRACE_CONTAINER
co.runner.RUN_IDENTITY = RUN_ID
co.record = {"run_id": RUN_ID, "source": SOURCE, "prefix": PREFIX,
    "mode": "candidate rollout; normal32-on; DD many-small-key copy/readback",
    "automatic_retry": False, "restoration_errors": [], "batches": []}
co.activated = []
co.trace = co.trace_log = co.trace_owner = None


REPLAY = """import boto3,json,sys,time
from botocore.config import Config
c=boto3.client('s3',endpoint_url='http://objects:9000',config=Config(connect_timeout=3,read_timeout=5,retries={'total_max_attempts':1}))
source,target,start,count=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4])
objects=sorted(c.list_objects_v2(Bucket='t09a',Prefix=source,MaxKeys=1000).get('Contents',[]),key=lambda x:(x['Size'],x['Key']))
selected=[];total=0
for obj in objects:
 if len(selected)>=256: break
 if total+obj['Size']<=33554432: selected.append(obj);total+=obj['Size']
rows=[]
for obj in selected[start:start+count]:
 t=time.monotonic();body=c.get_object(Bucket='t09a',Key=obj['Key'])['Body']
 try: data=body.read()
 finally: body.close()
 source_get=time.monotonic()-t
 key=target+obj['Key'][len(source):]
 t=time.monotonic();c.put_object(Bucket='t09a',Key=key,Body=data,IfNoneMatch='*');put=time.monotonic()-t
 t=time.monotonic();body=c.get_object(Bucket='t09a',Key=key)['Body']
 try: copied=body.read()
 finally: body.close()
 dest_get=time.monotonic()-t
 if copied!=data: raise ValueError('readback changed')
 rows.append({'key':key,'bytes':len(data),'source_get_seconds':source_get,
  'put_seconds':put,'dest_get_seconds':dest_get})
print(json.dumps({'selected':len(selected),'selected_bytes':total,'start':start,'rows':rows}))
"""


def replay_batch(start):
    result = json.loads(co.object_request(REPLAY, SOURCE, PREFIX, str(start), str(BATCH)))
    if (result["selected"] != SELECTED or result["selected_bytes"] != SELECTED_BYTES
            or result["start"] != start
            or len(result["rows"]) != min(BATCH, SELECTED - start)
            or any(row["bytes"] < 0 or not row["key"].startswith(PREFIX)
                   or any(not 0 < row[name] < 8 for name in
                          ("source_get_seconds", "put_seconds", "dest_get_seconds"))
                   for row in result["rows"])):
        raise ValueError("small-key replay response changed")
    co.record["batches"].append(result)
    return result


if __name__ == "__main__":
    OUT.mkdir(exist_ok=False)
    snapshot = None

    def interrupt(*_):
        raise KeyboardInterrupt("diagnostic interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    try:
        co.base.verify_held_deployments(co.kube)
        co.base.t09a_health(co.kube, OUT / "health-before.json", require_idle=True)
        snapshot = object_policy.capture(co.kube)
        co.record["object_before"] = snapshot
        object_policy.apply(co.kube, snapshot)
        co.identity = object_policy.await_ready(co.kube, object_policy.LIMIT_BYTES)
        co.record["candidate"] = co.identity
        co.start_trace()
        co.record["baseline"] = co.sample("candidate-baseline")
        co.checked("before-activation", co.base.OUTER_AVAILABLE_BYTES)
        de.activate_normal_topology()
        co.checked("admission", co.base.OUTER_AVAILABLE_BYTES)
        deadline = time.monotonic() + 90
        for start in range(0, SELECTED, BATCH):
            if time.monotonic() >= deadline:
                raise TimeoutError("bounded small-key replay deadline")
            co.checked("before-batch")
            replay_batch(start)
            co.checked("after-batch")
        co.record["observed"] = co.checked("window-complete")
        co.record["status"] = "NO_PSI_IN_SMALL_KEY_REPLAY"
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
        co.record["finished_at"] = time.time()
        (OUT / "summary.json").write_text(json.dumps(co.record, indent=2) + "\n")
        print(json.dumps({key: co.record.get(key) for key in
            ("status", "error", "restoration", "restoration_errors", "object_decision")}))
    raise SystemExit(0 if co.record["status"] == "NO_PSI_IN_SMALL_KEY_REPLAY"
        and not co.record["restoration_errors"] else 1)
