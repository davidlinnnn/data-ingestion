"""Namespace-specific object configuration; retain on PASS, restore on failure."""
import copy
import json
from pathlib import Path
import time

PATCH = json.loads(Path(__file__).with_name('object-candidate.patch.json').read_text())
RESOURCES = PATCH['spec']['template']['spec']['containers'][0]['resources']
STRATEGY = {'type': PATCH['spec']['strategy']['type']}
LIMIT_BYTES = 1073741824
READY_PROGRAM = """import json,urllib.request,urllib.error
try:
 ready=urllib.request.urlopen('http://objects:9000/minio/health/ready',timeout=2).status==200
except (urllib.error.URLError,TimeoutError,ConnectionError):
 ready=False
print(json.dumps(ready))
"""


def configuration(value):
    return {
        'resources': value['spec']['template']['spec']['containers'][0]['resources'],
        'strategy': value['spec']['strategy'],
    }


def capture(kube):
    value = kube.json('get', 'deployment', 'objects')
    return {'uid': value['metadata']['uid'], **copy.deepcopy(configuration(value))}


def replace(kube, value, target):
    operations = [
        {'op': 'test', 'path': '/metadata/uid', 'value': value['metadata']['uid']},
        {'op': 'test', 'path': '/metadata/resourceVersion',
         'value': value['metadata']['resourceVersion']},
    ]
    for key, path in (
        ('resources', '/spec/template/spec/containers/0/resources'),
        ('strategy', '/spec/strategy'),
    ):
        operations.extend([
            {'op': 'test', 'path': path, 'value': configuration(value)[key]},
            {'op': 'replace', 'path': path, 'value': target[key]},
        ])
    kube.run(['patch', 'deployment', 'objects', '--type=json',
              '-p', json.dumps(operations)], timeout=30)


def apply(kube, snapshot):
    value = kube.json('get', 'deployment', 'objects')
    if (value['metadata']['uid'] != snapshot['uid']
            or configuration(value) != {key: snapshot[key] for key in ('resources', 'strategy')}):
        raise ValueError('object configuration changed before candidate apply')
    replace(kube, value, {'resources': RESOURCES, 'strategy': STRATEGY})


def await_ready(kube, expected_bytes, *, excluded_uid='', seconds=120):
    from sentinel.object_monitor_bh import object_identity
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            identity = object_identity(kube, expected_bytes)
        except (KeyError, IndexError, ValueError):
            time.sleep(.5)  # Recreate temporarily has no ready Pod.
            continue
        if identity['pod_uid'] != excluded_uid:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if json.loads(kube.exec_python('coordinator', READY_PROGRAM,
                                          timeout=min(10, remaining))) is True:
                return identity
        time.sleep(.5)
    raise TimeoutError('object candidate/recovery readiness deadline')


def finish(kube, snapshot, *, qualified):
    value = kube.json('get', 'deployment', 'objects')
    if value['metadata']['uid'] != snapshot['uid']:
        raise ValueError('object Deployment changed outside qualification')
    old = {key: snapshot[key] for key in ('resources', 'strategy')}
    candidate = {'resources': RESOURCES, 'strategy': STRATEGY}
    observed = configuration(value)
    if observed not in (old, candidate) or (qualified and observed != candidate):
        raise ValueError('object configuration changed outside qualification')
    if not qualified and observed == candidate:
        replace(kube, value, old)
    target = candidate if qualified else old
    quantity = target['resources']['limits']['memory']
    multiplier = 1073741824 if quantity.endswith('Gi') else 1048576
    identity = await_ready(kube, int(quantity[:-2]) * multiplier)
    return {'decision': 'retained' if qualified else 'restored',
            'configuration': target, 'pod': identity}
