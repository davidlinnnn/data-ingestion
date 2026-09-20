"""Exercise the real AIMA consumer against the exact projected Pod workspace."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ProjectedOracleTest(unittest.TestCase):
    def test_complete_aima_oracle_reads_only_projected_dependencies(self):
        topology = importlib.import_module('pod_topology_'+os.environ.get('Q04_ORACLE_VERSION', 'p'))
        rendered = topology.kubernetes_list()
        maps = {x['metadata']['name']:x['data'] for x in rendered['items'] if x['kind']=='ConfigMap'}
        deployment = next(x for x in rendered['items'] if x['kind']=='Deployment')
        volume = next(x for x in deployment['spec']['template']['spec']['volumes'] if x['name']=='workspace')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for source in volume['projected']['sources']:
                projection = source['configMap']
                for item in projection['items']:
                    path = root/item['path'];path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_text(maps[projection['name']][item['key']])
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                       PYTHONPATH=os.pathsep.join(str(root/p) for p in ('src','tests/pdf_processing/q04','tests/pdf_processing/q02')),
                       Q02_SOURCE_ORACLE='/private/tmp/q04-inputs-yolo-lifecycle-v1/oracles/aima-code.json')
            program = '''import json
from pathlib import Path
from consumer import check_fixture
p=Path('/private/tmp/q04-aima-pod-cgroup-20260920-o')
x=json.loads((p/'offline-consumer-inputs.json').read_text())
d=json.loads((p/'failure-evidence/state/aima-pod-cgroup-o/fresh-08/document.json').read_text())
c=json.loads((p/'failure-evidence/state/aima-pod-cgroup-o/config.json').read_text())
result=check_fixture('08',d,x['evidence'],x['relationships']['relationships'],c['profiles']['08']['content_evidence']['relationships'],Path('/private/tmp/q04-inputs-yolo-lifecycle-v1/oracles'))
assert result['algorithms']==4 and result['continuation_edges']==8 and result['items']==615,result
print(json.dumps(result))
'''
            result = subprocess.run([sys.executable,'-c',program],cwd=root,env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__ == '__main__':
    unittest.main()
