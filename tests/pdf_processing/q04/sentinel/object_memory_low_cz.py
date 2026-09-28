"""One reversible, ancestor-effective object memory.low trial; never writes memory.min/max."""
import argparse
import json
from pathlib import Path
import subprocess

LOW = 768 * 1024**2
NODE = 'internal-a2a-vs6-local-worker2'


def capture(root, container_id, node_id):
    matches = list(root.rglob('cri-containerd-'+container_id+'.scope'))
    if len(matches) != 1 or not matches[0].is_relative_to(root/'docker'/node_id):
        raise ValueError('exact object cgroup or node changed')
    leaf = matches[0]
    levels = []
    child = None
    for p in [leaf, *leaf.parents]:
        if not (p/'memory.low').exists():
            break
        low, minimum, maximum = [(p/name).read_text().strip()
            for name in ['memory.low','memory.min','memory.max']]
        if low != '0' or minimum != '0':
            raise ValueError('existing protection requires a separate allocation plan')
        if maximum != 'max' and int(maximum) < LOW:
            raise ValueError('ancestor cap is below proposed protection')
        peers = {str(q):int((q/'memory.low').read_text()) for q in p.iterdir()
                 if q != child and (q/'memory.low').exists()}
        if any(peers.values()):
            raise ValueError('sibling protection would share the allowance')
        levels.append({'path':str(p),'inode':p.stat().st_ino,'low':low,
            'min':minimum,'max':maximum,'peer_lows':peers})
        child = p
    if len(levels)<2 or any(r['max']!='1073741824' for r in levels[:2]):
        raise ValueError('object and Pod must both have the existing 1Gi trial cap')
    return {'container_id':container_id,'node_id':node_id,'target':LOW,'levels':levels}


def write_low(path, value):
    (path/'memory.low').write_text(str(value))


def verify(snapshot):
    for row in snapshot['levels']:
        p = Path(row['path'])
        if p.stat().st_ino != row['inode'] or int((p/'memory.low').read_text()) != LOW:
            raise ValueError('protection identity/value changed')
        if (p/'memory.min').read_text().strip() != row['min'] or (p/'memory.max').read_text().strip() != row['max']:
            raise ValueError('min/max changed during protection setup')
        if any(int((Path(peer)/'memory.low').read_text()) for peer in row['peer_lows'] if (Path(peer)/'memory.low').exists()):
            raise ValueError('sibling protection changed')


def restore(snapshot):
    errors, absent = [], []
    for row in snapshot['levels']:  # Remove leaf protection before its ancestor allocation.
        p = Path(row['path'])
        try:
            if not p.exists():
                absent.append(str(p)); continue
            if p.stat().st_ino != row['inode']:
                raise ValueError('cgroup identity changed')
            if (p/'memory.low').read_text().strip() not in [row['low'],str(LOW)]:
                raise ValueError('memory.low changed outside this trial')
            write_low(p,row['low'])
            if (p/'memory.low').read_text().strip() != row['low']:
                raise ValueError('restoration readback failed')
        except Exception as error:
            errors.append(str(p)+': '+repr(error))
    return {'restored':not errors,'errors':errors,'already_absent':absent}


def verify_restored(snapshot):
    for row in snapshot['levels']:
        p = Path(row['path'])
        if p.exists():
            if p.stat().st_ino != row['inode'] or (p/'memory.low').read_text().strip() != row['low']:
                raise ValueError('original protection not restored: '+str(p))
    return {'verified_restored': True}


def apply(snapshot):
    try:
        for row in reversed(snapshot['levels']):  # Allocate parent protection first.
            p = Path(row['path'])
            if p.stat().st_ino != row['inode'] or (p/'memory.low').read_text().strip()!=row['low']:
                raise ValueError('protection precondition changed')
            write_low(p,LOW)
        verify(snapshot)
    except BaseException:
        result = restore(snapshot)
        if not result['restored']:
            raise RuntimeError('partial setup restoration failed: '+repr(result))
        raise


def stop_helper(action):
    name = 'q44-cz-protection-'+action
    result = subprocess.run(['docker','rm','--force',name],capture_output=True,text=True,timeout=15)
    if result.returncode and 'No such container' not in result.stderr:
        raise RuntimeError('cannot stop protection helper: '+result.stderr)
    remaining = subprocess.check_output(['docker','ps','-a','--filter','name=^/'+name+'$',
                                         '--format','{{.Names}}'],text=True,timeout=10).strip()
    if remaining:
        raise RuntimeError('protection helper remains: '+remaining)


def raw_host(action, directory, container_id=''):
    directory = Path(directory)
    if action=='restore':
        stop_helper('enter')
        stop_helper('restore')
    if action=='restore' and not (directory/'snapshot.json').exists():
        return {'restored':True,'not_started':True}
    directory.mkdir(exist_ok=True)
    image = subprocess.check_output(['docker','inspect','--format','{{.Config.Image}}',NODE],text=True,timeout=10).strip()
    node_id = subprocess.check_output(['docker','inspect','--format','{{.Id}}',NODE],text=True,timeout=10).strip()
    command = ['docker','run','--rm','--pull=never','--name','q44-cz-protection-'+action,
        '--network=none','--privileged','--cgroupns=host','--read-only',
        '-v',str(directory.resolve())+':/state','--entrypoint','python3',image,'-c',
        Path(__file__).read_text(),action,'--container-id',container_id,'--node-id',node_id]
    try:
        return json.loads(subprocess.check_output(command,text=True,timeout=20))
    except BaseException:
        stop_helper(action)
        raise


UNIT = 'kubelet-kubepods-burstable.slice'
OVERRIDE = '/run/systemd/system.control/'+UNIT+'.d/50-MemoryLow.conf'


def node(*args):
    return subprocess.check_output(['docker','exec',NODE,'timeout','10s',*args],text=True,timeout=15).strip()


def manager_low():
    return node('systemctl','show',UNIT,'--value','-p','MemoryLow')


def set_manager(value):
    node('flock','-w','6','/run/q44-cz-memory-low.lock','timeout','5s',
         'systemctl','set-property','--runtime',UNIT,'MemoryLow='+str(value))


def manager_snapshot():
    value = manager_low()
    if value != '0':
        raise ValueError('existing manager protection is outside trial scope')
    source = node('python3','-c',
        'import json,sys;from pathlib import Path;p=Path(sys.argv[1]);print(json.dumps(p.read_text() if p.exists() else None))',OVERRIDE)
    return {'low':value,'override':json.loads(source)}


def restore_manager(snapshot):
    if manager_low() not in [snapshot['low'],str(LOW)]:
        raise ValueError('manager protection changed outside trial')
    set_manager(snapshot['low'])
    # Restore only our one property file; never revert unrelated unit properties.
    node('python3','-c',
         'import json,sys;from pathlib import Path;p=Path(sys.argv[1]);old=json.loads(sys.argv[2]);'
         'p.write_text(old) if old is not None else p.unlink(missing_ok=True);'
         'Path("/run/q44-cz-memory-low.lock").unlink(missing_ok=True)',
         OVERRIDE,json.dumps(snapshot['override']))
    if manager_low()!=snapshot['low']:
        raise ValueError('manager restoration failed')


def host(action, directory, container_id=''):
    directory = Path(directory)
    manager_file = directory/'manager.json'
    if action=='enter':
        directory.mkdir(exist_ok=True)
        snapshot = manager_snapshot()
        with manager_file.open('x') as stream:
            json.dump(snapshot,stream,indent=2);stream.flush()
            import os
            os.fsync(stream.fileno())
        try:
            result = raw_host(action,directory,container_id)
            set_manager(LOW)
            if manager_low()!=str(LOW):
                raise ValueError('manager protection not applied')
            raw_host('check',directory)
            return result
        except BaseException:
            host('restore',directory)
            raise
    if action=='restore':
        stop_helper('enter')
        stop_helper('restore')
        manager_error = None
        try:
            if manager_file.exists():
                restore_manager(json.loads(manager_file.read_text()))
        except BaseException as error:
            manager_error = error
        result = raw_host(action,directory,container_id)
        if manager_error is not None:
            raise manager_error
        return result
    if action=='check' and manager_low()!=str(LOW):
        raise ValueError('manager protection changed')
    if action=='verify-restored':
        if manager_file.exists():
            expected = json.loads(manager_file.read_text())
            if manager_snapshot()!=expected:
                raise ValueError('manager property/override not restored')
        else:
            manager_snapshot()  # Still require the manager's baseline protection.
        if not (directory/'snapshot.json').exists():
            return {'verified_restored':True,'raw_not_started':True}
    return raw_host(action,directory,container_id)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['enter','check','restore','verify-restored'])
    parser.add_argument('--container-id',default='')
    parser.add_argument('--node-id',required=True)
    args = parser.parse_args()
    journal = Path('/state/snapshot.json')
    if args.action=='enter':
        snapshot = capture(Path('/sys/fs/cgroup'),args.container_id,args.node_id)
        with journal.open('x') as stream:
            json.dump(snapshot,stream,indent=2)
            stream.flush()
            import os
            os.fsync(stream.fileno())  # Durable recovery data precedes any mutation.
        apply(snapshot)
        result = {'applied':True,'levels':len(snapshot['levels']),'low_bytes':LOW}
    else:
        snapshot = json.loads(journal.read_text())
        if snapshot['node_id'] != args.node_id:
            raise ValueError('kind node identity changed')
        if args.action=='check':
            verify(snapshot)
            result = {'verified':True,'levels':len(snapshot['levels'])}
        elif args.action=='verify-restored':
            result = verify_restored(snapshot)
        else:
            result = restore(snapshot)
    Path('/state/'+args.action+'.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if args.action=='restore' and not result['restored']:
        raise SystemExit(1)
