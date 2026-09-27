"""Cheap marker-transport regression; fake OCR performs no model inference."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
Q04 = HERE.parents[1] / 'q04'
sys.path.insert(0, str(Q04))
import pod_workload_p as supervisor


def check():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); src = root / 'src'; pkg = src / 'pdf_processing'
        pkg.mkdir(parents=True); (pkg / '__init__.py').touch()
        # The real startup hook and lifecycle launcher, with a minimal OCR body.
        hook = (HERE / 'sitecustomize.py').read_text().replace(
            '(Path(__file__).resolve().parents[2] / "q04/pod-topology-v44/sitecustomize.py")',
            repr(str(Q04 / 'pod-topology-v44/sitecustomize.py')))
        hook = hook.replace(repr(str(Q04 / 'pod-topology-v44/sitecustomize.py')) + '.read_text()',
                            'Path(' + repr(str(Q04 / 'pod-topology-v44/sitecustomize.py')) + ').read_text()')
        (src / 'sitecustomize.py').write_text(hook)
        (pkg / 'ocr.py').write_text('def execute():\n    pass\nexecute()\n')
        captured = {}
        class Captured(Exception): pass
        def capture(*args, **kwargs):
            captured.update(kwargs['env']); raise Captured
        args = SimpleNamespace(workload_seconds=10, control=root, capacity=root/'unused', workspace=root)
        with patch.object(supervisor, 'require_pre_inference_gates'), patch.object(supervisor, 'write_once'), patch.object(supervisor, 'start_ticks', return_value=1), patch.object(supervisor, 'sha256', return_value='unused'), patch.object(supervisor, 'build_init_argv', return_value=[]), patch.object(supervisor.subprocess, 'run', side_effect=capture):
            try: supervisor.run(args)
            except Captured: pass
        parent, child = socket.socketpair()
        try:
            captured.update(Q04_OCR_TRACE_DIR=str(root/'trace'), PDF_PROCESS_LIFECYCLE_FD=str(child.fileno()))
            proc = subprocess.Popen([sys.executable, str(HERE.parents[3]/'src/pdf_processing/lifecycle_child.py'), 'pdf_processing.ocr'], env=captured, pass_fds=(child.fileno(),), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            child.close(); parent.settimeout(5)
            assert parent.recv(1) == b'1'; parent.sendall(b'1')
            stdout, stderr = proc.communicate(timeout=5)
            assert proc.returncode == 0, stderr.decode()
            rows = [json.loads(line) for path in (root/'trace').glob('*.jsonl') for line in path.read_text().splitlines()]
            assert [r['stage'] for r in rows] == ['ocr_enter'], rows
        finally:
            parent.close(); child.close()
            if 'proc' in locals() and proc.poll() is None:
                proc.kill(); proc.wait()
    print('PASS: supervisor environment -> lifecycle child -> startup hook marker')


if __name__ == '__main__':
    check()
