"""The real probe preserves parent-only max events alongside the unchanged leaf data."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sentinel import object_cgroup_probe_cp as probe


class AncestorProbeTest(unittest.TestCase):
    def test_parent_limit_events_are_not_lost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pod = root/'kubepods-podabc_def.slice'
            leaf = pod/'cri-containerd-deadbeef.scope'
            leaf.mkdir(parents=True)
            for path, events in [(leaf, 2), (pod, 970)]:
                for name, value in {
                    'memory.max':'1073741824', 'memory.high':'max',
                    'memory.current':'100', 'memory.swap.current':'0',
                    'memory.events':f'max {events}\noom 0\noom_kill 0\n',
                    'memory.events.local':f'max {events}\noom 0\noom_kill 0\n',
                    'memory.pressure':'full avg10=0.00 total=67\n',
                    'memory.stat':'anon 10\nfile 20\nkernel 5\npgscan_direct 3\npgscan_kswapd 4\nworkingset_refault_file 6\n',
                }.items():
                    (path/name).write_text(value)
            vm = root/'vmstat'
            vm.write_text('oom_kill 0\npgscan_direct 7\npgscan_kswapd 8\ncompact_stall 9\nallocstall_movable 10\nworkingset_refault_file 11\n')
            with patch.object(probe,'NODE_PRESSURE',leaf/'memory.pressure'), patch.object(probe,'VMSTAT',vm):
                row = probe.sample(leaf,'abc-def','deadbeef',1073741824)
            self.assertEqual(row['memory_events']['max'],2)
            self.assertEqual([x['events_local']['max'] for x in row['ancestors']],[2,970])
            self.assertEqual(row['ancestors'][1]['memory_max'],'1073741824')
            self.assertEqual(row['object_full_total_us'],67)
            self.assertEqual(row['vmstat']['pgscan_direct'],7)


if __name__ == '__main__':
    unittest.main()
