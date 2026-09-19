"""Offline reproduction of the I transport failures; never starts a workload."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pod_remote_evidence_i import IncrementalEvidenceMirror, PodEvidenceIdentity, sha256

with tempfile.TemporaryDirectory() as directory:
    base = Path(directory)
    remote = base / "remote"
    state = remote / "state"
    state.mkdir(parents=True)
    (state / "config.json").write_text("{}")
    identity = PodEvidenceIdentity("pod-i", "container-i", 42, 99, sha256(b"{}"))
    (remote / "transport-identity.json").write_text(json.dumps(identity.__dict__))
    (remote / "supervisor-ownership.json").write_text('{"pid":42,"start_ticks":99}')
    (remote / "ownership.json").write_text(json.dumps({"config_sha256": identity.config_sha256}))
    proc = base / "proc/42"
    proc.mkdir(parents=True)
    (proc / "stat").write_text("42 (supervisor) " + " ".join(["S"] + ["0"] * 18 + ["99"]))
    scratch = state / "yolo-pod-cgroup-i/worker-1/scratch/07/activity-owned/07.pdf"
    scratch.parent.mkdir(parents=True)
    scratch.write_bytes(b"temporary parser input")
    mirror = IncrementalEvidenceMirror(base / "mirror", identity)

    def snapshot(receiver):
        program = receiver.request_program(str(remote)).replace(
            "Path('/proc')", "Path(" + repr(str(base / "proc")) + ")")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(program, {})
        return json.loads(output.getvalue())

    mirror.ingest(snapshot(mirror), received_at=1)
    scratch.unlink()  # Actual successful group cleanup removes its scratch.
    try:
        mirror.ingest(snapshot(mirror), received_at=2)
    except ValueError as error:
        assert "remote evidence disappeared" in str(error) and "/scratch/" in str(error)
        print("REPRODUCED: ordinary scratch cleanup aborts live evidence transport")
    else:
        raise AssertionError("I scratch-disappearance failure did not reproduce")

    terminal = IncrementalEvidenceMirror(base / "terminal-mirror", identity)
    terminal.ingest(snapshot(terminal), received_at=1)
    try:
        terminal.ingest(snapshot(terminal), received_at=12)
    except ValueError as error:
        assert str(error) == "evidence transport gap exceeded"
        print("REPRODUCED: 11-second cleanup delay prevents failed-window evidence drain")
    else:
        raise AssertionError("I receipt-gap failure did not reproduce")
