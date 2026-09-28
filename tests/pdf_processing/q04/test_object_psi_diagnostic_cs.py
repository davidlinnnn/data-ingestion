"""Actual retained CR trigger vs CS's explicitly approved diagnostic policy."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from sentinel import run_warm_pod_cgroup_cs as run

E=Path(__file__).parent.parent/'t09a_bounds/normal-topology-cr/first-window-evidence'
A=json.loads((E/'pressure-attribution.json').read_text())

class DiagnosticGuardTest(unittest.TestCase):
    def setUp(self):
        self.first=deepcopy(A['first_sample'])
        self.row=deepcopy(A['first_object_psi']['first'])
        self.vm=deepcopy(A['vm_sample_at_stop'])
        run.checked_samples=0
        run.monitor=SimpleNamespace(error=None,samples=[self.first,self.row])

    def test_retained_89us_is_allowed_and_remains_in_samples(self):
        run.verify_sample(self.vm,0)
        self.assertEqual(run.monitor.samples[-1]['object_full_total_us'],89)

    def test_positive_average_is_rejected_even_if_later_sample_recovers(self):
        self.row['object_full_total_us']=self.first['object_full_total_us']
        self.row['object_full_avg10']=0.01
        recovered=deepcopy(self.row);recovered['object_full_avg10']=0
        run.monitor.samples.append(recovered)
        with self.assertRaisesRegex(ValueError,'object-service'):
            run.verify_sample(self.vm,0)

    def test_object_max_and_oom_still_stop(self):
        self.row['object_full_total_us']=self.first['object_full_total_us']
        for key in ['max','oom','oom_kill','oom_group_kill']:
            with self.subTest(event=key):
                run.checked_samples=0
                self.row['memory_events']=deepcopy(self.first['memory_events'])
                self.row['memory_events'][key]+=1
                with self.assertRaisesRegex(ValueError,'object-service'):
                    run.verify_sample(self.vm,0)

    def test_vm_floor_psi_oom_and_telemetry_still_stop(self):
        for key,value in [('available',run.base.VM_RUNTIME_FLOOR_BYTES-1),('psi_full_avg10',0.01),('vm_oom_kill',1)]:
            with self.subTest(key=key):
                bad=deepcopy(self.vm);bad[key]=value
                with self.assertRaises(ValueError):run.verify_sample(bad,0)
        bad=deepcopy(self.vm);bad['memory_events']['oom_kill']=1
        with self.assertRaises(ValueError):run.verify_sample(bad,0)
        bad=deepcopy(self.vm);bad['memory_current']=run.base.CGROUP_GUARD_BYTES+1
        with self.assertRaises(ValueError):run.verify_sample(bad,0)
        run.monitor.error=TimeoutError('exact object observer telemetry stalled')
        with self.assertRaises(TimeoutError):run.verify_sample(self.vm,0)

    def test_deadline_still_stops(self):
        with self.assertRaises(TimeoutError):
            run.base.remaining_timeout(0,30,'CS diagnostic')

if __name__=='__main__':unittest.main()
