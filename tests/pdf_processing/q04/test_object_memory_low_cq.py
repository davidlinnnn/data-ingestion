"""Actual protection writes: hierarchy, sibling allocation and partial-failure rollback."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sentinel import object_memory_low_cq as trial


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

    def test_existing_sibling_protection_rejects_before_writes(self):
        sibling=self.leaf.parent/'sibling';sibling.mkdir()
        (sibling/'memory.low').write_text('123')
        with self.assertRaisesRegex(ValueError,'sibling protection'):
            trial.capture(self.root,'cid','node')
        self.assertTrue(all((p/'memory.low').read_text()=='0' for p in self.paths))


if __name__=='__main__':
    unittest.main()
