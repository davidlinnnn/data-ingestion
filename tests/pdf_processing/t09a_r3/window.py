"""Authorized T03–T07 capacity lease; restore original replicas before unlocking."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tests/pdf_processing/t09a_r2'))
import run_window as run
import resources_window as r2_resources

OUT=Path('/private/tmp/t09a-r3-window-20260914-d')
NAMESPACES=[f'pdf-t{n:02}-validation' for n in range(3,8)]
ROLES=('activities','workflows','objects','temporal')
IDENTITIES={}

def k(ns,*args):
    return subprocess.check_output(['kubectl','--request-timeout=15s','-n',ns,*args],text=True,timeout=45)

def open_work():
    script=(ROOT/'tests/pdf_processing/t09a_r2/open_work.py').read_text()
    raw=subprocess.check_output(['kubectl','-n','pdf-t09a-validation','exec','-i','coordinator','--',run.PYTHON,'-'],input=script,text=True,timeout=180)
    values=json.loads(raw)
    for ns in NAMESPACES:
        value=next(v for v in values if v['namespace']==ns)
        assert value['query_status']=='complete' and not value['open'],f'New/unknown Temporal work: {ns}'
    return values

def wait_ready(ns,role,replicas):
    deadline=time.monotonic()+180
    while True:
        value=json.loads(k(ns,'get','deployment',role,'-o','json'))
        if value['status'].get('observedGeneration',0)>=value['metadata']['generation'] and value['status'].get('readyReplicas',0)==replicas and value['status'].get('updatedReplicas',0)==replicas:return value
        assert time.monotonic()<deadline,f'Restore readiness deadline: {ns}/{role}'
        time.sleep(3)

def nodes():return [n['metadata']['name'] for n in json.loads(k('default','get','nodes','-o','json'))['items']]

def running(predicate):
    found=[]
    for node in nodes():
        data=json.loads(subprocess.check_output(['docker','exec',node,'crictl','ps','--state','Running','-o','json'],text=True,timeout=20))
        found.extend({'node':node,'container':c['id'],'labels':c.get('labels',{})} for c in data['containers'] if predicate(c.get('labels',{})))
    return found

def selected_labels(label,roles):
    return label.get('io.kubernetes.pod.namespace') in NAMESPACES and label.get('io.kubernetes.pod.name','').startswith(tuple(r+'-' for r in roles))

def wait_absent(roles):
    while True:
        pods=[]
        for ns in NAMESPACES:
            pods += [p for p in json.loads(k(ns,'get','pods','-o','json'))['items'] if p['metadata']['name'].startswith(tuple(r+'-' for r in roles))]
        if not pods and not running(lambda label:selected_labels(label,roles)):return
        time.sleep(3)

def scale(ns,role,replicas):
    value=json.loads(k(ns,'get','deployment',role,'-o','json'))
    assert value['metadata']['uid']==IDENTITIES[(ns,role)],f'Deployment ownership changed: {ns}/{role}'
    k(ns,'scale','deployment/'+role,'--replicas='+str(replicas),'--resource-version='+value['metadata']['resourceVersion'])

def services_ready():
    script='''import asyncio,urllib.request
from temporalio.client import Client
async def main():
 for n in range(3,8):
  ns=f'pdf-t{n:02}-validation'
  with urllib.request.urlopen('http://objects.'+ns+'.svc.cluster.local:9000/minio/health/ready',timeout=10) as response:assert response.status==200
  client=await Client.connect('temporal.'+ns+'.svc.cluster.local:7233')
  assert await client.service_client.check_health()
asyncio.run(main())
'''
    subprocess.check_output(['kubectl','-n','pdf-t09a-validation','exec','-i','coordinator','--',run.PYTHON,'-'],input=script,text=True,timeout=120)


def main():
    OUT.mkdir(exist_ok=True)
    run.OUT.mkdir(parents=True,exist_ok=True)
    state={'started':time.time(),'phase':'checking','originals':[],'mutated':False}
    def save(): (OUT/'window-state.json').write_text(json.dumps(state,indent=2)+'\n')
    with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            assert not (OUT/'original-deployments.json').exists(),'Use a new window directory; preserve prior lease evidence'
            original=json.loads(Path('/private/tmp/t09a-r2-20260914/capacity-inventory.json').read_text())['items']
            snapshots=[]
            for ns in NAMESPACES:
                for role in ROLES:
                    value=json.loads(k(ns,'get','deployment',role,'-o','json'))
                    expected=next(x for x in original if x['kind']=='Deployment' and x['metadata']['namespace']==ns and x['metadata']['name']==role)
                    assert value['metadata']['uid']==expected['metadata']['uid'] and value['spec']['replicas']==expected['spec']['replicas'],f'Ownership/replica change: {ns}/{role}'
                    assert value['spec']==expected['spec'],f'Deployment resource/configuration change: {ns}/{role}'
                    IDENTITIES[(ns,role)]=value['metadata']['uid']
                    snapshots.append(value)
                    state['originals'].append({'namespace':ns,'deployment':role,'uid':value['metadata']['uid'],'replicas':value['spec']['replicas']})
            (OUT/'original-deployments.json').write_text(json.dumps(snapshots))
            (OUT/'open-before.json').write_text(json.dumps(open_work(),indent=2))
            state.update(phase='pausing-workers',mutated=True);save()
            for ns in NAMESPACES:
                for role in ('activities','workflows'):scale(ns,role,0)
            wait_absent(('activities','workflows'))
            (OUT/'open-after-workers.json').write_text(json.dumps(open_work(),indent=2))
            state['phase']='pausing-services';save()
            for ns in NAMESPACES:
                for role in ('temporal','objects'):scale(ns,role,0)
            wait_absent(('temporal','objects'))
            run.quiesce()
            assert not running(lambda label:label.get('io.kubernetes.pod.namespace')=='pdf-t09a-validation' and label.get('io.kubernetes.pod.name','').startswith(('r2-activities-','r2-workflows-'))),'Prior runtime remains'
            state.update(phase='admission',paused_at=time.time(),available_after_pause=run.vm());save()
            run.admission()
            state.update(phase='ready',admission_passed_at=time.time());save()
            print('AUTHORIZED PAUSE COMPLETE; admission PASS; waiting for staged action',flush=True)
            action_index=1
            deadline=time.monotonic()+7200
            while True:
                path=OUT/f'action-{action_index:03}.json'
                if not path.exists():
                    assert time.monotonic()<deadline,'Capacity lease action deadline'
                    time.sleep(1);continue
                action=json.loads(path.read_text());mode=action['mode']
                if mode=='finish':break
                assert mode=='preflight' or state.get('preflight_passed'), 'Keynote preflight must pass first'
                state.update(phase='running',action=action,action_started=time.time());save()
                try:
                    if mode in ('fault','drain'):
                        import fault_window
                        fault_window.main(held_lock=True,run_guard=mode=='fault')
                    elif mode=='full-suite':
                        import full_suite_window
                        run.admission()
                        full_suite_window.main(held_lock=True)
                    else:
                        run.admission();r2_resources.setup()
                        run.k('scale','deployment/'+run.WORKFLOWS,'--replicas=1')
                        run.k('rollout','status','deployment/'+run.WORKFLOWS,'--timeout=60s')
                        if mode=='preflight':run.trial('10',action.get('trial','preflight-10'),True)
                        elif mode=='fresh':
                            for sid in action['sids']:run.trial(sid,'fresh-'+sid,True)
                        elif mode=='warm':
                            for i,sid in enumerate(('06','07','08','native','06')):run.trial(sid,f'warm-{i}-{sid}',i==0,['--require-fresh'])
                        elif mode=='compatibility':run.trial('native','compatible-old-native',True,['--source-from-old','drain-native','--expect-old-groups','--require-fresh'])
                        elif mode=='replay':
                            for i,sid in enumerate(action['sids']):
                                script='from pathlib import Path; import sys; r=Path(sys.argv[1]); (r/(sys.argv[2]+"-request.json")).write_bytes((r/(sys.argv[3]+"-request.json")).read_bytes())'
                                run.k('exec','coordinator','--',run.PYTHON,'-c',script,'/tmp/'+run.PREFIX+'-results','replay-'+sid,'fresh-'+sid)
                                run.trial(sid,'replay-'+sid,i==0,['--expect-reuse','--expect-exact-replay','--require-fresh'])
                        else:raise ValueError('Unsupported staged action: '+mode)
                finally:run.quiesce()
                (OUT/f'result-{action_index:03}.json').write_text(json.dumps({'action':action,'status':'passed','finished':time.time()}))
                if mode=='preflight':state['preflight_passed']=True
                state.update(phase='ready',last_completed=action_index);save()
                print('STAGED ACTION PASSED',action,flush=True)
                action_index+=1
        except BaseException as error:
            state.update(phase='failed',error=str(error),failed_at=time.time());save();raise
        finally:
            # Even an API failure must not release this lease while own inference
            # remains active or authorized borrowed services remain paused.
            while True:
                try:
                    run.quiesce()
                    if not running(lambda label:label.get('io.kubernetes.pod.namespace')=='pdf-t09a-validation' and label.get('io.kubernetes.pod.name','').startswith(('r2-activities-','r2-workflows-'))):break
                except Exception:pass
                print('Holding capacity lock for T09a runtime cleanup',flush=True);time.sleep(5)
            state['owned_quiescent_at']=time.time();save()
            if state['mutated']:
                while True:
                    try:
                        for roles in (('objects','temporal'),('workflows','activities')):
                            selected=[v for v in state['originals'] if v['deployment'] in roles]
                            for value in selected:scale(value['namespace'],value['deployment'],value['replicas'])
                            for value in selected:wait_ready(value['namespace'],value['deployment'],value['replicas'])
                            if roles==('objects','temporal'):services_ready()
                        state.update(restored_at=time.time(),restoration='all original replicas ready');save();break
                    except Exception as error:
                        state['restoration_error']=str(error);save()
                    print('RESTORE INCOMPLETE; lock retained; retrying authorized restoration',flush=True);time.sleep(5)
            state['released_at']=time.time();save()
            fcntl.flock(lock,fcntl.LOCK_UN)
            print('T09a quiescent; original environments restored; capacity lock released',flush=True)

if __name__=='__main__':main()
