"""Creates one bounded disposable diagnostic Pod; no PVC, inference or workflow."""
import json,subprocess,time
from pathlib import Path
from sentinel import run_yolo_pod_cgroup_j as r
p=Path(__file__).parent;k=r.Kubectl();r.verify_outer_identity(k)
r.t09a_health(k,p/'before-health.json',require_idle=True)
name='q04-j-proc-diagnostic-20260920'
spec={"apiVersion":"v1","kind":"Pod","metadata":{"name":name},"spec":{"restartPolicy":"Never","activeDeadlineSeconds":120,"nodeName":r.NODE,"automountServiceAccountToken":False,"securityContext":{"runAsUser":1000,"runAsGroup":1000},"containers":[{"name":"probe","image":"pdf-checkpoint-prototype:linux-v2","imagePullPolicy":"Never","command":["/bin/sleep","110"],"resources":{"requests":{"memory":"64Mi","cpu":"100m"},"limits":{"memory":"256Mi","cpu":"1"}},"securityContext":{"allowPrivilegeEscalation":False,"capabilities":{"drop":["ALL"]}}}]}}
created=json.loads(k.run(['create','-f','-','-o','json'],input=json.dumps(spec)));uid=created['metadata']['uid']
(p/'pod-identity.json').write_text(json.dumps({'name':name,'uid':uid,'spec':spec},indent=2)+'\n')
try:
 k.run(['wait','--for=condition=Ready','pod/'+name,'--timeout=45s'])
 probe=subprocess.Popen(k.base+['exec','-i',name,'--','/experiment/.venv/bin/python','-c',(p/'probe.py').read_text()],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 time.sleep(5)
 events=[]
 for i in range(50):
  start=time.time();k.run(['exec',name,'--','/bin/true']);events.append({'start':start,'end':time.time()});time.sleep(.2)
 stdout,stderr=probe.communicate(timeout=40)
 (p/'probe-result.json').write_text(stdout);(p/'probe-stderr.log').write_text(stderr);(p/'exec-events.json').write_text(json.dumps(events,indent=2)+'\n')
 assert probe.returncode==0
finally:
 current=k.json('get','pod',name);assert current['metadata']['uid']==uid
 k.run(['delete','--raw',f'/api/v1/namespaces/{r.NAMESPACE}/pods/{name}','-f','-'],input=json.dumps({'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':uid},'gracePeriodSeconds':0}))
 k.run(['wait','--for=delete','pod/'+name,'--timeout=30s'])
 r.verify_outer_identity(k);r.t09a_health(k,p/'after-health.json',require_idle=True)
 (p/'cleanup.json').write_text(json.dumps({'pod_uid':uid,'deleted':True,'held_32_unchanged':True})+'\n')
