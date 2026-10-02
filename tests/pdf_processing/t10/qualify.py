"""One bounded package qualification; fresh namespace/prefix, retained shared bytes.

Uses existing Temporal/MinIO in pdf-t09a-validation. Mutates only newly created T10
workers and one UID-checked MinIO Pod during a quiescent PVC-preserving replacement.
Run once with a new namespace/out; failures stop and retain evidence. No run retry.
"""
import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
PYTHON = '/experiment/.venv/bin/python'
NODE = 'internal-a2a-vs6-local-worker'
SHARED = 'pdf-t09a-validation'


def command(argv, data=None, timeout=120):
    return subprocess.check_output(argv, input=data, text=True, timeout=timeout)


def main(args):
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    ns = args.namespace
    def k(*argv, data=None, namespace=ns, timeout=120):
        return command(['kubectl', '--request-timeout=15s', '-n', namespace, *argv], data, timeout)
    def save(name, value):
        (out/(name+'.json')).write_text(json.dumps(value, indent=2)+'\n')
    def apply(value):
        with mutation_lock:
            assert not aborting.is_set(), monitor_errors
            return k('apply', '-f', '-', data=json.dumps(value))
    def driver(script, *argv, timeout=360):
        process=subprocess.Popen(['kubectl','--request-timeout=15s','-n',ns,'exec','coordinator','--',PYTHON,script,*argv],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        started=time.monotonic()
        while True:
            if aborting.is_set() or time.monotonic()-started>timeout:
                process.terminate();process.wait(timeout=10)
                raise RuntimeError('Runtime guard/command deadline: '+str(monitor_errors))
            try:
                stdout,stderr=process.communicate(timeout=.2)
                if process.returncode:raise RuntimeError(stderr)
                return stdout
            except subprocess.TimeoutExpired:pass
    def verify(case, route='/tmp/route-a.json', *argv):
        result=json.loads(driver('/tmp/t10/verify.py', case, route, *argv))
        if case=='check':
            k('cp','coordinator:'+argv[1]+'/history.json',str(out/(Path(argv[1]).name+'-history.json')))
        return result
    def manage(case, route='/tmp/route-a.json', *argv):
        result=json.loads(driver('/app/manage.py', '--route', route, case, *argv))
        if case=='export':
            directory=argv[argv.index('--out')+1]
            for name in ('summary.json','processing-result.json','retained-references.json'):
                k('cp','coordinator:'+directory+'/'+name,str(out/(Path(directory).name+'-'+name)))
        return result
    def copy_file(path, target):
        k('cp', str(path), 'coordinator:'+target)
    def pod(deployment):
        rows = json.loads(k('get', 'pods', '-l', 'app='+deployment, '-o', 'json'))['items']
        return next(p for p in rows if not p['metadata'].get('deletionTimestamp'))
    def ready(deployment):
        assert not aborting.is_set(), monitor_errors
        k('rollout', 'status', 'deployment/'+deployment, '--timeout=90s')
        p = pod(deployment)
        if deployment.endswith('-activity'):
            until=time.monotonic()+20
            while True:
                logs=k('logs',p['metadata']['name'])
                if '"event": "bootstrap_verified"' in logs and '"event": "memory_policy_verified"' in logs:break
                assert time.monotonic()<until and not aborting.is_set(), 'Activity startup policy/bootstrap missing'
                time.sleep(.2)
            (out/(deployment+'-'+p['metadata']['uid']+'-startup.log')).write_text(logs)
        save(deployment+'-pod-'+p['metadata']['uid'], {'name': p['metadata']['name'],
            'uid': p['metadata']['uid'], 'node': p['spec']['nodeName'],
            'containers': p['status']['containerStatuses']})
        return p
    def scale(deployment, value):
        with mutation_lock:
            if value:assert not aborting.is_set(), monitor_errors
            k('scale', 'deployment/'+deployment, '--replicas='+str(value))
    owned = []
    monitors = []
    monitor_errors = []
    aborting = threading.Event()
    ending = threading.Event()
    mutation_lock = threading.RLock()
    object_monitor = None
    success = False
    runtime_deadline = time.monotonic()+1500
    def abort(reason):
        with mutation_lock:
            if aborting.is_set():return
            monitor_errors.append(str(reason)); aborting.set()
            # Fence polling and physically stop only containers in this owned namespace.
            rows=json.loads(k('get','pods','-o','json'))['items']
            for name in owned:
                try:scale(name,0)
                except Exception as error:monitor_errors.append(str(error))
            for p in rows:
                if p['metadata'].get('labels',{}).get('app') in owned:
                    for c in p['status'].get('containerStatuses',[]):
                        if c.get('containerID'):
                            try:command(['docker','exec',p['spec']['nodeName'],'crictl','stop','--timeout=1',c['containerID'].split('://')[1]],timeout=20)
                            except Exception as error:monitor_errors.append(str(error))
    def observe(label):
        log = (out/(label+'-samples.jsonl')).open('w')
        process = subprocess.Popen(['docker','exec',NODE,'python3','-u','-c',
            (ROOT/'tests/pdf_processing/t10/sample.py').read_text(),ns],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ready_sample = threading.Event()
        state = {'last':time.monotonic(), 'pid':None, 'start_ticks':None, 'previous':None, 'ended':False}
        def read():
            try:
                assert process.stdout is not None
                first = None
                for line in process.stdout:
                    row = json.loads(line)
                    log.write(line); log.flush()
                    state['last']=time.monotonic()
                    if row.get('event')=='start':state['pid']=row['pid'];state['start_ticks']=row['start_ticks'];continue
                    if row.get('event')=='end':state['ended']=True;continue
                    if state['previous'] is not None:
                        assert 0<row['time']-state['previous']<=1, 'Worker sample gap'
                    state['previous']=row['time']
                    first = first or row
                    assert row['available'] >= 1610612736, 'VM floor crossed'
                    assert row['vm_oom_kill'] == first['vm_oom_kill'], 'VM OOM'
                    assert len(row['parser_pids']) <= 1, 'Second parser admitted'
                    for worker in row['workers']:
                        assert worker['memory_max']==5368709120, 'Worker hard limit changed'
                        assert worker['memory_current']<=4294967296, '4GiB sample guard crossed'
                        assert worker['full_avg10']==0, 'Worker full PSI'
                        assert all(worker['memory_events'].get(k,0)==0 for k in ('oom','oom_kill','oom_group_kill')), 'Worker OOM'
                    ready_sample.set()
                assert ending.is_set() and state['ended'], 'Unexpected observer EOF'
            except BaseException as error:
                abort(error);ready_sample.set()
                # A rejecting sample is retained; keep draining through the end marker.
                if process.stdout is not None:
                    for line in process.stdout:
                        log.write(line);log.flush()
                        row=json.loads(line)
                        if row.get('event')=='end':state['ended']=True
            finally:
                log.close()
        def watch():
            while not ending.wait(.1):
                if time.monotonic()>runtime_deadline-300:abort('Cleanup reserve reached');return
                if time.monotonic()-state['last']>1:abort('Worker telemetry stalled');return
                if object_monitor is not None:
                    if object_monitor.error is not None:abort(object_monitor.error);return
                    if object_monitor.samples and object_monitor.samples[-1]['object_full_avg10']>0:
                        abort('Sustained object full PSI');return
        reader = threading.Thread(target=read, daemon=True)
        watcher=threading.Thread(target=watch,daemon=True)
        monitors.append((process, reader, watcher, state))
        reader.start()
        assert ready_sample.wait(20) and not monitor_errors, monitor_errors
        watcher.start()
    with open('/private/tmp/data-ingestion-pdf-qualification.lock', 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not k('get', 'namespace', ns, '--ignore-not-found', '-o', 'name')
        initial_deployments = json.loads(command(['kubectl', 'get', 'deployments', '-A', '-o', 'json']))
        historical = [d for d in initial_deployments['items'] if d['metadata']['namespace'].startswith('pdf-')]
        save('historical-deployments-before', [{'namespace': d['metadata']['namespace'],
            'name': d['metadata']['name'], 'uid': d['metadata']['uid'], 'replicas': d['spec']['replicas'],
            'spec_sha256': hashlib.sha256(json.dumps(d['spec'], sort_keys=True).encode()).hexdigest()} for d in historical])
        assert all(d['spec']['replicas'] == 0 for d in historical
                   if not (d['metadata']['namespace'] == SHARED and d['metadata']['name'] in ('objects','temporal','workflows')))
        spec = importlib.util.spec_from_file_location('release', ROOT/'deploy/pdf-processing/release.py')
        assert spec is not None and spec.loader is not None
        renderer = importlib.util.module_from_spec(spec); spec.loader.exec_module(renderer)
        profile = json.loads((ROOT/'deploy/pdf-processing/profiles/selected-native-v1.json').read_text())
        bundle = renderer.render(profile, args.image, ns, 't10-core-a', 't09a', args.prefix,
            'temporal.'+SHARED+':7233', 'http://objects.'+SHARED+':9000', 'store-access')
        for item in bundle['items'][1:]:
            item['spec']['template']['spec']['nodeName'] = NODE
            item['spec']['template']['spec']['containers'][0]['env'].append({'name':'T10_QUALIFICATION_NAMESPACE','value':ns})
        route = json.loads(bundle['items'][0]['data']['route.json'])
        route_path = out/'route-a.json'; route_path.write_text(json.dumps(route, indent=2))
        save('deployment-a', bundle)
        evidence=args.resume_evidence or out
        if args.resume_evidence:
            assert json.loads((evidence/'route-a.json').read_text())==route, 'Resume changes immutable release'
            prior_cleanup=json.loads((evidence/'cleanup.json').read_text())
            assert prior_cleanup['pods']==[] and not prior_cleanup['monitor_errors'] and not prior_cleanup['cleanup_errors']
            for case in ('normal-ten','normal-multiple','replay-ten','replay-multiple','loss-assembly','loss-finalize'):
                result=json.loads((evidence/(case+'.json')).read_text())
                summary=result.get('result',result)['summary']
                assert summary['processing_complete'] and summary['status']=='complete'
            save('reused-evidence',{'path':str(evidence),'route_id':route['id'],
                'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence.glob('*.json')}})
        try:
            apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': ns}})
            secret = json.loads(k('get', 'secret', 'store-access', '-o', 'json', namespace=SHARED))
            apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'store-access', 'namespace': ns}, 'data': secret['data']})
            apply(bundle)
            coordinator = {'apiVersion':'v1', 'kind':'Pod', 'metadata':{'name':'coordinator','namespace':ns},
                'spec': {'nodeName':NODE, 'automountServiceAccountToken':False,
                    'terminationGracePeriodSeconds':5,
                    'containers':[{'name':'client','image':args.image,'imagePullPolicy':'IfNotPresent',
                        'command':[PYTHON,'-c','import time;time.sleep(3600)'],
                        'envFrom':[{'secretRef':{'name':'store-access'}}],
                        'env':[{'name':'TEMPORAL_ADDRESS','value':'temporal.'+SHARED+':7233'},
                               {'name':'OBJECT_ENDPOINT','value':'http://objects.'+SHARED+':9000'}]}]}}
            apply(coordinator); k('wait','pod/coordinator','--for=condition=Ready','--timeout=90s')
            k('exec','coordinator','--','mkdir','-p','/tmp/t10')
            for path in (ROOT/'tests/pdf_processing/t10/verify.py', ROOT/'tests/pdf_processing/t03/verify_store.py'):
                copy_file(path, '/tmp/t10/'+path.name)
            copy_file(route_path, '/tmp/route-a.json')
            save('idle-before', verify('idle'))
            if not args.resume_evidence:
                assert not json.loads(driver('-c', 'import boto3,json;print(json.dumps(boto3.client("s3",endpoint_url="http://objects.'+SHARED+':9000").list_objects_v2(Bucket="t09a",Prefix='+repr(route['binding']['store']['prefix'])+',MaxKeys=1).get("Contents",[])))'))
            admission = []
            for _ in range(30):
                row = json.loads(driver('-c', 'import psutil,json;print(json.dumps({"available":psutil.virtual_memory().available,"psi":open("/proc/pressure/memory").read()}))'))
                assert row['available'] >= 4831838208 and 'full avg10=0.00' in row['psi'], row
                admission.append(row); time.sleep(2)
            save('admission', admission)
            sys.path.insert(0,str(ROOT/'tests/pdf_processing/q04'))
            from sentinel import object_monitor_bh, object_cgroup_probe_db
            object_monitor_bh.probe=object_cgroup_probe_db
            object_monitor_bh.RUN_ID=ns
            class Kube:
                def json(self,*argv):return json.loads(k(*argv,'-o','json',namespace=SHARED))
            object_monitor=object_monitor_bh.ObjectMonitor(Kube(),out/'object-samples.jsonl',1073741824)
            object_monitor.start(seconds=1500)
            observe('runtime')
            def workers_gone():
                until=time.monotonic()+90
                while any(p['metadata']['name']!='coordinator' for p in json.loads(k('get','pods','-o','json'))['items']):
                    assert time.monotonic()<until and not monitor_errors
                    time.sleep(.5)
            if args.store_only_evidence:
                prior=args.store_only_evidence
                clean=json.loads((prior/'cleanup.json').read_text())
                assert clean['pods']==[] and not clean['monitor_errors'] and not clean['cleanup_errors']
                assert json.loads((prior/'route-a.json').read_text())==route
                assert json.loads((prior/'reviewed-08.json').read_text())['summary']['processing_complete']
                assert json.loads((prior/'late-a-recovered.json').read_text())['summary']['processing_complete']
                copy_file(prior/'route-b.json','/tmp/route-b.json')
                retained_workflow=json.loads((evidence/'normal-multiple-submitted.json').read_text())['workflow_id']
                identity=json.loads((prior/'export-reviewed-08-processing-result.json').read_text())['source']['request_id']
                names=[]
                save('reused-complete-interactions',{'path':str(prior),'workers_activated':False})
            else:
                names = [d['metadata']['name'] for d in bundle['items'][1:]]
                owned.extend(names)
                for name in names: scale(name, 1); ready(name)
                observed_deadline=time.monotonic()+10
                while True:
                    rows=(out/'runtime-samples.jsonl').read_text().splitlines()
                    if rows and len(json.loads(rows[-1]).get('workers',[]))==1:break
                    assert time.monotonic()<observed_deadline and not monitor_errors, 'Worker cgroup not observed'
                    time.sleep(.2)
                def run_case(case, fixture, route_file='/tmp/route-a.json'):
                    assert not aborting.is_set(),monitor_errors
                    capture = manage('capture', route_file, '--pdf', '/tmp/'+fixture+'.pdf')
                    request = {'version':3, 'completion':'required_evidence_v1', 'profile':'native-v1',
                        'request_id':ns+'-'+case, 'source_revision':'synthetic:t10:'+case, 'artifact':capture}
                    path = out/(case+'-request.json'); path.write_text(json.dumps(request,indent=2)); copy_file(path,'/tmp/request.json')
                    save(case+'-submitted', manage('submit', route_file, '--request','/tmp/request.json','--workflow-id',request['request_id']))
                    return request['request_id']
                for fixture in (() if args.resume_evidence else ('ten','multiple')):
                    copy_file(args.fixtures/(fixture+'.pdf'), '/tmp/'+fixture+'.pdf')
                    identity = run_case('normal-'+fixture, fixture)
                    save('normal-'+fixture, verify('check', '/tmp/route-a.json', identity, '/tmp/normal-'+fixture, fixture))
                    save('export-'+fixture, manage('export', '/tmp/route-a.json', '--workflow-id',identity,'--out','/tmp/export-'+fixture))
                    replay = identity+'-replay'
                    save('replay-'+fixture+'-submitted', manage('submit','/tmp/route-a.json','--request','/tmp/request.json','--workflow-id',replay))
                    result = verify('check','/tmp/route-a.json',replay,'/tmp/replay-'+fixture,fixture)
                    assert all(s['reused'] for s in result['summary']['steps']), 'Exact replay recomputed completed work'
                    save('replay-'+fixture,result)
                    assert not monitor_errors, monitor_errors
                if not args.resume_evidence:
                    invalid=json.loads((out/'normal-multiple-request.json').read_text())
                    invalid['request_id']=ns+'-invalid';invalid['artifact']['sha256']='f'*64
                    invalid_path=out/'invalid-request.json';invalid_path.write_text(json.dumps(invalid));copy_file(invalid_path,'/tmp/invalid.json')
                    save('invalid-submitted',manage('submit','/tmp/route-a.json','--request','/tmp/invalid.json','--workflow-id',invalid['request_id']))
                    save('invalid-result',verify('failure','/tmp/route-a.json',invalid['request_id']))
                for mode, fixture in (() if args.resume_evidence else (('assembly','ten'), ('finalize','multiple'))):
                    fault = copy.deepcopy(bundle['items'][2])
                    fault['spec']['replicas'] = 1
                    fault_cm = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'fault-'+mode,'namespace':ns},
                        'immutable':True,'data':{'fault_worker.py':(ROOT/'tests/pdf_processing/t10/fault_worker.py').read_text()}}
                    apply(fault_cm)
                    pod_spec = fault['spec']['template']['spec']; c = pod_spec['containers'][0]
                    c['command']=[PYTHON,'/fault/fault_worker.py']; c['env'].append({'name':'T10_FAULT','value':mode})
                    c['volumeMounts'].append({'name':'fault','mountPath':'/fault','readOnly':True})
                    pod_spec['volumes'].append({'name':'fault','configMap':{'name':'fault-'+mode}})
                    apply(fault); old = ready(names[1])
                    identity = run_case('loss-'+mode, fixture)
                    deadline = time.monotonic()+120
                    while True:
                        raw = k('exec',old['metadata']['name'],'--',PYTHON,'-c','from pathlib import Path;print(Path("/scratch/fault.json").read_text() if Path("/scratch/fault.json").exists() else "")')
                        if raw.strip(): break
                        assert time.monotonic()<deadline and not monitor_errors, monitor_errors
                        time.sleep(.5)
                    marker = json.loads(raw); save(mode+'-unregistered', verify('unregistered','/tmp/route-a.json',marker['operation']))
                    save(mode+'-progress', manage('status','/tmp/route-a.json','--workflow-id',identity))
                    normal = copy.deepcopy(bundle['items'][2]); normal['spec']['replicas']=1
                    started = time.monotonic(); apply(normal); new = ready(names[1])
                    assert new['metadata']['uid'] != old['metadata']['uid']
                    old_container = old['status']['containerStatuses'][0]['containerID'].split('://')[1]
                    current = json.loads(command(['docker','exec',NODE,'crictl','ps','-o','json']))
                    assert old_container not in [c['id'] for c in current['containers']]
                    result = verify('check','/tmp/route-a.json',identity,'/tmp/loss-'+mode,fixture)
                    save('loss-'+mode+'-observed',result)
                    assert 2 in result['activity_attempts'], result['activity_attempts']
                    assert all(s['attempt']==1 for s in result['activity_starts'] if s['stage']=='group'), 'Committed page work repeated after cross-stage loss'
                    assert any(s=={'stage':mode,'attempt':2} for s in result['activity_starts'])
                    save('loss-'+mode, {'replacement_seconds':time.monotonic()-started,'old_uid':old['metadata']['uid'],
                        'new_uid':new['metadata']['uid'],'old_container_stopped':True,'result':result})
                    assert not monitor_errors, monitor_errors
                if args.restart_evidence:
                    prior=args.restart_evidence
                    assert json.loads((prior/'route-a.json').read_text())==route
                    clean=json.loads((prior/'cleanup.json').read_text())
                    assert clean['pods']==[] and not clean['monitor_errors'] and not clean['cleanup_errors']
                    restart=json.loads((prior/'container-restart.json').read_text())
                    assert restart['after']['restartCount']==restart['before']['restartCount']+1 and restart['scratch']==['keep.txt']
                    save('reused-restart-evidence',{'path':str(prior),'container_restart':restart,
                        'checked_export':json.loads((prior/'export-after-worker-restart.json').read_text())})
                    retained_workflow=json.loads((evidence/'normal-multiple-submitted.json').read_text())['workflow_id']
                else:
                    old=pod(names[1]);old_status=old['status']['containerStatuses'][0]
                    k('exec',old['metadata']['name'],'--',PYTHON,'-c',
                        'from pathlib import Path;[(Path("/scratch")/n).mkdir() for n in ("preflight-stale","activity-stale","ocr-stale")];Path("/scratch/keep.txt").write_text("owned sentinel")')
                    command(['docker','exec',NODE,'crictl','stop','--timeout=1',old_status['containerID'].split('://')[1]])
                    restart_deadline=time.monotonic()+120
                    while True:
                        current=pod(names[1]);status=current['status']['containerStatuses'][0]
                        if status['restartCount']==old_status['restartCount']+1 and status.get('ready'):break
                        assert time.monotonic()<restart_deadline and not monitor_errors
                        time.sleep(.5)
                    assert current['metadata']['uid']==old['metadata']['uid']
                    # Readiness is container readiness; wait separately for bootstrap/startup cleanup.
                    cleanup_deadline=time.monotonic()+30
                    while True:
                        scratch=json.loads(k('exec',current['metadata']['name'],'--',PYTHON,'-c',
                            'from pathlib import Path;import json;print(json.dumps([p.name for p in Path("/scratch").iterdir()]))'))
                        if scratch==['keep.txt']:break
                        assert time.monotonic()<cleanup_deadline
                        time.sleep(.2)
                    save('container-restart',{'pod_uid':current['metadata']['uid'],'before':old_status,'after':status,'scratch':scratch})
                    retained_workflow=json.loads((evidence/'normal-multiple-submitted.json').read_text())['workflow_id']
                    save('export-after-worker-restart',manage('export','/tmp/route-a.json','--workflow-id',retained_workflow,'--out','/tmp/export-after-worker-restart'))
                # Source-reviewed profile B is immutable, and only replaces A after quiescence.
                save('idle-before-rollout',verify('idle'))
                for name in names:scale(name,0)
                workers_gone()
                accepted=json.loads(args.accepted_config.read_text())['profiles']['08']
                if args.reviewed_evidence:
                    prior=args.reviewed_evidence
                    clean=json.loads((prior/'cleanup.json').read_text())
                    assert clean['pods']==[] and not clean['monitor_errors'] and not clean['cleanup_errors']
                    prior_bundle=json.loads((prior/'deployment-b.json').read_text())
                    profile_b=json.loads(prior_bundle['items'][0]['data']['profile.json'])
                    assert json.loads((prior/'route-a.json').read_text())==route
                    save('reused-reviewed-evidence',{'path':str(prior),'previous_route':json.loads((prior/'route-b.json').read_text())['id']})
                else:
                    profile_b=copy.deepcopy(accepted);profile_b.pop('release',None)
                    copy_file(args.accepted_bundle/'originals/08.pdf','/tmp/original-08.pdf')
                    original=manage('capture','/tmp/route-a.json','--pdf','/tmp/original-08.pdf')
                    review=next(iter(profile_b['content_evidence']['reviews'].values()))
                    assert original['sha256']==review['original_source']['artifact']['sha256']
                    review['original_source']['artifact']=original
                    save('original-source-bootstrap',{'retained_historical_reference':accepted['content_evidence']['reviews'],
                        'release_capture':original,'historical_bytes_deleted':False})
                assert profile_b['method']==profile['method'], 'Different accepted parser method'
                bundle_b=renderer.render(profile_b,args.image,ns,'t10-core-b','t09a',args.prefix,
                    'temporal.'+SHARED+':7233','http://objects.'+SHARED+':9000','store-access')
                for item in bundle_b['items'][1:]:
                    item['spec']['template']['spec']['nodeName']=NODE
                    item['spec']['template']['spec']['containers'][0]['env'].append({'name':'T10_QUALIFICATION_NAMESPACE','value':ns})
                route_b=json.loads(bundle_b['items'][0]['data']['route.json'])
                route_b_path=out/'route-b.json';route_b_path.write_text(json.dumps(route_b,indent=2))
                save('deployment-b',bundle_b);apply(bundle_b);copy_file(route_b_path,'/tmp/route-b.json')
                names_b=[d['metadata']['name'] for d in bundle_b['items'][1:]];owned.extend(names_b)
                for name in names_b:scale(name,1);ready(name)
                # A queued submission must remain unconsumed by B's different release queues.
                late=json.loads((evidence/'normal-ten-request.json').read_text());late['request_id']=ns+'-late-a'
                late_path=out/'late-a-request.json';late_path.write_text(json.dumps(late));copy_file(late_path,'/tmp/late-a.json')
                save('late-a-submitted',manage('submit','/tmp/route-a.json','--request','/tmp/late-a.json','--workflow-id',late['request_id']))
                time.sleep(5)
                save('late-a-fenced',verify('held','/tmp/route-a.json',late['request_id']))
                copy_file(args.accepted_bundle/'fixtures/08.pdf','/tmp/08.pdf')
                copy_file(args.accepted_document,'/tmp/aima-reference.json')
                identity=(json.loads((args.reviewed_evidence/'reviewed-08-submitted.json').read_text())['workflow_id']
                    if args.reviewed_evidence else run_case('reviewed-08','08','/tmp/route-b.json'))
                save('reviewed-08',verify('check','/tmp/route-b.json',identity,'/tmp/reviewed-08','08'))
                save('export-reviewed-08',manage('export','/tmp/route-b.json','--workflow-id',identity,'--out','/tmp/export-reviewed-08'))
                for name in names_b:scale(name,0)
                workers_gone()
                for name in names:scale(name,1);ready(name)
                save('late-a-recovered',verify('check','/tmp/route-a.json',late['request_id'],'/tmp/late-a','ten'))
            save('store-contract', verify('store'))
            save('inventory', verify('inventory'))
            save('idle-after', verify('idle'))
            for name in names:scale(name,0)
            workers_gone()
            # Retain the Deployment, PVC and every object version; replace only its Pod.
            objects=json.loads(k('get','deployment/objects','-o','json',namespace=SHARED))
            object_pods=json.loads(k('get','pods','-l','app=pdf-objects','-o','json',namespace=SHARED))['items']
            assert len(object_pods)==1 and not object_pods[0]['metadata'].get('deletionTimestamp')
            old_object=object_pods[0]
            save('object-observer-before-replacement',object_monitor.stop());object_monitor=None
            replacement_started=time.monotonic()
            assert json.loads(k('get','pod',old_object['metadata']['name'],'-o','json',namespace=SHARED))['metadata']['uid']==old_object['metadata']['uid']
            k('delete','--raw','/api/v1/namespaces/'+SHARED+'/pods/'+old_object['metadata']['name'],'-f','-',
                data=json.dumps({'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':old_object['metadata']['uid']}}),namespace=SHARED)
            k('wait','pod/'+old_object['metadata']['name'],'--for=delete','--timeout=60s',namespace=SHARED)
            k('rollout','status','deployment/objects','--timeout=90s',namespace=SHARED)
            new_object=json.loads(k('get','pods','-l','app=pdf-objects','-o','json',namespace=SHARED))['items'][0]
            assert new_object['metadata']['uid']!=old_object['metadata']['uid']
            after_objects=json.loads(k('get','deployment/objects','-o','json',namespace=SHARED))
            assert after_objects['metadata']['uid']==objects['metadata']['uid'] and after_objects['spec']==objects['spec']
            replacement_seconds=time.monotonic()-replacement_started
            assert replacement_seconds<=120, 'Object Pod replacement exceeded retained 120s bound'
            object_monitor=object_monitor_bh.ObjectMonitor(Kube(),out/'object-after-samples.jsonl',1073741824)
            object_monitor.start(seconds=300)
            save('object-pod-replacement',{'old_uid':old_object['metadata']['uid'],'new_uid':new_object['metadata']['uid'],
                'deployment_uid':objects['metadata']['uid'],'volumes':new_object['spec']['volumes'],'workers_quiescent':True})
            save('object-replacement-bound',{'seconds':replacement_seconds,'bound_seconds':120})
            save('export-after-store-restart',manage('export','/tmp/route-a.json','--workflow-id',retained_workflow,'--out','/tmp/export-after-store-restart'))
            save('export-reviewed-after-store-restart',manage('export','/tmp/route-b.json','--workflow-id',identity,'--out','/tmp/export-reviewed-after-store-restart'))
            print('PASS: package rollout/loss/restart, retained references and actual Temporal/store seam',flush=True)
            success = True
        finally:
            cleanup_errors=[]
            for name in owned:
                try:scale(name,0)
                except Exception as error:cleanup_errors.append(str(error))
            try:
              if k('get','pod','coordinator','--ignore-not-found','-o','name'):
                if not success:
                    cleanup_script='''import asyncio,os,json
from temporalio.client import Client
async def main():
 c=await Client.connect(os.environ['TEMPORAL_ADDRESS'])
 stopped=[]
 async for e in c.list_workflows("ExecutionStatus = 'Running'"):
  if e.id.startswith('''+repr(ns+'-')+'''):
   await c.get_workflow_handle(e.id).terminate('T10 owned qualification failed; preserve partial evidence')
   stopped.append(e.id)
 print(json.dumps(stopped))
asyncio.run(main())
'''
                    save('failed-owned-workflows',json.loads(k('exec','coordinator','--',PYTHON,'-c',cleanup_script)))
                deadline=time.monotonic()+90
                while True:
                    rows=json.loads(k('get','pods','-o','json'))['items']
                    if all(p['metadata']['name']=='coordinator' for p in rows):break
                    assert time.monotonic()<deadline, 'Owned workers remain'
                    time.sleep(.5)
                k('delete','pod','coordinator','--wait=true','--timeout=30s')
            except Exception as error:cleanup_errors.append(str(error))
            ending.set()
            for process, reader, watcher, state in monitors:
              try:
                stop_sample='''import os,signal,sys
from pathlib import Path
mode,scope,source,pid,ticks=sys.argv[1:]
matches=[]
for path in Path('/proc').glob('[0-9]*/cmdline'):
 try:argv=path.read_bytes().split(bytes([0]))
 except (FileNotFoundError,ProcessLookupError):continue
 if argv[-3:]==[source.encode(),scope.encode(),b'']:matches.append(int(path.parent.name))
assert len(matches)<=1
if mode=='verify':assert not matches,matches
elif matches:
 p=matches[0]
 if pid!='None':
  assert p==int(pid) and int(Path(f'/proc/{p}/stat').read_text().rsplit(') ',1)[1].split()[19])==int(ticks)
 os.kill(p,signal.SIGTERM)
'''
                sample_scope=[ns,(ROOT/'tests/pdf_processing/t10/sample.py').read_text(),str(state['pid']),str(state['start_ticks'])]
                command(['docker','exec',NODE,'python3','-c',stop_sample,'stop',*sample_scope])
                process.wait(timeout=10);reader.join(timeout=10)
                if watcher.ident is not None:watcher.join(timeout=10)
                command(['docker','exec',NODE,'python3','-c',stop_sample,'verify',*sample_scope])
                assert process.returncode==0 and state['ended'] and not reader.is_alive(), 'Observer cleanup incomplete'
              except Exception as error:cleanup_errors.append(str(error))
            if object_monitor is not None:
                try:save('object-observer',object_monitor.stop())
                except Exception as error:cleanup_errors.append(str(error))
            save('cleanup', {'owned_workers_off':owned,'pods':json.loads(k('get','pods','-o','json'))['items'],
                'shared_bytes_deleted':False,'monitor_errors':monitor_errors,'cleanup_errors':cleanup_errors})
            final_deployments=json.loads(command(['kubectl','get','deployments','-A','-o','json']))['items']
            for before in historical:
                after=next(d for d in final_deployments if d['metadata']['uid']==before['metadata']['uid'])
                assert after['spec']==before['spec'], 'Historical Deployment changed'
            save('historical-deployments-preserved',{'count':len(historical),'specs_and_uids_unchanged':True})
            assert not monitor_errors and not cleanup_errors,(monitor_errors,cleanup_errors)


if __name__ == '__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('image','namespace','prefix'):cli.add_argument('--'+name,required=True)
    cli.add_argument('--out',type=Path,required=True)
    cli.add_argument('--fixtures',type=Path,required=True)
    cli.add_argument('--accepted-config',type=Path,required=True)
    cli.add_argument('--accepted-bundle',type=Path,required=True)
    cli.add_argument('--accepted-document',type=Path,required=True,help='Latest accepted #45 full AIMA document, not the older bundle reference')
    cli.add_argument('--resume-evidence',type=Path,help='Reuse checked same-route successes after proof of complete owned cleanup')
    cli.add_argument('--restart-evidence',type=Path,help='Reuse checked same-route container restart/export after complete owned cleanup')
    cli.add_argument('--reviewed-evidence',type=Path,help='Resolve an already complete reviewed-profile result without rerunning inference')
    cli.add_argument('--store-only-evidence',type=Path,help='Reuse complete routing/profile evidence; run only remaining store checks with workers off')
    main(cli.parse_args())
