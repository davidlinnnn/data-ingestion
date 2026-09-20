import unittest
from unittest.mock import Mock, patch
import pod_workload_m as workload
from pathlib import Path
from types import SimpleNamespace


class THPTests(unittest.TestCase):
    def test_entrypoint_applies_policy_before_spawning_workload(self):
        events = []
        args = SimpleNamespace(control=Path('/unused'))
        with patch.object(workload, 'parser') as parser, \
             patch.object(workload, 'disable_thp', side_effect=lambda: events.append('policy') or {}), \
             patch.object(workload, 'write_once', side_effect=lambda *a, **k: events.append('record')), \
             patch.object(workload, 'run', side_effect=lambda a: events.append('run') or 0):
            parser.return_value.parse_args.return_value = args
            self.assertEqual(workload.main([]), 0)
        self.assertEqual(events, ['policy', 'record', 'run'])

    def test_process_policy_is_set_and_read_back(self):
        libc = Mock()
        libc.prctl.side_effect = [0, 1]
        with patch('ctypes.CDLL', return_value=libc):
            self.assertEqual(workload.disable_thp()['thp_disabled'], 1)
        self.assertEqual(libc.prctl.call_args_list[0].args, (41, 1, 0, 0, 0))
        self.assertEqual(libc.prctl.call_args_list[1].args, (42, 0, 0, 0, 0))

    def test_failed_or_ineffective_policy_stops_before_workload(self):
        for values in ([-1], [0, 0], [0, -1]):
            libc = Mock()
            libc.prctl.side_effect = values
            with patch('ctypes.CDLL', return_value=libc):
                with self.assertRaises(OSError):
                    workload.disable_thp()


if __name__ == '__main__':
    unittest.main()
