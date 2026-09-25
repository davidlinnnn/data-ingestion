"""Single approved Keynote window. No retries or expanded pause scope."""
import concurrent.futures
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[4]
OUT=Path('/private/tmp/q04-keynote-window-20260916-a')
PACKAGE=Path('/private/tmp/q04-keynote-18be1b3-20260916-a-package')
REMOTE='/tmp/q04-keynote-18be1b3-20260916-a'
PYTHON='/experiment/.venv/bin/python'
NS='pdf-t09a-validation'
CONTEXT='kind-internal-a2a-vs6-local'
PREFIX='q04/keynote-18be1b3-20260916-a/'
BASE=['kubectl','--context',CONTEXT,'--request-timeout=15s']
CANDIDATES=json.loads((REPO/'tests/pdf_processing/q04/preflight/evidence/pause-candidates.json').read_text())['deployments']
assert {(r['namespace'],r['name']) for r in CANDIDATES}=={(f'pdf-t{n:02}-validation',role) for n in range(3,8) for role in ('activities','workflows','objects','temporal')} and len(CANDIDATES)==20
STATE={'phase':'preparing','mutations':[],'errors':[]}


def save():
    (OUT/'lease-state.json').write_text(json.dumps(STATE,indent=2)+'\n')
    print(json.dumps({'time':time.time(),'phase':STATE['phase'],'errors':STATE['errors']}),flush=True)


def k(ns,*args,**kwargs):
    return subprocess.check_output(BASE+['-n',ns,*args],timeout=kwargs.pop('timeout',30),**kwargs)


def remote(script,timeout=60):
    return k(NS,'exec','-i','coordinator','--','env','PYTHONDONTWRITEBYTECODE=1',PYTHON,'-',input=script.encode(),timeout=timeout)


def write_remote(path,data):
    remote('from pathlib import Path\nPath('+repr(path)+').open("xb").write('+repr(data)+')\n')


def health(name):
    script=(REPO/'tests/pdf_processing/q04/preflight/remote_probe.py').read_text()
    value=json.loads(remote(script+'\nprint(json.dumps(asyncio.run(services({"prefix":'+repr(PREFIX)+'}))))\n',timeout=190))
    (OUT/name).write_text(json.dumps(value,indent=2))
    for row in value['namespaces']:
        assert row.get('query_status')=='complete' and row['temporal_health'] and not row['running'] and row['object_ready']==200,row
    return value


def scale(row,replicas):
    obj=json.loads(k(row['namespace'],'get','deployment',row['name'],'-o','json'))
    assert obj['metadata']['uid']==row['uid'],'Deployment UID changed'
    k(row['namespace'],'scale','deployment/'+row['name'],'--replicas='+str(replicas),
      '--current-replicas='+str(obj['spec']['replicas']),'--resource-version='+obj['metadata']['resourceVersion'])


def wait_deployments(rows,ready,deadline):
    while True:
        pending=[]
        for row in rows:
            obj=json.loads(k(row['namespace'],'get','deployment',row['name'],'-o','json'))
            assert obj['metadata']['uid']==row['uid']
            n=row['replicas'] if ready else 0
            if obj['spec']['replicas']!=n or obj['status'].get('readyReplicas',0)!=n or obj['status'].get('replicas',0)!=n:pending.append(row['name'])
        if not pending:return
        assert time.time()<deadline,('Deployment readiness deadline',pending)
        time.sleep(2)


def absent_runtime_once(rows):
    allowed={(r['namespace'],r['name']) for r in rows}
    pods=json.loads(k(NS,'get','pods','-A','-o','json'))['items']
    matches=[p['metadata']['name'] for p in pods if any(p['metadata']['namespace']==ns and p['metadata']['name'].startswith(role+'-') for ns,role in allowed)]
    assert not matches,('old service Pods remain',matches)
    nodes=json.loads(k(NS,'get','nodes','-o','json'))['items']
    found=[]
    for node in nodes:
        value=json.loads(subprocess.check_output(['docker','exec',node['metadata']['name'],'crictl','ps','--state','Running','-o','json'],timeout=20))
        for c in value['containers']:
            labels=c.get('labels',{})
            if any(labels.get('io.kubernetes.pod.namespace')==ns and labels.get('io.kubernetes.pod.name','').startswith(role+'-') for ns,role in allowed):found.append(c['id'])
    assert not found,('old service containers remain',found)


def absent_runtime(rows):
    deadline=time.time()+60
    while True:
        try:return absent_runtime_once(rows)
        except AssertionError:
            if time.time()>=deadline:raise
            time.sleep(2)


def stage():
    manifest=json.loads((PACKAGE/'package.json').read_text())
    for name,digest in manifest['archives'].items():assert hashlib.sha256((PACKAGE/name).read_bytes()).hexdigest()==digest
    uid=k(NS,'get','pod','coordinator','-o','jsonpath={.metadata.uid}').decode()
    assert uid=='39c4bf45-45ae-4646-8d7b-ec47b2c61785'
    k(NS,'exec','coordinator','--','mkdir',REMOTE)
    k(NS,'exec','coordinator','--','mkdir',REMOTE+'/code',REMOTE+'/inputs',REMOTE+'/logs')
    for name,folder in [('repo.tar','code'),('inputs.tar','inputs')]:
        with (PACKAGE/name).open('rb') as stream:subprocess.run(BASE+['-n',NS,'exec','-i','coordinator','--','tar','--keep-old-files','--no-same-owner','-C',REMOTE+'/'+folder,'-xf','-'],stdin=stream,check=True,timeout=60)


def restore():
    STATE['phase']='restoring';save()
    errors=[]
    for roles in [('objects','temporal'),('activities','workflows')]:
        rows=[r for r in CANDIDATES if r['name'] in roles]
        for row in rows:
            try:scale(row,row['replicas'])
            except Exception as e:errors.append({'namespace':row['namespace'],'deployment':row['name'],'error':str(e)})
        try:wait_deployments(rows,True,time.time()+120)
        except Exception as e:errors.append({'readiness':str(e)})
    (OUT/'restore-errors.json').write_text(json.dumps(errors,indent=2))
    assert not errors,errors
    health('health-after.json')
    final=[{'namespace':r['namespace'],'name':r['name'],**json.loads(k(r['namespace'],'get','deployment',r['name'],'-o','json'))['metadata']} for r in CANDIDATES]
    (OUT/'restored-identities.json').write_text(json.dumps(final,indent=2))
    STATE['restored_at']=time.time();STATE['restored']=True;save()


def main():
    OUT.mkdir()
    with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as local_lock:
        fcntl.flock(local_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        pre=json.loads(Path('/private/tmp/q04-authorized-precheck-20260916-a.json').read_text())
        assert not pre['runtime']['proposed_path_exists'] and pre['services']['proposed_prefix_objects']==0
        assert pre['runtime']['python_matches'] and pre['runtime']['platform_matches'] and not pre['runtime']['package_differences'] and not pre['runtime']['model_differences'] and not pre['runtime']['processes']
        original=[]
        for row in CANDIDATES:
            obj=json.loads(k(row['namespace'],'get','deployment',row['name'],'-o','json'))
            assert obj['metadata']['uid']==row['uid'] and obj['spec']['replicas']==row['replicas'] and obj['status'].get('readyReplicas',0)==row['replicas']
            original.append(obj)
        (OUT/'original-deployments.private.json').write_text(json.dumps(original,indent=2))
        assert health('health-before.json')['proposed_prefix_objects']==0
        probe=(REPO/'tests/pdf_processing/q04/preflight/remote_probe.py').read_text()
        bundle=json.loads(Path('/private/tmp/q04-inputs-local-v5/inputs.json').read_text())
        expected={'profile':bundle['base_profile'],'producer':bundle['producer'],'run_root':REMOTE,'prefix':PREFIX}
        fresh=json.loads(remote(probe+'\nprint(json.dumps(inventory(json.loads('+repr(json.dumps(expected))+'))))\n'))
        (OUT/'runtime-precheck.json').write_text(json.dumps(fresh,indent=2))
        assert fresh['python_matches'] and fresh['platform_matches'] and not fresh['package_differences'] and not fresh['model_differences'] and not fresh['processes'] and not fresh['proposed_path_exists']
        stage()
        holder_script='''import fcntl,json,time,os,psutil\nfrom pathlib import Path\nroot=Path(ROOT)\nwith open('/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:\n fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)\n root.joinpath('reservation.json').write_text(json.dumps({'pid':os.getpid(),'created':psutil.Process().create_time(),'acquired':time.time()}))\n while not root.joinpath('release-reservation').exists():time.sleep(.5)\n'''.replace('ROOT',repr(REMOTE))
        holder_log=(OUT/'reservation.log').open('x')
        holder=subprocess.Popen(BASE+['-n',NS,'exec','-i','coordinator','--','env','PYTHONDONTWRITEBYTECODE=1',PYTHON,'-'],stdin=subprocess.PIPE,stdout=holder_log,stderr=subprocess.STDOUT)
        assert holder.stdin is not None;holder.stdin.write(holder_script.encode());holder.stdin.close()
        acquired=False;mutated=False
        try:
            for _ in range(30):
                assert holder.poll() is None,'reservation holder failed'
                if remote('from pathlib import Path\nprint(Path('+repr(REMOTE+'/reservation.json')+').exists())\n').strip()==b'True':acquired=True;break
                time.sleep(.2)
            assert acquired
            start=time.time();capacity=json.loads((REPO/'tests/pdf_processing/q04/preflight/capacity.draft.json').read_text())
            capacity.update(status='AUTHORIZED',owner='Q04 capacity/cleanup owner in task 01a0aa2d-e84d-71c2-9bed-42ff7d40b114',
                approval_reference='Direct user authorization in this task on 2026-09-16, confirmed before14:34UTC: one20-minute process Keynote fresh/restored/replay; exact PAUSE-CANDIDATES T03-T0720Deployments; supersedes preparation-only restriction',starts_at=start,ends_at=start+1200)
            (OUT/'capacity.json').write_text(json.dumps(capacity,indent=2));write_remote(REMOTE+'/capacity.json',json.dumps(capacity).encode())
            STATE.update(started=start,ends_at=start+1200,reservation=True)
            health('health-reserved.json')
            idle=json.loads(remote("import psutil,json,os\nrows=[]\nfor p in psutil.process_iter():\n args=p.cmdline()\n if p.pid!=os.getpid() and any(any(s in a for s in ('warm_child','pdf_processing.parse','q03/','q04/','supervise.py')) for a in args):rows.append(p.pid)\nprint(json.dumps(rows))\n"))
            assert not idle,('competing coordinator work',idle)
            STATE['coordinator_idle']=True
            for roles in [('activities','workflows'),('objects','temporal')]:
                STATE['phase']='pausing-'+roles[0];save()
                rows=[r for r in CANDIDATES if r['name'] in roles]
                for row in rows:
                    assert holder.poll() is None and time.time()<start+180
                    mutated=True;STATE['mutations'].append({'namespace':row['namespace'],'deployment':row['name'],'uid':row['uid'],'original_replicas':row['replicas']});save();scale(row,0)
                wait_deployments(rows,False,start+180);absent_runtime(rows)
                if roles[0]=='activities':health('health-after-worker-pause.json')
            STATE['phase']='admission';save()
            script='''import sys,json,time\nfrom pathlib import Path\nsys.path[:0]=[ROOT+'/code/src',ROOT+'/code/tests/pdf_processing/q04']\nfrom telemetry import sample,check_sample\nfrom contracts import validate_window\nroot=Path(ROOT);limits=json.loads((root/'capacity.json').read_text());rows=[];initial=sample()\nassert initial['vm_oom_kill']==28,'OOM baseline changed'\nwith (root/'pre-admission.jsonl').open('x') as stream:\n for i in range(61):\n  row=sample();rows.append(row);stream.write(json.dumps(row)+'\\n');stream.flush();validate_window(limits,time.time());check_sample(row,initial,limits)\n  assert row['available']>=limits['admission_available_bytes'] and row['psi_full_avg10']==0,'capacity admission rejected'\n  if i<60:time.sleep(1)\nprint(json.dumps({'minimum_available':min(r['available'] for r in rows),'samples':len(rows)}))\n'''.replace('ROOT',repr(REMOTE))
            (OUT/'admission.json').write_bytes(remote(script,timeout=80))
            STATE['phase']='running-keynote';save()
            command='''set -euC
R=ROOT
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4
export PYTHONPATH="$R/code/src:$R/code/tests/pdf_processing/q04:$R/code/tests/pdf_processing/q02:$R/code/tests/pdf_processing/q03"
export PDF_QUALIFICATION_LOCK="$R/driver.lock"
cd "$R/code"
/experiment/.venv/bin/python -c "from prepare import verify_bundle;from pathlib import Path;verify_bundle(Path('$R/inputs'))"
timeout --signal=INT --kill-after=15s 60s /experiment/.venv/bin/python tests/pdf_processing/q04/q04_runtime.py --phase init --bundle "$R/inputs" --state "$R/state" --capacity "$R/capacity.json" --temporal temporal:7233 --endpoint http://objects:9000 --bucket t09a --prefix PREFIX --model-cache /experiment/PROTOTYPE-wipe-me/hf --trial-seconds 180 --capacity-approved > "$R/logs/init.log" 2>&1
timeout --signal=INT --kill-after=180s 825s /experiment/.venv/bin/python tests/pdf_processing/q04/q04_runtime.py --phase matrix --fixture 10 --bundle "$R/inputs" --state "$R/state" --capacity "$R/capacity.json" --name keynote-window-1 --trial-seconds 180 --capacity-approved > "$R/logs/matrix.log" 2>&1
'''.replace('ROOT',REMOTE).replace('PREFIX',PREFIX)
            driver=subprocess.Popen(BASE+['-n',NS,'exec','coordinator','--','sh','-c',command],stdout=(OUT/'runtime-transport.log').open('x'),stderr=subprocess.STDOUT)
            while driver.poll() is None:
                assert holder.poll() is None,'reservation transport lost'
                assert time.time()<start+900,'work window ended; enter cleanup'
                time.sleep(1)
            STATE['runtime_returncode']=driver.returncode
            assert driver.returncode==0,'sentinel driver failed; retain logs, no retry'
            STATE['sentinel_passed']=True
        except BaseException as e:
            STATE['errors'].append({'type':type(e).__name__,'reason':str(e)});STATE['phase']='failed';save()
        finally:
            # Cleanup and restoration are independent; no failed inspection skips restore.
            try:
                script=(REPO/'tests/pdf_processing/q04/sentinel/cleanup.py').read_text()
                cleanup_raw=remote(script+'\nasyncio.run(main('+repr(REMOTE)+'))\n',timeout=150)
                (OUT/'cleanup.json').write_bytes(cleanup_raw)
                STATE['cleanup_verified']=True
                if json.loads(cleanup_raw)['errors']:
                    STATE['errors'].append({'cleanup_required_intervention':json.loads(cleanup_raw)['errors']})
                    STATE['sentinel_passed']=False
            except BaseException as e:STATE['errors'].append({'cleanup':str(e)});save()
            try:
                with (OUT/'remote-evidence.tar').open('xb') as output:
                    subprocess.run(BASE+['-n',NS,'exec','coordinator','--','tar','-C',REMOTE,'--exclude=code','--exclude=inputs','-cf','-','.'],stdout=output,stderr=(OUT/'capture.log').open('x'),check=True,timeout=45)
            except BaseException as e:STATE['errors'].append({'capture':str(e)});save()
            try:
                if mutated:restore()
                else:STATE['restored']=True
            except BaseException as e:STATE['errors'].append({'restore':str(e)});save()
            if STATE.get('restored') and STATE.get('cleanup_verified'):
                write_remote(REMOTE+'/release-reservation',b'complete\n');holder.wait(timeout=10)
                STATE['reservation_released']=True
            STATE['finished']=time.time();STATE['phase']='complete' if not STATE['errors'] else 'needs-review';save()
            holder_log.close()
    return 0 if not STATE['errors'] else 1

if __name__=='__main__':sys.exit(main())
