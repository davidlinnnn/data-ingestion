import asyncio
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import signal
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class HostTest(unittest.TestCase):
    def test_launch_and_cleanup_target_measured_worker(self):
        def require(condition, message):
            if not condition:
                raise ValueError(message)
        modules = {'consumer': SimpleNamespace(require=require),
                   'host': SimpleNamespace(Host=object),
                   'host_be': SimpleNamespace(lifecycle_boundary=nullcontext)}
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('measured_host', Path(__file__).with_name('t09b_host.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            host = module.Host()
            host.config = {'python': sys.executable}
            host.config_path = Path(directory)/'config.json'
            host.root, host.generation, host.pod = Path(directory), 0, None
            with patch.object(module.subprocess, 'Popen') as launch:
                asyncio.run(host.launch_start())
            try:
                argv = launch.call_args.args[0]
                self.assertEqual(argv[1], str(Path(__file__).with_name('worker.py')))
                self.assertEqual(argv[2:], ['--config', str(host.config_path),
                                           '--out', str(host.current), '--generation', '1'])
                host.current.mkdir()
                (host.current/'ownership.json').write_text(json.dumps({
                    'pid': 123, 'created': 1, 'start_ticks': 456,
                }))
                with patch.object(module.subprocess, 'run') as send:
                    host.signal(123, signal.SIGTERM)
                script = send.call_args.args[0][2]
                self.assertIn('t09b/worker.py', script)
                self.assertIn("/proc/{parent}/stat", script)
                self.assertEqual(send.call_args.args[0][-1], '456')
                self.assertNotIn('q04/worker_bc.py', script)
                send.reset_mock()
                send.return_value.stdout = '{}'
                with patch.object(module.subprocess, 'run', send):
                    host.force_stop()
                self.assertIn('t09b/worker.py', send.call_args.args[0][2])
                self.assertEqual(send.call_args.args[0][-1], '456')
            finally:
                host.log.close()

    def test_signal_helper_preserves_the_actual_failure(self):
        def require(condition, message):
            if not condition:
                raise ValueError(message)
        modules = {'consumer': SimpleNamespace(require=require),
                   'host': SimpleNamespace(Host=object),
                   'host_be': SimpleNamespace(lifecycle_boundary=nullcontext)}
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location(
                'diagnostic_host', Path(__file__).with_name('t09b_host.py')
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        failure = module.subprocess.CalledProcessError(
            1, ['python'], stderr='AssertionError: worker command identity changed\n'
        )
        with patch.object(module.subprocess, 'run', side_effect=failure):
            with self.assertRaisesRegex(
                RuntimeError, 'worker command identity changed'
            ):
                module.checked_helper(['python'], 1)
