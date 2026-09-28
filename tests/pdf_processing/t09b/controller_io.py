"""Read-only retained-object checks and bounded native trace ownership."""
import json
import time
from uuid import uuid4

from trace_session import TraceSession


class NativeTrace(TraceSession):
    def __init__(self, kube, pod, output, prefix):
        self.kube, self.pod = kube, pod
        self.owner = '/tmp/t09b-trace-' + uuid4().hex
        self.remote_stopped = False
        script = '''set -eu
owner=$1
export MC_HOST_probe="http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@127.0.0.1:9000"
timeout -k 5 2500 mc admin trace --json --verbose probe &
pid=$!
trap 'kill -TERM "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; rm -f "$owner"' EXIT INT TERM
set -- $(cat /proc/$pid/stat)
ticks=${22}
(set -C; printf '%s %s\\n' "$pid" "$ticks" > "$owner")
wait "$pid"
'''
        command = list(kube.base) + ['exec', pod, '--', 'sh', '-c', script, 'trace', self.owner]
        super().__init__(command, output, 't09a', prefix, prefix.rstrip('/') + '-markers/')

    def close(self):
        self.stopping = True
        try:
            if not self.remote_stopped:
                script = '''set -eu
owner=$1
test -s "$owner"
read pid ticks < "$owner"
if test -e /proc/$pid/stat; then
 set -- $(cat /proc/$pid/stat)
 actual=${22}
 test "$actual" = "$ticks"
 kill -TERM "$pid"
fi
n=0
while test -e "$owner"; do
 n=$((n+1)); test "$n" -lt 100; sleep .1
done
test ! -e /proc/$pid/stat
'''
                self.kube.run(['exec', self.pod, '--', 'sh', '-c', script, 'stop', self.owner], timeout=15)
                self.remote_stopped = True
        finally:
            super().close()


def retained_object(runner, kube):
    deployment = runner.object_trial.deployment(kube)
    spec = deployment['spec']
    expected = {'requests': {'cpu': '100m', 'memory': '768Mi'},
                'limits': {'memory': '1Gi'}}
    if (spec['template']['spec']['containers'][0]['resources'] != expected
            or spec['strategy'] != {'type': 'Recreate'}
            or deployment['status'].get('availableReplicas') != 1):
        raise ValueError('accepted object-service configuration is not healthy')
    pvc = kube.json('get', 'pvc', 'object-data')
    if pvc['status']['phase'] != 'Bound':
        raise ValueError('object PVC is not bound')
    identity = runner.object_monitor_bh.object_identity(kube, runner.object_trial.TRIAL_BYTES)
    return {'deployment_uid': deployment['metadata']['uid'],
            'pvc_uid': pvc['metadata']['uid'], 'volume': pvc['spec']['volumeName'],
            'pod': identity, 'resources': expected, 'strategy': 'Recreate'}


def marker(kube, prefix):
    call_id = uuid4().hex
    key = prefix.rstrip('/') + '-markers/' + call_id
    # Credentials stay in the existing coordinator environment. Marker objects
    # are unique, retained and excluded by run-level traffic reconciliation.
    program = '''import boto3,json
s=boto3.client('s3',endpoint_url='http://objects:9000')
def tag(params,**kwargs): params.setdefault('headers',{})['X-T09b-Call-Id']=CALL_ID
s.meta.events.register('before-call.s3',tag)
s.put_object(Bucket='t09a',Key=KEY,Body=b'',IfNoneMatch='*')
print(json.dumps({'call_id':CALL_ID}))
'''.replace('CALL_ID', repr(call_id)).replace('KEY', repr(key))
    result = json.loads(kube.exec_python('coordinator', program, timeout=20))
    if result != {'call_id': call_id}:
        raise ValueError('trace marker response changed')
    return call_id


def start_trace(kube, pod, output, prefix):
    trace = NativeTrace(kube, pod, output, prefix)
    try:
        # A short settle is not readiness: admission requires the observed marker.
        time.sleep(2)
        trace.ready(marker(kube, prefix))
        return trace
    except BaseException:
        trace.close()
        raise


def finish_trace(trace, kube, prefix):
    """Call only after worker stop; remote timeout remains a separate cleanup bound."""
    try:
        report = trace.finish(marker(kube, prefix))
        report['remote_stopped'] = trace.remote_stopped
        return report
    finally:
        trace.close()
