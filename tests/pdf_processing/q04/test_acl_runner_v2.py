"""Local integration tests for the versioned ACL outer-admission runner."""

from io import StringIO
import json
from pathlib import Path
import unittest

from fake_clock import FakeClock
from outer_admission import OuterAdmissionRejected
from sentinel.acl_admission import (
    AclAdmissionCallbacks,
    ReservationIdentity,
    policy_from_capacity,
    run_outer_admission,
)
from sentinel.run_acl_v2 import (
    PHASE,
    TARGET_AVAILABLE_BYTES,
    build_capacity,
    build_runtime_command,
    launch_after_admission,
)

class CallbackInterrupted(BaseException):
    pass


class FailingStream:
    def write(self, _value):
        raise CallbackInterrupted("record interrupted")

    def flush(self):
        raise AssertionError("flush must not follow an interrupted write")


class AclRunnerV2(unittest.TestCase):
    def setUp(self):
        self.capacity = build_capacity(
            started_at=1_000.0,
            owner="test capacity owner",
            approval_reference="test-only authorization",
        )
        self.identity = ReservationIdentity(
            coordinator_uid="coordinator-uid",
            hostname="coordinator",
            pid=321,
            start_ticks=987_654,
            lock_device_major=0,
            lock_device_minor=91,
            lock_inode=123_456,
            token="reservation-token",
            phase=PHASE,
            reservation_path=Path("/reservation.json"),
            release_path=Path("/release"),
            hostname_path=Path("/etc/hostname"),
            proc_root=Path("/proc"),
        )

    def identity_reads(self, identity=None, *, process_state="S", lock_held=True):
        identity = identity or self.identity
        reservation = {
            "coordinator_uid": identity.coordinator_uid,
            "hostname": identity.hostname,
            "pid": identity.pid,
            "start_ticks": identity.start_ticks,
            "lock_device_major": identity.lock_device_major,
            "lock_device_minor": identity.lock_device_minor,
            "lock_inode": identity.lock_inode,
            "token": identity.token,
            "phase": identity.phase,
        }
        values = {
            identity.reservation_path: json.dumps(reservation),
            identity.hostname_path: identity.hostname + "\n",
            identity.proc_root / str(identity.pid) / "stat": (
                f"{identity.pid} (reservation holder) {process_state} "
                + " ".join(["0"] * 18 + [str(identity.start_ticks)] + ["0"] * 5)
            ),
            identity.proc_root / "locks": (
                "8: FLOCK ADVISORY WRITE "
                f"{identity.pid} 00:5b:{identity.lock_inode} 0 EOF\n"
                if lock_held
                else ""
            ),
        }
        return lambda path: values[path]

    def test_capacity_preserves_full_observation_workload_and_cleanup_budgets(self):
        self.assertEqual(self.capacity["ends_at"] - self.capacity["starts_at"], 1500)
        self.assertEqual(self.capacity["outer_observation_seconds"], 180)
        self.assertEqual(self.capacity["outer_continuous_seconds"], 60)
        self.assertEqual(
            self.capacity["outer_admission_available_bytes"],
            TARGET_AVAILABLE_BYTES,
        )
        self.assertEqual(self.capacity["minimum_work_seconds"], 825)
        self.assertEqual(self.capacity["cleanup_seconds"], 300)
        self.assertEqual(
            {
                "admission_seconds": self.capacity["admission_seconds"],
                "admission_available_bytes": self.capacity[
                    "admission_available_bytes"
                ],
                "min_available_bytes": self.capacity["min_available_bytes"],
                "max_cgroup_bytes": self.capacity["max_cgroup_bytes"],
                "max_full_psi": self.capacity["max_full_psi"],
                "max_sample_gap_seconds": self.capacity[
                    "max_sample_gap_seconds"
                ],
                "max_replacement_seconds": self.capacity[
                    "max_replacement_seconds"
                ],
            },
            {
                "admission_seconds": 60,
                "admission_available_bytes": 3_221_225_472,
                "min_available_bytes": 1_610_612_736,
                "max_cgroup_bytes": 3_221_225_472,
                "max_full_psi": 0,
                "max_sample_gap_seconds": 3,
                "max_replacement_seconds": 90,
            },
        )
        self.assertEqual(
            1500 - 180 - 825 - 300,
            195,
            "25-minute lease must retain a 195-second setup/verification margin",
        )

    def test_changed_active_guard_is_rejected_before_observation(self):
        changed = dict(self.capacity, max_sample_gap_seconds=4)

        with self.assertRaisesRegex(
            ValueError, "outer admission contract changed: max_sample_gap_seconds"
        ):
            policy_from_capacity(changed)

    def test_outer_and_per_case_admission_thresholds_are_distinct(self):
        self.assertEqual(
            self.capacity["outer_admission_available_bytes"],
            4_831_838_208,
        )
        self.assertEqual(
            self.capacity["outer_continuous_seconds"],
            60,
        )
        self.assertEqual(
            self.capacity["outer_observation_seconds"],
            180,
        )
        self.assertEqual(
            self.capacity["admission_available_bytes"],
            3_221_225_472,
        )
        self.assertEqual(self.capacity["admission_seconds"], 60)
        self.assertGreater(
            self.capacity["outer_admission_available_bytes"],
            self.capacity["admission_available_bytes"],
        )

    def test_identity_sample_and_record_callbacks_propagate_control_interrupts(self):
        callbacks = {
            "identity": AclAdmissionCallbacks(
                self.identity,
                StringIO(),
                sampler=lambda _proc, _cgroup: {},
                read_text=lambda _path: (_ for _ in ()).throw(
                    CallbackInterrupted("identity interrupted")
                ),
            ).verify_identity,
            "sample": AclAdmissionCallbacks(
                self.identity,
                StringIO(),
                sampler=lambda _proc, _cgroup: (_ for _ in ()).throw(
                    CallbackInterrupted("sample interrupted")
                ),
                read_text=self.identity_reads(),
            ).sample,
            "record": lambda: AclAdmissionCallbacks(
                self.identity,
                FailingStream(),
                sampler=lambda _proc, _cgroup: {},
                read_text=self.identity_reads(),
            ).record({"time": 1}),
        }

        for name, callback in callbacks.items():
            with self.subTest(name=name):
                with self.assertRaises(CallbackInterrupted):
                    callback()

    def test_outer_admission_records_resets_and_passes_before_launch(self):
        clock = FakeClock()
        samples = 0
        evidence = StringIO()

        def sample(_proc, _cgroup):
            nonlocal samples
            samples += 1
            return {
                "time": clock.time(),
                "available": TARGET_AVAILABLE_BYTES - 1 if samples == 1 else TARGET_AVAILABLE_BYTES,
                "psi_full_avg10": 0,
                "vm_oom_kill": 28,
                "memory_current": 1_000,
                "memory_events": {"oom_kill": 0},
            }

        callbacks = AclAdmissionCallbacks(
            self.identity,
            evidence,
            sampler=sample,
            read_text=self.identity_reads(),
            path_exists=lambda _path: False,
        )
        launched = []
        capacity = dict(self.capacity, ends_at=clock.time() + 1500)

        summary, runtime = launch_after_admission(
            lambda: run_outer_admission(
                capacity,
                callbacks,
                wall_time=clock.time,
                monotonic=clock.monotonic,
                sleep=clock.sleep,
            ),
            lambda: launched.append("runtime") or "driver",
            lease_ends_monotonic=clock.monotonic() + 1500,
            monotonic=clock.monotonic,
        )

        self.assertEqual(summary["resets"], 1)
        self.assertEqual(summary["continuous_seconds"], 60)
        self.assertEqual(runtime, "driver")
        self.assertEqual(launched, ["runtime"])
        self.assertEqual(len(evidence.getvalue().splitlines()), 62)

    def test_identity_drift_rejects_before_runtime_launch(self):
        clock = FakeClock()
        launched = []
        callbacks = AclAdmissionCallbacks(
            self.identity,
            StringIO(),
            sampler=lambda _proc, _cgroup: {
                "time": clock.time(),
                "available": TARGET_AVAILABLE_BYTES,
                "psi_full_avg10": 0,
                "vm_oom_kill": 28,
                "memory_current": 1_000,
                "memory_events": {"oom_kill": 0},
            },
            read_text=lambda path: (
                json.dumps(
                    {
                        "coordinator_uid": "changed",
                        "hostname": self.identity.hostname,
                        "pid": self.identity.pid,
                        "start_ticks": self.identity.start_ticks,
                        "lock_device_major": self.identity.lock_device_major,
                        "lock_device_minor": self.identity.lock_device_minor,
                        "lock_inode": self.identity.lock_inode,
                        "token": self.identity.token,
                        "phase": self.identity.phase,
                    }
                )
                if path == self.identity.reservation_path
                else self.identity_reads()(path)
            ),
            path_exists=lambda _path: False,
        )

        with self.assertRaisesRegex(OuterAdmissionRejected, "identity or ownership drift"):
            launch_after_admission(
                lambda: run_outer_admission(
                    dict(self.capacity, ends_at=clock.time() + 1500),
                    callbacks,
                    wall_time=clock.time,
                    monotonic=clock.monotonic,
                    sleep=clock.sleep,
                ),
                lambda: launched.append("runtime"),
                lease_ends_monotonic=clock.monotonic() + 1500,
                monotonic=clock.monotonic,
            )

        self.assertEqual(launched, [])

    def test_dead_or_unlocked_reservation_rejects_before_runtime_launch(self):
        cases = {
            "zombie": self.identity_reads(process_state="Z"),
            "unlocked": self.identity_reads(lock_held=False),
        }
        for label, reader in cases.items():
            with self.subTest(label=label):
                clock = FakeClock()
                launched = []
                callbacks = AclAdmissionCallbacks(
                    self.identity,
                    StringIO(),
                    sampler=lambda _proc, _cgroup: {
                        "time": clock.time(),
                        "available": TARGET_AVAILABLE_BYTES,
                        "psi_full_avg10": 0,
                        "vm_oom_kill": 28,
                        "memory_current": 1_000,
                        "memory_events": {"oom_kill": 0},
                    },
                    read_text=reader,
                    path_exists=lambda _path: False,
                )

                with self.assertRaisesRegex(
                    OuterAdmissionRejected, "identity or ownership drift"
                ):
                    launch_after_admission(
                        lambda: run_outer_admission(
                            dict(self.capacity, ends_at=clock.time() + 1500),
                            callbacks,
                            wall_time=clock.time,
                            monotonic=clock.monotonic,
                            sleep=clock.sleep,
                        ),
                        lambda: launched.append("runtime"),
                        lease_ends_monotonic=clock.monotonic() + 1500,
                        monotonic=clock.monotonic,
                    )

                self.assertEqual(launched, [])

    def test_launch_rechecks_workload_and_cleanup_after_admission_returns(self):
        clock = FakeClock()
        launched = []
        lease_ends_monotonic = clock.monotonic() + 1500

        def delayed_success():
            clock.sleep(376)
            return {"passed": True}

        with self.assertRaisesRegex(RuntimeError, "workload and cleanup reserve"):
            launch_after_admission(
                delayed_success,
                lambda: launched.append("runtime"),
                lease_ends_monotonic=lease_ends_monotonic,
                monotonic=clock.monotonic,
            )

        self.assertEqual(launched, [])

    def test_runtime_command_is_new_acl_fixture_09_matrix_only(self):
        command = build_runtime_command()

        self.assertIn("--phase matrix", command)
        self.assertIn("--fixture 09", command)
        self.assertIn("--name " + PHASE, command)
        self.assertIn(" 825s ", command)
        self.assertIn("825s sh -eu -c", command)
        self.assertLess(command.index(" 825s "), command.index("verify_bundle"))
        self.assertNotIn("--phase init", command)
        self.assertNotIn("--fixture 10", command)
        self.assertNotIn("scale", command)


if __name__ == "__main__":
    unittest.main()
