"""Read-only recheck; no uploads, workflow starts, model imports or signals."""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--bundle',type=Path,required=True)
    cli.add_argument('--out',type=Path,required=True)
    args=cli.parse_args()
    # Reserve an exclusive local result before contacting the cluster.
    with args.out.open('x') as stream:
        bundle=json.loads((args.bundle/'inputs.json').read_text())
        expected={'profile':bundle['base_profile'],'producer':bundle['producer'],
            'run_root':'/tmp/q04-keynote-18be1b3-20260916-a','prefix':'q04/keynote-18be1b3-20260916-a/'}
        script=Path(__file__).with_name('remote_probe.py').read_text()+'\nasyncio.run(main(json.loads('+repr(json.dumps(expected))+')))\n'
        result=subprocess.run(['kubectl','--context','kind-internal-a2a-vs6-local','--request-timeout=10s','-n','pdf-t09a-validation','exec','-i','coordinator','--',
            'env','PYTHONDONTWRITEBYTECODE=1','/experiment/.venv/bin/python','-'],input=script,text=True,capture_output=True,timeout=240)
        if result.returncode:
            json.dump({'status':'ERROR','stderr':result.stderr},stream,indent=2)
            raise SystemExit(result.returncode)
        stream.write(result.stdout)

if __name__=='__main__':main()
