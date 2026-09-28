import unittest
from unittest.mock import patch
from sentinel import run_yolo_pod_cgroup_l as runner
import pod_topology_l as topology
class ProbeTests(unittest.TestCase):
 def test_no_recurring_exec_probe_inside_measured_container(self):
  value=topology.kubernetes_list()
  pod=next(x for x in value['items'] if x['kind']=='Deployment')['spec']['template']['spec']
  c=pod['containers'][0]
  self.assertNotIn('readinessProbe',c)
  self.assertNotIn('livenessProbe',c)
  self.assertEqual(c['startupProbe']['exec']['command'],['/bin/sh','-c','test -d /q04-control && test -w /q04-evidence'])
  self.assertEqual(c['startupProbe']['periodSeconds'],2)
  self.assertEqual(c['startupProbe']['failureThreshold'],15)
 def test_runtime_mount_readiness_is_still_checked_by_persistent_sample(self):
  program=runner.sample_program()
  check=next(line for line in program.splitlines() if "runtime mount readiness changed" in line)
  from pathlib import Path
  import os
  with patch.object(Path,'is_dir',return_value=False):
   with self.assertRaisesRegex(ValueError,'runtime mount readiness changed'):exec(check,{'Path':Path,'os':os})
  with patch.object(Path,'is_dir',return_value=True),patch.object(os,'access',return_value=False):
   with self.assertRaisesRegex(ValueError,'runtime mount readiness changed'):exec(check,{'Path':Path,'os':os})
if __name__=='__main__':unittest.main()
