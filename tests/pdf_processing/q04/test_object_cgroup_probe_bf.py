"""Exact object Pod/container binding survives limit and identity drift checks."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sentinel import object_cgroup_probe_bf as probe


class ObjectProbeTest(unittest.TestCase):
    def test_exact_cgroup_and_limit_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cgroup = root / 'kubepods-podabc_def.slice/cri-containerd-deadbeef.scope'
            cgroup.mkdir(parents=True)
            (cgroup / 'memory.max').write_text('536870912\n')
            (cgroup / 'memory.current').write_text('100\n')
            (cgroup / 'memory.events').write_text('max 0\noom 0\noom_kill 0\n')
            (cgroup / 'memory.pressure').write_text('full avg10=0.00 avg60=0.00 total=1\n')
            node = root / 'node-pressure'
            node.write_text('full avg10=0.00 avg60=0.00 total=2\n')
            with patch.object(probe, 'NODE_PRESSURE', node):
                self.assertEqual(probe.exact_cgroup(root, 'abc-def', 'deadbeef',
                    536870912), cgroup)
                row = probe.sample(cgroup, 'abc-def', 'deadbeef', 536870912)
                self.assertEqual(row['memory_current'], 100)
                self.assertEqual(row['object_full_total_us'], 1)
                with self.assertRaisesRegex(ValueError, 'limit changed'):
                    probe.sample(cgroup, 'abc-def', 'deadbeef', 805306368)
            with self.assertRaisesRegex(ValueError, 'exact object cgroup'):
                probe.exact_cgroup(root, 'abc-def', 'other', 536870912)


if __name__ == '__main__':
    unittest.main()
