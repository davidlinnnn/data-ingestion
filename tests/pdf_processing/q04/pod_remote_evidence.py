"""Identity-fenced incremental evidence transport for one Q04 worker Pod.

The module has no Kubernetes side effects.  The live runner supplies the
transport callable; tests exercise the same ingest interface with an in-memory
adapter.  Pod-local collection cadence and controller transport cadence are
separate contracts.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Callable


STREAM_FILES = {
    "state/yolo-pod-cgroup-a-measurement/resource-attribution.jsonl",
    "vm-controller.jsonl",
    "workload.log",
}
FINAL_REQUIRED = {
    "state/yolo-pod-cgroup-a/phase-complete.json",
    "state/yolo-pod-cgroup-a/reviewed-window-contract.json",
    "state/yolo-pod-cgroup-a/fresh-index.json",
    "state/yolo-pod-cgroup-a/fresh-07/accepted.json",
    "state/yolo-pod-cgroup-a/fresh-07/document.json",
    "state/yolo-pod-cgroup-a/fresh-07/source-reviewed-equivalence.json",
    "state/yolo-pod-cgroup-a/restored-07/accepted.json",
    "state/yolo-pod-cgroup-a/restored-07/document.json",
    "state/yolo-pod-cgroup-a/restored-07/source-reviewed-equivalence.json",
    "state/yolo-pod-cgroup-a/replay-07/accepted.json",
    "state/yolo-pod-cgroup-a/replay-07/document.json",
    "state/yolo-pod-cgroup-a/replay-07/source-reviewed-equivalence.json",
    "state/yolo-pod-cgroup-a-measurement/resource-attribution.jsonl",
    "state/yolo-pod-cgroup-a-measurement/resource-attribution-summary.json",
    "state/yolo-pod-cgroup-a-measurement/measurement-contract.json",
    "workload-exit.json",
    "cleanup-complete.json",
    "durable-terminal-manifest.json",
    "workload.log",
    "init-exit.json",
    "state/config.json",
    "state/pod-init.json",
}
ROOT_ALLOWED = {
    "supervisor-ownership.json",
    "ownership.json",
    "transport-identity.json",
    "no-inference-preflight.json",
    "budget-adoption.json",
    "capacity.json",
    "init-exit.json",
    "workload-exit.json",
    "cleanup-complete.json",
    "durable-terminal-manifest.json",
    "evidence-volume-identity.json",
    "workload.log",
    "state/config.json",
    "state/pod-init.json",
}
ALLOWED_PREFIXES = (
    "state/yolo-pod-cgroup-a/",
    "state/yolo-pod-cgroup-a-measurement/",
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class PodEvidenceIdentity:
    pod_uid: str
    container_id: str
    worker_pid: int
    worker_start_ticks: int
    config_sha256: str

    def __post_init__(self):
        if not self.pod_uid or not self.container_id or not self.config_sha256:
            raise ValueError("complete Pod/container/config identity required")
        if self.worker_pid <= 0 or self.worker_start_ticks <= 0:
            raise ValueError("positive worker process identity required")


def snapshot_program(
    root: str,
    offsets: dict[str, int],
    sequence: int,
    identity: PodEvidenceIdentity,
) -> str:
    """Return a Pod-local read-only snapshot program.

    Each file chunk is read from the caller's prior byte offset. JSONL chunks
    end at the last newline, so transport never invents a partial sample.
    """
    return """import base64,hashlib,json,os
from pathlib import Path
root=Path(ROOT); offsets=OFFSETS; streams=set(STREAMS); expected=IDENTITY
allowed=set(ALLOWED); prefixes=PREFIXES
if not root.is_dir(): raise FileNotFoundError(root)
transport=json.loads((root/'transport-identity.json').read_text())
if transport!=expected: raise ValueError('transport identity changed')
supervisor=json.loads((root/'supervisor-ownership.json').read_text())
workload=json.loads((root/'ownership.json').read_text())
config_hash=hashlib.sha256((root/'state/config.json').read_bytes()).hexdigest()
proc=Path('/proc')/str(supervisor['pid'])/'stat'
if proc.exists():
 raw=proc.read_text(); ticks=int(raw[raw.rfind(')')+1:].split()[19]); process_state='live'
 if ticks!=expected['worker_start_ticks']: raise ValueError('supervisor PID identity changed')
else:
 if not (root/'workload-exit.json').is_file() or not (root/'cleanup-complete.json').is_file():
  raise ValueError('supervisor absent without terminal markers')
 process_state='confirmed_absent_terminal'
if (supervisor['pid']!=expected['worker_pid']
 or supervisor['start_ticks']!=expected['worker_start_ticks']
 or workload['config_sha256']!=expected['config_sha256']
 or config_hash!=expected['config_sha256']):
 raise ValueError('live transport identity changed')
files=[]
for path in sorted(root.rglob('*')):
 if path.is_symlink(): raise ValueError('evidence symlink forbidden: '+str(path))
 if not path.is_file(): continue
 name=path.relative_to(root).as_posix()
 if name=='inputs' or name.startswith('inputs/'): continue
 if name not in allowed and not any(name.startswith(prefix) for prefix in prefixes):
  raise ValueError('unexpected evidence path: '+name)
 start=offsets.get(name,0)
 size=path.stat().st_size
 if start<0 or start>size: raise ValueError('evidence offset drift: '+name)
 with path.open('rb') as stream:
  stream.seek(start); raw=stream.read(4*1024*1024)
 if name in streams and raw and not raw.endswith(b'\\n'):
  split=raw.rfind(b'\\n'); raw=b'' if split<0 else raw[:split+1]
 files.append({'path':name,'offset':start,'size':len(raw),'total_size':size,
  'eof':start+len(raw)==size,
  'sha256':hashlib.sha256(raw).hexdigest(),
  'data':base64.b64encode(raw).decode()})
print(json.dumps({'schema_version':1,'sequence':SEQUENCE,'identity':expected,
 'process_state':process_state,'files':files},
 sort_keys=True,separators=(',',':')))
""".replace("ROOT", repr(root)).replace(
        "OFFSETS", repr(dict(sorted(offsets.items())))
    ).replace("STREAMS", repr(sorted(STREAM_FILES))).replace(
        "SEQUENCE", repr(sequence)
    ).replace(
        "IDENTITY", repr(identity.__dict__)
    ).replace(
        "ALLOWED", repr(sorted(ROOT_ALLOWED))
    ).replace(
        "PREFIXES", repr(ALLOWED_PREFIXES)
    )


class IncrementalEvidenceMirror:
    """Mirror immutable prefixes and append-only streams behind one interface."""

    def __init__(
        self,
        root: Path,
        identity: PodEvidenceIdentity,
        *,
        maximum_transport_gap_seconds: float = 5.0,
    ):
        if maximum_transport_gap_seconds <= 0:
            raise ValueError("positive transport gap required")
        self.root = root
        self.identity = identity
        self.maximum_transport_gap_seconds = maximum_transport_gap_seconds
        self.offsets: dict[str, int] = {}
        self.remote_sizes: dict[str, int] = {}
        self.complete: set[str] = set()
        self.sequence = 0
        self.last_received_at: float | None = None
        self.records: list[dict] = []
        self.finalized = False

    def _path(self, relative: str) -> Path:
        value = PurePosixPath(relative)
        if value.is_absolute() or ".." in value.parts or not value.parts:
            raise ValueError("unsafe evidence path")
        return self.root.joinpath(*value.parts)

    def request_program(self, remote_root: str) -> str:
        return snapshot_program(
            remote_root, self.offsets, self.sequence + 1, self.identity
        )

    def ingest(self, envelope: dict, *, received_at: float) -> dict:
        if self.finalized:
            raise ValueError("evidence mirror already finalized")
        if envelope.get("schema_version") != 1:
            raise ValueError("evidence transport schema changed")
        if envelope.get("sequence") != self.sequence + 1:
            raise ValueError("evidence transport sequence gap")
        if envelope.get("identity") != self.identity.__dict__:
            raise ValueError("evidence transport identity changed")
        if envelope.get("process_state") not in {"live", "confirmed_absent_terminal"}:
            raise ValueError("evidence supervisor state is not verified")
        if self.last_received_at is not None:
            gap = received_at - self.last_received_at
            if gap <= 0 or gap > self.maximum_transport_gap_seconds:
                raise ValueError("evidence transport gap exceeded")
        written = []
        seen = set()
        for row in envelope.get("files", []):
            relative = row.get("path")
            if relative in seen:
                raise ValueError("duplicate evidence inventory path")
            seen.add(relative)
            target = self._path(relative)
            expected = self.offsets.get(relative, 0)
            if row.get("offset") != expected:
                raise ValueError("evidence transport offset drift")
            raw = base64.b64decode(row.get("data", ""), validate=True)
            if row.get("size") != len(raw) or row.get("sha256") != sha256(raw):
                raise ValueError("evidence transport chunk integrity failure")
            total_size = row.get("total_size")
            eof = row.get("eof")
            if (
                not isinstance(total_size, int)
                or isinstance(total_size, bool)
                or total_size < expected + len(raw)
                or eof is not (expected + len(raw) == total_size)
            ):
                raise ValueError("evidence transport extent changed")
            prior_size = self.remote_sizes.get(relative)
            if prior_size is not None and total_size < prior_size:
                raise ValueError("evidence remote file shrank")
            if relative in STREAM_FILES and raw and not raw.endswith(b"\n"):
                raise ValueError("partial evidence stream record")
            target.parent.mkdir(parents=True, exist_ok=True)
            mode = "ab" if expected else "xb"
            if raw:
                with target.open(mode) as stream:
                    stream.write(raw)
            elif expected == 0 and not target.exists():
                target.touch(exist_ok=False)
            self.offsets[relative] = expected + len(raw)
            self.remote_sizes[relative] = total_size
            if eof:
                self.complete.add(relative)
            else:
                self.complete.discard(relative)
            written.append({"path": relative, "bytes": len(raw)})
        disappeared = sorted(set(self.remote_sizes) - seen)
        if disappeared:
            raise ValueError("remote evidence disappeared: " + ", ".join(disappeared))
        record = {
            "sequence": envelope["sequence"],
            "received_at": received_at,
            "files": written,
            "pod_uid": self.identity.pod_uid,
            "container_id": self.identity.container_id,
            "worker_pid": self.identity.worker_pid,
            "worker_start_ticks": self.identity.worker_start_ticks,
            "config_sha256": self.identity.config_sha256,
            "process_state": envelope["process_state"],
        }
        self.sequence += 1
        self.last_received_at = received_at
        self.records.append(record)
        return record

    def finalize(self, *, require_success: bool) -> dict:
        required = set(FINAL_REQUIRED if require_success else {"workload-exit.json"})
        missing = sorted(name for name in required if not self._path(name).is_file())
        if missing:
            raise ValueError("required evidence missing: " + ", ".join(missing))
        incomplete = sorted(required - self.complete)
        if incomplete:
            raise ValueError("required evidence incomplete: " + ", ".join(incomplete))
        if require_success:
            terminal = json.loads(
                self._path("durable-terminal-manifest.json").read_text()
            )
            inventory = terminal.get("inventory")
            if (
                terminal.get("schema_version") != 1
                or terminal.get("terminal") is not True
                or terminal.get("status") != "PASS_CANDIDATE"
                or terminal.get("workload_succeeded") is not True
                or terminal.get("cleanup_complete") is not True
                or not isinstance(inventory, list)
            ):
                raise ValueError("durable terminal evidence is incomplete")
            inventory_digest = sha256(
                json.dumps(
                    inventory, sort_keys=True, separators=(",", ":")
                ).encode()
            )
            if terminal.get("inventory_sha256") != inventory_digest:
                raise ValueError("durable terminal inventory digest mismatch")
            observed = []
            inventory_paths = [item.get("path") for item in inventory]
            if (
                not all(isinstance(path, str) and path for path in inventory_paths)
                or inventory_paths != sorted(inventory_paths)
                or len(set(inventory_paths)) != len(inventory_paths)
            ):
                raise ValueError("durable terminal inventory paths are invalid")
            for item in inventory:
                relative = item.get("path")
                target = self._path(relative)
                raw = target.read_bytes()
                observed.append(
                    {"path": relative, "bytes": len(raw), "sha256": sha256(raw)}
                )
                if relative not in self.complete:
                    raise ValueError("durable inventory member is incomplete")
            if observed != inventory:
                raise ValueError("durable terminal inventory readback mismatch")
            capacity = terminal.get("capacity", {})
            terminal_bytes = self._path(
                "durable-terminal-manifest.json"
            ).stat().st_size
            inventory_bytes = sum(item["bytes"] for item in inventory)
            final_logical_bytes = inventory_bytes + terminal_bytes
            if (
                capacity.get("requested_bytes") != 1_073_741_824
                or capacity.get("evidence_used_bytes") != inventory_bytes
                or capacity.get("evidence_free_bytes")
                != 1_073_741_824 - inventory_bytes
                or final_logical_bytes > 939_524_096
                or capacity.get("filesystem_free_bytes", -1) - terminal_bytes
                < 134_217_728
            ):
                raise ValueError("durable terminal capacity watermark breached")
            summary = json.loads(
                self._path(
                    "state/yolo-pod-cgroup-a-measurement/measurement-contract.json"
                ).read_text()
            )
            if not (
                summary.get("workload_succeeded")
                and summary.get("qualification_complete")
                and summary.get("cgroup_resource_complete")
            ):
                raise ValueError("Pod-local qualification evidence is incomplete")
            cleanup = json.loads(self._path("cleanup-complete.json").read_text())
            if not (
                cleanup.get("worker_absent")
                and cleanup.get("owned_children_absent")
                and cleanup.get("scratch_absent")
            ):
                raise ValueError("owned cleanup markers are incomplete")
        self.finalized = True
        return {
            "status": "PASS" if require_success else "FAILURE_EVIDENCE_RETAINED",
            "transport_records": len(self.records),
            "transport_last_sequence": self.sequence,
            "identity": self.identity.__dict__,
            "required_files": sorted(required),
        }

    def verify_archive_fingerprint(self, rows: list[list]) -> None:
        archive = {name: (size, digest) for name, size, digest in rows}
        if set(archive) != set(self.remote_sizes):
            raise ValueError("archive inventory differs from evidence mirror")
        for name, remote_size in self.remote_sizes.items():
            if archive[name][0] != remote_size:
                raise ValueError("archive evidence size changed")
            if name in self.complete:
                raw = self._path(name).read_bytes()
                if len(raw) != remote_size or sha256(raw) != archive[name][1]:
                    raise ValueError("archive evidence digest differs from mirror")


def pull_once(
    mirror: IncrementalEvidenceMirror,
    remote_root: str,
    execute: Callable[[str], str],
    *,
    now: Callable[[], float],
) -> dict:
    """Execute one transport read and ingest it; any loss fails closed."""
    raw = execute(mirror.request_program(remote_root))
    return mirror.ingest(json.loads(raw), received_at=now())
