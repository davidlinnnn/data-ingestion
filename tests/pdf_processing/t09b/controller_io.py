"""Read-only retained-object checks and bounded native trace ownership."""
import json
import time
from uuid import uuid4

from trace_session import TraceSession


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
    key = prefix.rstrip('/') + '/measurement-markers/' + call_id
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
    command = list(kube.base) + ['exec', pod, '--', 'sh', '-c',
        'export MC_HOST_probe="http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@127.0.0.1:9000"; '
        'exec timeout 2500 mc admin trace --json --verbose probe']
    trace = TraceSession(command, output, 't09a', prefix)
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
        return trace.finish(marker(kube, prefix))
    finally:
        trace.close()
