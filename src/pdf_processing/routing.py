"""Frozen explicit queues for independently deployed processing stages.

This pure module is safe in the deterministic Workflow sandbox. Queue names are
content-addressed by the complete release binding; a release is never retargeted.
"""
import hashlib
import json
import re

STAGES = ('prepare', 'group', 'assembly', 'select', 'component_ocr', 'finalize')
CONTRACT = 'pdf-explicit-routing-v1'


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def release_binding(profile, producer, limits, bucket, prefix):
    return {'profile': fingerprint(profile), 'producer': fingerprint(producer),
        'limits': fingerprint(limits), 'models': fingerprint(profile['method']['model_artifacts']),
        'store': {'bucket': bucket, 'prefix': prefix}}


def release(binding, images, prefix):
    """Build a maintainer manifest after images/profile/models have been retained."""
    value = {'contract': CONTRACT, 'binding': binding, 'images': images, 'prefix': prefix}
    identity = fingerprint(value)
    value['id'] = identity
    value['queues'] = {stage: f'{prefix}-{stage}-{identity}' for stage in ('workflow', *STAGES)}
    validate(value)
    return value


def validate(route):
    try:
        if set(route) != {'contract', 'binding', 'images', 'prefix', 'id', 'queues'}:
            raise ValueError()
        if route['contract'] != CONTRACT or not re.fullmatch(r'[a-z0-9-]{1,80}', route['prefix']):
            raise ValueError()
        binding = route['binding']
        if set(binding) != {'profile', 'producer', 'limits', 'models', 'store'}:
            raise ValueError()
        if any(not re.fullmatch('[0-9a-f]{64}', binding[k]) for k in ('profile','producer','limits','models')):
            raise ValueError()
        if set(binding['store']) != {'bucket', 'prefix'} or not all(binding['store'].values()):
            raise ValueError()
        stages = ('workflow', *STAGES)
        if set(route['images']) != set(stages) or any(not re.fullmatch(r'.+@sha256:[0-9a-f]{64}', v) for v in route['images'].values()):
            raise ValueError()
        identity = fingerprint({k: route[k] for k in ('contract','binding','images','prefix')})
        if route['id'] != identity or route['queues'] != {s: f'{route["prefix"]}-{s}-{identity}' for s in stages}:
            raise ValueError()
    except (KeyError, TypeError, AttributeError):
        raise ValueError('invalid_routing') from None
    except ValueError:
        raise ValueError('invalid_routing') from None
    return route


def stage_for(value):
    stage = value['operation']['kind'] if value['stage'] == 'execute' else value['stage']
    if stage not in STAGES:
        raise ValueError('invalid_routing_stage')
    return stage


def submission(request, release_id, retained):
    """Internal admission: select an explicitly retained release; never resolve latest."""
    route = retained.get(release_id)
    if route is None:
        raise ValueError('routing_unavailable')
    validate(route)
    if route['id'] != release_id:
        raise ValueError('invalid_routing')
    if request.get('routing_id', route['id']) != route['id']:
        raise ValueError('request_routing_conflict')
    return {'request': {**request, 'routing_id': route['id']},
            'routing': json.loads(json.dumps(route))}
