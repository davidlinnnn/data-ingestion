"""Cooperative local callbacks for versioned ACL outer admission."""

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import time

from outer_admission import (
    OuterAdmissionPolicy,
    OuterAdmissionRejected,
    observe_capacity,
)
from telemetry import sample as linux_sample


WINDOW_SECONDS = 1_500
OBSERVATION_SECONDS = 180
CONTINUOUS_SECONDS = 60
WORKLOAD_SECONDS = 825
CLEANUP_SECONDS = 300
SAMPLE_INTERVAL_SECONDS = 1
TARGET_AVAILABLE_BYTES = 4_831_838_208
PER_CASE_AVAILABLE_BYTES = 3_221_225_472
EXPECTED_VM_OOM_KILL = 28
EXPECTED_CGROUP_OOM_KILL = 0


@dataclass(frozen=True)
class ReservationIdentity:
    """Exact local identities rechecked before every telemetry sample."""

    coordinator_uid: str
    hostname: str
    pid: int
    start_ticks: int
    lock_device_major: int
    lock_device_minor: int
    lock_inode: int
    token: str
    phase: str
    reservation_path: Path
    release_path: Path
    hostname_path: Path = Path("/etc/hostname")
    proc_root: Path = Path("/proc")


def _proc_identity(stat_text):
    """Read Linux /proc state and field 22 despite spaces in process comm."""
    closing = stat_text.rfind(")")
    if closing < 0:
        raise ValueError("reservation holder process identity unavailable")
    fields = stat_text[closing + 1 :].split()
    if len(fields) <= 19:
        raise ValueError("reservation holder process identity incomplete")
    state = fields[0]
    if state in {"Z", "X", "x"}:
        raise ValueError("reservation holder is not live")
    return state, int(fields[19])


def _reservation_lock_held(locks_text, identity):
    for line in locks_text.splitlines():
        fields = line.split()
        if len(fields) < 6 or fields[1] != "FLOCK" or fields[3] != "WRITE":
            continue
        device_major, device_minor, inode = fields[5].split(":")
        if (
            int(fields[4]) == identity.pid
            and int(device_major, 16) == identity.lock_device_major
            and int(device_minor, 16) == identity.lock_device_minor
            and int(inode) == identity.lock_inode
        ):
            return True
    return False


class AclAdmissionCallbacks:
    """Small adapter over bounded local files; no callback catches control flow."""

    def __init__(
        self,
        identity,
        evidence_stream,
        *,
        sampler=linux_sample,
        read_text=None,
        path_exists=None,
        cgroup_root=Path("/sys/fs/cgroup"),
    ):
        self.identity = identity
        self.evidence_stream = evidence_stream
        self.sampler = sampler
        self.read_text = read_text or (lambda path: path.read_text())
        self.path_exists = path_exists or (
            lambda path: any(entry.name == path.name for entry in path.parent.iterdir())
        )
        self.cgroup_root = cgroup_root

    def verify_identity(self):
        actual = json.loads(self.read_text(self.identity.reservation_path))
        expected = {
            "coordinator_uid": self.identity.coordinator_uid,
            "hostname": self.identity.hostname,
            "pid": self.identity.pid,
            "start_ticks": self.identity.start_ticks,
            "lock_device_major": self.identity.lock_device_major,
            "lock_device_minor": self.identity.lock_device_minor,
            "lock_inode": self.identity.lock_inode,
            "token": self.identity.token,
            "phase": self.identity.phase,
        }
        if actual != expected:
            raise ValueError("reservation identity changed")
        if self.read_text(self.identity.hostname_path).strip() != self.identity.hostname:
            raise ValueError("coordinator hostname changed")
        stat_path = self.identity.proc_root / str(self.identity.pid) / "stat"
        _, start_ticks = _proc_identity(self.read_text(stat_path))
        if start_ticks != self.identity.start_ticks:
            raise ValueError("reservation holder PID identity changed")
        if not _reservation_lock_held(
            self.read_text(self.identity.proc_root / "locks"), self.identity
        ):
            raise ValueError("reservation holder no longer owns the qualification lock")
        if self.path_exists(self.identity.release_path):
            raise ValueError("reservation was released")

    def sample(self):
        return self.sampler(self.identity.proc_root, self.cgroup_root)

    def record(self, row):
        payload = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        written = self.evidence_stream.write(payload)
        if written is not None and written != len(payload):
            raise OSError("short admission evidence write")
        self.evidence_stream.flush()


def policy_from_capacity(
    capacity, *, expected_vm_oom_kill=EXPECTED_VM_OOM_KILL
):
    required = {
        "admission_seconds": CONTINUOUS_SECONDS,
        "admission_available_bytes": PER_CASE_AVAILABLE_BYTES,
        "min_available_bytes": 1_610_612_736,
        "max_cgroup_bytes": 3_221_225_472,
        "max_full_psi": 0,
        "max_sample_gap_seconds": 3,
        "max_replacement_seconds": 90,
        "outer_observation_seconds": OBSERVATION_SECONDS,
        "outer_continuous_seconds": CONTINUOUS_SECONDS,
        "outer_admission_available_bytes": TARGET_AVAILABLE_BYTES,
        "minimum_work_seconds": WORKLOAD_SECONDS,
        "cleanup_seconds": CLEANUP_SECONDS,
        "expected_vm_oom_kill": expected_vm_oom_kill,
        "expected_cgroup_oom_kill": EXPECTED_CGROUP_OOM_KILL,
    }
    for name, value in required.items():
        if capacity.get(name) != value:
            raise ValueError("ACL outer admission contract changed: " + name)
    if capacity.get("ends_at", 0) - capacity.get("starts_at", 0) != WINDOW_SECONDS:
        raise ValueError("ACL capacity lease must be exactly 25 minutes")
    return OuterAdmissionPolicy(
        available_bytes=TARGET_AVAILABLE_BYTES,
        continuous_seconds=CONTINUOUS_SECONDS,
        observation_seconds=OBSERVATION_SECONDS,
        sample_interval_seconds=SAMPLE_INTERVAL_SECONDS,
        max_sample_gap_seconds=capacity["max_sample_gap_seconds"],
        max_cgroup_bytes=capacity["max_cgroup_bytes"],
        expected_vm_oom_kill=expected_vm_oom_kill,
        expected_cgroup_oom_kill=EXPECTED_CGROUP_OOM_KILL,
        minimum_work_seconds=WORKLOAD_SECONDS,
        cleanup_seconds=CLEANUP_SECONDS,
    )


def run_outer_admission(
    capacity,
    callbacks,
    *,
    expected_vm_oom_kill=EXPECTED_VM_OOM_KILL,
    wall_time=time.time,
    monotonic=time.monotonic,
    sleep=time.sleep,
):
    """Run admission before the caller receives permission to launch runtime."""
    return observe_capacity(
        policy_from_capacity(
            capacity, expected_vm_oom_kill=expected_vm_oom_kill
        ),
        lease_ends_at=capacity["ends_at"],
        sample=callbacks.sample,
        verify_identity=callbacks.verify_identity,
        record=callbacks.record,
        wall_time=wall_time,
        monotonic=monotonic,
        sleep=sleep,
    )


def identity_from_reservation(
    reservation,
    *,
    expected_coordinator_uid,
    expected_phase,
    expected_token,
    reservation_path,
    release_path,
):
    if reservation.get("coordinator_uid") != expected_coordinator_uid:
        raise ValueError("unexpected coordinator UID in reservation")
    if reservation.get("phase") != expected_phase:
        raise ValueError("unexpected phase in reservation")
    if reservation.get("token") != expected_token:
        raise ValueError("unexpected reservation token")
    return ReservationIdentity(
        coordinator_uid=reservation["coordinator_uid"],
        hostname=reservation["hostname"],
        pid=reservation["pid"],
        start_ticks=reservation["start_ticks"],
        lock_device_major=reservation["lock_device_major"],
        lock_device_minor=reservation["lock_device_minor"],
        lock_inode=reservation["lock_inode"],
        token=expected_token,
        phase=reservation["phase"],
        reservation_path=reservation_path,
        release_path=release_path,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capacity", type=Path, required=True)
    parser.add_argument("--reservation", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--coordinator-uid", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--reservation-token", required=True)
    parser.add_argument(
        "--expected-vm-oom-kill", type=int, default=EXPECTED_VM_OOM_KILL
    )
    args = parser.parse_args(argv)

    capacity = json.loads(args.capacity.read_text())
    reservation = json.loads(args.reservation.read_text())
    identity = identity_from_reservation(
        reservation,
        expected_coordinator_uid=args.coordinator_uid,
        expected_phase=args.phase,
        expected_token=args.reservation_token,
        reservation_path=args.reservation,
        release_path=args.release,
    )
    with args.evidence.open("x", buffering=1) as stream:
        callbacks = AclAdmissionCallbacks(identity, stream)
        try:
            summary = run_outer_admission(
                capacity,
                callbacks,
                expected_vm_oom_kill=args.expected_vm_oom_kill,
            )
        except OuterAdmissionRejected as error:
            outcome = {
                "passed": False,
                "reason": error.reason,
                "fatal": error.fatal,
                "resets": error.resets,
                "samples": len(error.samples),
            }
            args.result.open("x").write(json.dumps(outcome, sort_keys=True) + "\n")
            raise
    args.result.open("x").write(json.dumps(summary, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
