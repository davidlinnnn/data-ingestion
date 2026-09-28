"""Host-side bounded real Pod-loss driver. Uses only pdf-t03-validation."""
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

namespace='pdf-t03-validation'
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
def kubectl(*args,**kwargs):
    return subprocess.run(['kubectl','-n',namespace,*args],check=True,**kwargs)
for mode in ('processing','upload','ack'):
    case=mode+'-'+uuid.uuid4().hex
    log=(out/(mode+'.json')).open('w')
    process=subprocess.Popen(['kubectl','-n',namespace,'exec','coordinator','--',
        '/experiment/.venv/bin/python','/driver/verify_pdf.py','--case',case,'--mode',mode],stdout=log)
    probe="import boto3; c=boto3.client('s3',endpoint_url='http://objects:9000'); r=c.list_objects_v2(Bucket='t03',Prefix='final/faults/"+case+"/ready.json'); print(len(r.get('Contents',[])))"
    deadline=time.monotonic()+180
    killed=None
    try:
        while time.monotonic()<deadline:
            if process.poll() is not None:
                raise RuntimeError('PDF driver exited before fault was observed')
            ready=kubectl('exec','coordinator','--','/experiment/.venv/bin/python','-c',probe,
                          capture_output=True,text=True).stdout.strip()
            if ready=='1':
                pods=json.loads(kubectl('get','pods','-l','app=t03-activities','-o','json',capture_output=True,text=True).stdout)
                assert len(pods['items'])==1
                pod=pods['items'][0]
                killed={'name':pod['metadata']['name'],'uid':pod['metadata']['uid'],'time':time.time(),'case':case}
                kubectl('delete','pod',killed['name'],'--grace-period=0','--force')
                break
            time.sleep(.5)
        if killed is None:
            raise RuntimeError('No native/upload/ack fault marker within bound')
        process.wait(timeout=180)
        assert process.returncode==0
        (out/(mode+'-pod.json')).write_text(json.dumps(killed,indent=2))
    finally:
        if process.poll() is None: process.terminate()
        log.close()
    print(mode+' passed',flush=True)
