"""Real systemd regression: raw low is lost; managed low survives a resource update.
Run inside the existing node. Only an owned temporary slice/service is changed.
"""
import json
from pathlib import Path
import subprocess

UNIT='q44crcontrol.slice'
SERVICE='q44crcontrol.service'
LOW=8*1024**2

def run(*args):
    return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT,timeout=15).strip()

def prop(key):
    return run('systemctl','show',UNIT,'--value','-p',key)

record={}
try:
    assert not Path('/sys/fs/cgroup/q44crcontrol.slice').exists()
    run('systemd-run','--unit='+SERVICE,'--slice='+UNIT,'--property=MemoryMax=16M',
        '--property=RuntimeMaxSec=90','/bin/sleep','90')
    path=Path('/sys/fs/cgroup')/prop('ControlGroup').lstrip('/')/'memory.low'
    assert prop('MemoryLow')=='0' and path.read_text().strip()=='0'
    path.write_text(str(LOW))
    record['raw_before_update']=int(path.read_text())
    run('systemctl','set-property','--runtime',UNIT,'CPUWeight=100')
    record['raw_after_update']=int(path.read_text())
    assert record['raw_after_update']==0, 'raw-write reset did not reproduce'
    run('systemctl','set-property','--runtime',UNIT,'MemoryLow='+str(LOW))
    run('systemctl','set-property','--runtime',UNIT,'CPUWeight=101')
    record['managed_after_update']=int(path.read_text())
    record['manager_property']=int(prop('MemoryLow'))
    assert record['managed_after_update']==record['manager_property']==LOW
    record['status']='PASS'
finally:
    run('systemctl','stop',SERVICE,UNIT)
    run('systemctl','revert',UNIT)
    record['slice_absent']=not Path('/sys/fs/cgroup/q44crcontrol.slice').exists()
    record['runtime_override_absent']=all(not Path(base+'/'+UNIT+'.d').exists() for base in ['/run/systemd/system','/run/systemd/system.control'])
    print(json.dumps(record),flush=True)
    assert record['slice_absent'] and record['runtime_override_absent']
