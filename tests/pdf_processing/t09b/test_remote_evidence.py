import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io

import pod_remote_evidence as remote


class RemoteEvidenceTest(unittest.TestCase):
    def test_snapshot_does_not_read_past_extent_when_stream_grows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'remote'
            root.mkdir()
            (root / 'state').mkdir()
            config = b'{}'
            (root / 'state/config.json').write_bytes(config)
            identity = remote.PodEvidenceIdentity('pod', 'container', 99999999, 1,
                                                  remote.base.sha256(config))
            for name, value in {
                'transport-identity.json': identity.__dict__,
                'supervisor-ownership.json': {'pid': identity.worker_pid, 'start_ticks': 1},
                'ownership.json': {'config_sha256': identity.config_sha256},
                'workload-exit.json': {'returncode': 1},
                'cleanup-complete.json': {},
            }.items():
                (root / name).write_text(json.dumps(value))
            relative = f'state/{remote.PHASE}/worker-1/storage.jsonl'
            ledger = root / relative
            ledger.parent.mkdir(parents=True)
            first, appended = b'{"row":1}\n', b'{"row":2}\n'
            ledger.write_bytes(first)
            original_open = Path.open
            grew = False

            def racing_open(path, *args, **kwargs):
                nonlocal grew
                if path == ledger and args and args[0] == 'rb' and not grew:
                    grew = True
                    with original_open(path, 'ab') as stream:
                        stream.write(appended)
                return original_open(path, *args, **kwargs)

            output = io.StringIO()
            with patch.object(Path, 'open', racing_open), contextlib.redirect_stdout(output):
                exec(remote.base.snapshot_program(str(root), {}, 1, identity), {})
            mirror = remote.IncrementalEvidenceMirror(Path(directory) / 'local', identity)
            mirror.ingest(json.loads(output.getvalue()), received_at=1)
            self.assertEqual((mirror.root / relative).read_bytes(), first)

            result = subprocess.run([sys.executable, '-c', mirror.request_program(str(root))],
                                    check=True, capture_output=True, text=True, timeout=10)
            mirror.ingest(json.loads(result.stdout), received_at=2)
            self.assertEqual((mirror.root / relative).read_bytes(), first + appended)

    def test_ledger_chunks_wait_for_newline_and_preserve_interruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'remote'
            root.mkdir()
            (root / 'state').mkdir()
            config = b'{}'
            (root / 'state/config.json').write_bytes(config)
            identity = remote.PodEvidenceIdentity('pod', 'container', 99999999, 1,
                                                  remote.base.sha256(config))
            documents = {
                'transport-identity.json': identity.__dict__,
                'supervisor-ownership.json': {'pid': identity.worker_pid, 'start_ticks': 1},
                'ownership.json': {'config_sha256': identity.config_sha256},
                'workload-exit.json': {'returncode': 1},
                'cleanup-complete.json': {},
            }
            for name, value in documents.items():
                (root / name).write_text(json.dumps(value))
            relative = f'state/{remote.PHASE}/worker-1/storage.jsonl'
            ledger = root / relative
            ledger.parent.mkdir(parents=True)
            ledger.write_text('{"kind":"start"}\n{"kind":')
            mirror = remote.IncrementalEvidenceMirror(Path(directory) / 'local', identity)

            def pull(at):
                result = subprocess.run([sys.executable, '-c', mirror.request_program(str(root))],
                                        check=True, capture_output=True, text=True, timeout=10)
                mirror.ingest(json.loads(result.stdout), received_at=at)

            pull(1)
            self.assertEqual((mirror.root / relative).read_text(), '{"kind":"start"}\n')
            self.assertNotIn(relative, mirror.complete)
            with ledger.open('a') as stream:
                stream.write('"finish"}\n')
            pull(2)
            self.assertEqual((mirror.root / relative).read_bytes(), ledger.read_bytes())
            self.assertIn(relative, mirror.complete)
            self.assertIn(relative, remote.base.FINAL_REQUIRED)
            self.assertNotIn(f'state/{remote.PHASE}/worker-2/storage.jsonl', remote.base.FINAL_REQUIRED)
            with self.assertRaises(ValueError):
                mirror.finalize(require_success=True)
