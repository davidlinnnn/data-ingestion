"""Owned remote cleanup through a local transport; never connects to services."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from host import Host


class RemoteCleanup(unittest.IsolatedAsyncioTestCase):
    def host(self, root):
        host = Host(root/'config.json', root, {'python': sys.executable, 'pod_namespace': 'local-test', 'drain_seconds': 1})
        host.pod = {'metadata': {'name': 'owned', 'uid': 'original-uid'}}
        host.generation = 1
        host.current = root/'worker-1'
        host.worker_command = [sys.executable, '-c', 'import time; time.sleep(60)', str(root/'unique-owned-command')]
        host.process = MagicMock(poll=lambda: 1, wait=lambda timeout: 1, returncode=1)
        return host

    async def test_disconnected_launcher_still_stops_exact_remote_worker(self):
        import psutil
        with tempfile.TemporaryDirectory() as tmp:
            host = self.host(Path(tmp))
            assert host.worker_command is not None
            remote = subprocess.Popen(host.worker_command)
            unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
            host.current.mkdir()
            (host.current/'ownership.json').write_text(json.dumps({'pid': remote.pid, 'created': psutil.Process(remote.pid).create_time()}))
            actual_output = subprocess.check_output
            def local_transport(command, **kwargs):
                local = command[command.index('--')+1:]
                # Emulate the isolated Pod PID namespace, retaining real local processes.
                local[2] = ('import psutil; psutil.process_iter=lambda: [psutil.Process(%d), psutil.Process(%d)]\n' % (remote.pid, unrelated.pid))+local[2]
                return actual_output(local, **kwargs)
            try:
                with patch.object(host, 'kubectl', return_value=json.dumps(host.pod)), patch('host.subprocess.check_output', side_effect=local_transport):
                    with self.assertRaisesRegex(ValueError, 'cleanup remains pending'):
                        await host.stop()
                remote.wait(timeout=5)
                self.assertIsNone(unrelated.poll())
                self.assertIsNotNone(host.process)
                evidence = json.loads(next(host.root.glob('remote-cleanup-*.json')).read_text())
                self.assertTrue(evidence['worker_absent'])
                self.assertEqual(evidence['owned_pids'], [remote.pid])
            finally:
                for process in (remote, unrelated):
                    if process.poll() is None: process.kill()
                    process.wait(timeout=5)

    async def test_before_ownership_publication_uses_exact_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            host = self.host(Path(tmp))
            assert host.worker_command is not None
            remote = subprocess.Popen(host.worker_command)
            actual_output = subprocess.check_output
            def local_transport(command, **kwargs):
                local = command[command.index('--')+1:]
                # Emulate the isolated Pod PID namespace, retaining real local processes.
                local[2] = ('import psutil; psutil.process_iter=lambda: [psutil.Process(%d)]\n' % remote.pid)+local[2]
                return actual_output(local, **kwargs)
            try:
                with patch.object(host, 'kubectl', return_value=json.dumps(host.pod)), patch('host.subprocess.check_output', side_effect=local_transport):
                    with self.assertRaisesRegex(ValueError, 'cleanup remains pending'):
                        await host.stop()
                remote.wait(timeout=5)
                evidence = json.loads(next(host.root.glob('remote-cleanup-*.json')).read_text())
                self.assertFalse(evidence['identity_published'])
                self.assertEqual(evidence['owned_pids'], [remote.pid])
            finally:
                if remote.poll() is None: remote.kill()
                remote.wait(timeout=5)

    async def test_parent_gone_with_surviving_child_keeps_cleanup_pending(self):
        import psutil
        with tempfile.TemporaryDirectory() as tmp:
            host = self.host(Path(tmp))
            pid_file = Path(tmp)/'child.pid'
            parent_script = 'import subprocess,sys; from pathlib import Path; p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); Path(sys.argv[1]).write_text(str(p.pid))'
            host.worker_command = [sys.executable, '-c', parent_script, str(pid_file)]
            parent = subprocess.Popen(host.worker_command)
            parent.wait(timeout=5)
            child = psutil.Process(int(pid_file.read_text()))
            launcher = host.process
            actual_output = subprocess.check_output
            def local_transport(command, **kwargs):
                local = command[command.index('--')+1:]
                local[2] = ('import psutil; psutil.process_iter=lambda: [psutil.Process(%d)]\n' % child.pid)+local[2]
                return actual_output(local, **kwargs)
            try:
                with patch.object(host, 'kubectl', return_value=json.dumps(host.pod)), patch('host.subprocess.check_output', side_effect=local_transport):
                    with self.assertRaisesRegex(ValueError, 'child/scratch cleanup remains pending'):
                        await host.stop()
                self.assertIs(host.process, launcher)
                self.assertTrue(child.is_running())
                evidence = json.loads(next(host.root.glob('remote-cleanup-*.json')).read_text())
                self.assertTrue(evidence['worker_absent'])
                self.assertNotIn('remote_absent', evidence)
                self.assertEqual(evidence['owned_pids'], [])
            finally:
                child.kill()
                try: child.wait(timeout=5)
                except psutil.TimeoutExpired: pass

    async def test_local_parent_exit_without_cleanup_proof_retains_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            host = self.host(Path(tmp))
            host.pod = None
            launcher = host.process
            with self.assertRaisesRegex(ValueError, 'child/scratch cleanup remains pending'):
                await host.stop()
            self.assertIs(host.process, launcher)

    async def test_changed_pod_uid_preserves_pending_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            host = self.host(Path(tmp))
            launcher = host.process
            with patch.object(host, 'kubectl', return_value=json.dumps({'metadata': {'uid': 'replacement'}})), patch('host.subprocess.check_output') as execute:
                with self.assertRaisesRegex(ValueError, 'Pod identity changed'):
                    await host.stop()
                execute.assert_not_called()
            self.assertIs(host.process, launcher)
            assert host.pod is not None
            self.assertEqual(host.pod['metadata']['uid'], 'original-uid')

    async def test_graceful_remote_exit_waits_for_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            host = self.host(Path(tmp))
            host.current.mkdir()
            (host.current/'stopped.json').write_text(json.dumps({'parser_absent': True, 'scratch_absent': True, 'generation': 1}))
            launcher = MagicMock(returncode=None, poll=lambda: None)
            def wait(timeout):
                launcher.returncode = 0
                return 0
            launcher.wait = wait
            host.process = launcher
            with patch.object(host, 'stop_remote', return_value={'worker_absent': True, 'forced': False}):
                await host.stop()
            self.assertIsNone(host.process)

    async def test_transport_failure_can_retry_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            host = self.host(Path(tmp))
            host.current.mkdir()
            (host.current/'stopped.json').write_text(json.dumps({'parser_absent': True, 'scratch_absent': True, 'generation': 1}))
            launcher = host.process
            with patch.object(host, 'stop_remote', side_effect=[OSError('transport unavailable'), {'worker_absent': True, 'forced': False}]) as cleanup:
                with self.assertRaisesRegex(OSError, 'transport unavailable'):
                    await host.stop()
                self.assertIs(host.process, launcher)
                with self.assertRaisesRegex(ValueError, 'transport failed'):
                    await host.stop()
                self.assertEqual(cleanup.call_count, 2)
            self.assertIsNone(host.process)


if __name__ == '__main__':
    unittest.main()
