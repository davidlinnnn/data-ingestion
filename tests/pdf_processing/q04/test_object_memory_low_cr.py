"""Actual protection writes: hierarchy, sibling allocation and partial-failure rollback."""
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
from sentinel import object_memory_low_cr as trial


class ProtectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.leaf = self.root/'docker/node/pod/cri-containerd-cid.scope'
        self.leaf.mkdir(parents=True)
        self.paths = [self.leaf,self.leaf.parent,self.leaf.parent.parent,self.root/'docker']
        for i,p in enumerate(self.paths):
            for name,value in [('memory.low','0'),('memory.min','0'),
                               ('memory.max','1073741824' if i<2 else 'max')]:
                (p/name).write_text(value)

    def test_effective_chain_and_idempotent_restore(self):
        snapshot = trial.capture(self.root,'cid','node')
        trial.apply(snapshot)
        with self.assertRaisesRegex(ValueError,'not restored'):
            trial.verify_restored(snapshot)
        self.assertTrue(all((p/'memory.low').read_text()==str(trial.LOW) for p in self.paths))
        self.assertTrue(trial.restore(snapshot)['restored'])
        self.assertTrue(trial.verify_restored(snapshot)['verified_restored'])
        self.assertTrue(trial.restore(snapshot)['restored'])
        self.assertTrue(all((p/'memory.low').read_text()=='0' for p in self.paths))
        self.assertTrue(all((p/'memory.min').read_text()=='0' for p in self.paths))

    def test_applied_write_then_failure_restores_ancestors(self):
        snapshot = trial.capture(self.root,'cid','node')
        real = trial.write_low
        def broken(p,value):
            real(p,value)
            if p==self.leaf.parent and value==trial.LOW:
                raise OSError('write applied; caller failed')
        with patch.object(trial,'write_low',side_effect=broken):
            with self.assertRaisesRegex(OSError,'caller failed'):
                trial.apply(snapshot)
        self.assertTrue(all((p/'memory.low').read_text()=='0' for p in self.paths))

    def test_timeout_stops_remote_writer_before_caller_can_restore(self):
        with patch.object(trial.subprocess,'check_output',side_effect=[
                'kind-image','node',subprocess.TimeoutExpired('docker run',20)]), \
                patch.object(trial,'stop_helper') as stop:
            with self.assertRaises(subprocess.TimeoutExpired):
                trial.raw_host('enter',self.root/'journal','cid')
            stop.assert_called_once_with('enter')
        # A killed caller can leave a helper before journal creation: stop it first.
        with patch.object(trial,'stop_helper') as stop:
            self.assertTrue(trial.raw_host('restore',self.root/'missing')['not_started'])
            self.assertEqual([c.args[0] for c in stop.call_args_list],['enter','restore'])

    def test_manager_setting_survives_reconciliation_and_restores(self):
        state={'low':'0'}
        old={'low':'0','override':None}
        def set_low(value):state['low']=str(value)
        def restore_manager(snapshot):state['low']=snapshot['low']
        with patch.object(trial,'manager_snapshot',return_value=old), \
             patch.object(trial,'manager_low',side_effect=lambda:state['low']), \
             patch.object(trial,'set_manager',side_effect=set_low), \
             patch.object(trial,'restore_manager',side_effect=restore_manager), \
             patch.object(trial,'stop_helper'), patch.object(trial,'raw_host',return_value={'restored':True}):
            trial.host('enter',self.root/'journal','cid')
            # systemd applies its stored value when other properties are updated.
            self.assertEqual(int(state['low']),trial.LOW)
            trial.host('restore',self.root/'journal')
            self.assertEqual(state['low'],'0')

    def test_manager_write_applied_then_error_restores_both_layers(self):
        state={'low':'0'}
        def failed(value):
            state['low']=str(value)
            raise OSError('manager write applied; response lost')
        def rollback(snapshot):state['low']=snapshot['low']
        with patch.object(trial,'manager_snapshot',return_value={'low':'0','override':None}), \
             patch.object(trial,'set_manager',side_effect=failed), \
             patch.object(trial,'restore_manager',side_effect=rollback), \
             patch.object(trial,'stop_helper'), patch.object(trial,'raw_host',return_value={}) as raw:
            with self.assertRaisesRegex(OSError,'response lost'):
                trial.host('enter',self.root/'journal','cid')
            self.assertEqual(state['low'],'0')
            self.assertEqual([c.args[0] for c in raw.call_args_list],['enter','restore'])

    def test_existing_sibling_protection_rejects_before_writes(self):
        sibling=self.leaf.parent/'sibling';sibling.mkdir()
        (sibling/'memory.low').write_text('123')
        with self.assertRaisesRegex(ValueError,'sibling protection'):
            trial.capture(self.root,'cid','node')
        self.assertTrue(all((p/'memory.low').read_text()=='0' for p in self.paths))


if __name__=='__main__':
    unittest.main()
