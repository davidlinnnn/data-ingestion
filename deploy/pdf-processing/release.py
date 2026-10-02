"""Render an inactive, immutable group5/single-parser release. No cluster writes."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from pdf_processing.routing import release, release_binding, STAGES
from pdf_processing.object_store import digest

BOUNDS = json.loads((ROOT/'tests/pdf_processing/t09b/SUPPORTED-BOUNDS.json').read_text())


def render(profile, image, namespace, name, bucket, prefix, temporal, endpoint, secret):
    if profile.get('group_pages') != 5 or profile['method']['options']['do_ocr'] is not False:
        raise ValueError('Selected release requires group5/native parsing')
    if not re.fullmatch(r'[a-z0-9]([a-z0-9-]{0,35}[a-z0-9])?', name):
        raise ValueError('Invalid release name')
    prefix = prefix.strip('/')+'/'
    for review in profile.get('content_evidence', {}).get('reviews', {}).values():
        original=review.get('original_source')
        if original and not original['artifact']['key'].startswith(prefix+'sources/'):
            raise ValueError('Capture reviewed original source in the release prefix before rendering')
    producer = {p.name: digest(p.read_bytes()) for p in (ROOT/'src/pdf_processing').glob('*.py')}
    route = release(release_binding(profile, producer, BOUNDS['limits'], bucket, prefix),
                    {s: image for s in ('workflow', *STAGES)}, name)
    config_name = name+'-'+route['id'][:16]
    config = {'apiVersion': 'v1', 'kind': 'ConfigMap',
        'metadata': {'name': config_name, 'namespace': namespace}, 'immutable': True,
        'data': {'route.json': json.dumps(route, sort_keys=True),
                 'profile.json': json.dumps(profile, sort_keys=True)}}
    deployments = []
    for role in ('workflow', 'activity'):
        deployment_name = config_name+'-'+role
        values = {'WORKER_ROLE': role, 'TEMPORAL_ADDRESS': temporal,
            'TASK_QUEUE': route['queues']['workflow' if role == 'workflow' else 'prepare'],
            'WORKER_IMAGE': image, 'ROUTING_FILE': '/release/route.json', 'DRAIN_SECONDS': '30',
            'HF_HUB_OFFLINE': '1', 'NUMPY_MADVISE_HUGEPAGE': '0', 'OMP_NUM_THREADS': '4',
            'OPENBLAS_NUM_THREADS': '4'}
        if role == 'activity':
            values.update(WORKER_STAGE='all', OBJECT_ENDPOINT=endpoint, OBJECT_BUCKET=bucket,
                OBJECT_PREFIX=prefix, PROFILE_FILE='/release/profile.json',
                MODEL_CACHE='/experiment/PROTOTYPE-wipe-me/hf', SCRATCH='/scratch',
                PARSER_MODE='warm', LIMITS=json.dumps(BOUNDS['limits']),
                PARSER_BUDGETS=json.dumps(BOUNDS['parser_budgets']))
        container = {'name': 'worker', 'image': image, 'imagePullPolicy': 'IfNotPresent',
            'env': [{'name': n, 'value': v} for n, v in values.items()],
            'resources': {'requests': {'cpu': '100m', 'memory': '256Mi'},
                          'limits': {'cpu': '4', 'memory': '5Gi'}},
            'volumeMounts': [{'name': 'release', 'mountPath': '/release', 'readOnly': True}]}
        volumes = [{'name': 'release', 'configMap': {'name': config_name}}]
        if role == 'activity':
            container['envFrom'] = [{'secretRef': {'name': secret}}]
            container['volumeMounts'].append({'name': 'scratch', 'mountPath': '/scratch'})
            volumes.append({'name': 'scratch', 'emptyDir': {'sizeLimit': '1Gi'}})
        deployments.append({'apiVersion': 'apps/v1', 'kind': 'Deployment',
            'metadata': {'name': deployment_name, 'namespace': namespace},
            'spec': {'replicas': 0, 'strategy': {'type': 'Recreate'},
                'selector': {'matchLabels': {'app': deployment_name}},
                'template': {'metadata': {'labels': {'app': deployment_name}},
                    'spec': {'terminationGracePeriodSeconds': 60,
                        'nodeSelector': {'kubernetes.io/arch': 'arm64'},
                        'automountServiceAccountToken': False,
                        'containers': [container], 'volumes': volumes}}}})
    return {'apiVersion': 'v1', 'kind': 'List', 'items': [config, *deployments]}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--profile', type=Path, required=True)
    for arg in ('image', 'namespace', 'name', 'bucket', 'prefix', 'temporal', 'endpoint', 'secret'):
        cli.add_argument('--'+arg, required=True)
    args = vars(cli.parse_args())
    args['profile'] = json.loads(args['profile'].read_text())
    print(json.dumps(render(**args), indent=2))
