import asyncio
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import q04_runtime
from runtime_policy import Run


class RuntimePolicyTest(unittest.IsolatedAsyncioTestCase):
    async def test_actual_coordinator_records_runtime_psi_but_admission_stays_strict(self):
        positive = dict(time=time.time() - .2, available=4_000_000_000, vm_oom_kill=0,
                   memory_current=1, memory_events={'oom_kill': 0}, psi_full_avg10=.18)
        zero = {**positive, 'time': positive['time'] + .1, 'psi_full_avg10': 0}
        limits = dict(ends_at=time.time() + 60, cleanup_seconds=0,
                      max_sample_gap_seconds=10, min_available_bytes=3_000_000_000,
                      max_full_psi=0, max_cgroup_bytes=10,
                      admission_seconds=1, admission_available_bytes=3_000_000_000)
        with tempfile.TemporaryDirectory() as directory:
            current = Path(directory)
            (current / 'samples.jsonl').write_text(
                json.dumps(positive) + '\n' + json.dumps(zero) + '\n')
            host = type('Host', (), {'current': current, 'process': type('P', (), {'poll': lambda self: None})(), 'pod': None})()
            run = Run({'window': limits}, {}, current, None, None, host)
            with patch.object(q04_runtime, 'validate_window'):
                with self.assertRaisesRegex(ValueError, 'VM PSI pressure'):
                    await run.admission()
                run.runtime_node_psi_telemetry = True
                self.assertEqual((await run.guard())['psi_full_avg10'], 0)
                (current / 'samples.jsonl').write_text(json.dumps({**zero, 'vm_oom_kill': 1}) + '\n')
                with self.assertRaisesRegex(ValueError, 'VM OOM'):
                    await run.guard()


if __name__ == '__main__':
    unittest.main()
