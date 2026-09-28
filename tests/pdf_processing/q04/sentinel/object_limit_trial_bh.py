"""One UID-fenced, reversible 1 GiB object-service trial on existing kind."""

import json
import time

from sentinel.object_monitor_bh import object_identity


DEPLOYMENT = 'objects'
DEPLOYMENT_UID = '9e69720a-ff80-4aa5-9941-14925dfdf981'
OLD_LIMIT = '512Mi'
TRIAL_LIMIT = '1Gi'
OLD_BYTES = 536870912
TRIAL_BYTES = 1073741824


def deployment(kube) -> dict:
    value = kube.json('get', 'deployment', DEPLOYMENT)
    if (value['metadata']['uid'] != DEPLOYMENT_UID
            or value['spec']['replicas'] != 1
            or value['spec']['selector']['matchLabels'] != {'app': 'pdf-objects'}
            or len(value['spec']['template']['spec']['containers']) != 1):
        raise ValueError('object-service Deployment identity changed')
    return value


def limit(value: dict) -> str:
    return value['spec']['template']['spec']['containers'][0]['resources']['limits']['memory']


def patch_limit(kube, value: dict, before: str, after: str):
    if limit(value) != before:
        raise ValueError('object-service limit precondition changed')
    path = '/spec/template/spec/containers/0/resources/limits/memory'
    patch = [
        {'op': 'test', 'path': '/metadata/uid', 'value': DEPLOYMENT_UID},
        {'op': 'test', 'path': '/metadata/resourceVersion',
         'value': value['metadata']['resourceVersion']},
        {'op': 'test', 'path': path, 'value': before},
        {'op': 'replace', 'path': path, 'value': after},
    ]
    kube.run(['patch', 'deployment', DEPLOYMENT, '--type=json',
              '-p', json.dumps(patch)], timeout=30)


def await_object_pod(kube, expected_bytes: int, excluded_uid: str,
                     *, deadline: float) -> dict:
    while time.time() < deadline:
        try:
            identity = object_identity(kube, expected_bytes)
        except (KeyError, IndexError, ValueError):
            time.sleep(.5)  # RollingUpdate may briefly expose old and new Pods.
            continue
        if identity['pod_uid'] != excluded_uid:
            if limit(deployment(kube)) != ('1Gi' if expected_bytes == TRIAL_BYTES else '512Mi'):
                raise ValueError('object-service Deployment limit changed after rollout')
            return identity
        time.sleep(.5)
    raise TimeoutError('object-service exact replacement Pod readiness deadline')


def capture(kube) -> dict:
    before = deployment(kube)
    if limit(before) != OLD_LIMIT:
        raise ValueError('object-service original 512Mi limit changed')
    return {'deployment_uid': DEPLOYMENT_UID, 'old_limit': OLD_LIMIT,
            'trial_limit': TRIAL_LIMIT,
            'old_pod': object_identity(kube, OLD_BYTES),
            'trial_pod': None}


def enter(kube, trial: dict, *, deadline: float) -> dict:
    patch_limit(kube, deployment(kube), OLD_LIMIT, TRIAL_LIMIT)
    trial['trial_pod'] = await_object_pod(kube, TRIAL_BYTES,
        trial['old_pod']['pod_uid'], deadline=deadline)
    return trial


def restore(kube, trial: dict, *, deadline: float) -> dict:
    current = deployment(kube)
    observed = limit(current)
    if observed == TRIAL_LIMIT:
        patch_limit(kube, current, TRIAL_LIMIT, OLD_LIMIT)
        excluded = trial['trial_pod']['pod_uid'] if trial['trial_pod'] else ''
        restored = await_object_pod(kube, OLD_BYTES, excluded,
                                    deadline=deadline)
    elif observed == OLD_LIMIT:
        excluded = trial['trial_pod']['pod_uid'] if trial['trial_pod'] else ''
        restored = await_object_pod(kube, OLD_BYTES, excluded,
                                    deadline=deadline)
    else:
        raise ValueError('object-service limit changed outside BH trial')
    return {'restored_limit': OLD_LIMIT, 'pod': restored,
            'deployment_uid': DEPLOYMENT_UID}
