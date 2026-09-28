"""Read-only Kubernetes inventory; emits no environment values or credentials."""
import json
import subprocess
import datetime
from pathlib import Path


def kubectl(*args):
    return json.loads(subprocess.check_output(['kubectl','--context','kind-internal-a2a-vs6-local','--request-timeout=10s',*args,'-o','json'],text=True,timeout=30))


def main(out):
    deployments=kubectl('get','deployments','-A')['items']
    pods=kubectl('get','pods','-A')['items']
    def identity(v):
        return {k:v['metadata'].get(k) for k in ('namespace','name','uid','resourceVersion')}
    result={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'deployments':[{**identity(v),'replicas':v['spec']['replicas'],'ready':v['status'].get('readyReplicas',0),
            'containers':[{'name':c['name'],'image':c['image'],'resources':c.get('resources',{})} for c in v['spec']['template']['spec']['containers']]}
            for v in deployments],
        'coordinators':[{**identity(v),'node':v['spec']['nodeName'],'phase':v['status']['phase'],
            'volumes':v['spec'].get('volumes',[]),'containers':[{'name':c['name'],'image':c['image'],
                'resources':c.get('resources',{}),'mounts':c.get('volumeMounts',[])} for c in v['spec']['containers']],
            'statuses':[{k:c.get(k) for k in ('name','ready','restartCount','imageID','containerID')} for c in v['status']['containerStatuses']]}
            for v in pods if v['metadata']['name']=='coordinator'],
        'pods':[{**identity(v),'node':v['spec'].get('nodeName'),'phase':v['status']['phase'],
            'owners':v['metadata'].get('ownerReferences',[]),'labels':v['metadata'].get('labels',{})} for v in pods],
        'nodes':[{**identity(v),'capacity':v['status']['capacity'],'allocatable':v['status']['allocatable'],
            'conditions':v['status']['conditions']} for v in kubectl('get','nodes')['items']]}
    with Path(out).open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({'captured_at':result['captured_at'],'deployments':len(deployments),'pods':len(pods),
        'coordinator':next(v for v in result['coordinators'] if v['namespace']=='pdf-t09a-validation')},indent=2))

if __name__=='__main__':
    import sys
    main(sys.argv[1])
