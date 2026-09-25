"""Deterministic outer capacity-owner admission tests; no live runtime or inference."""

from dataclasses import replace
import signal
import time
import unittest
from unittest.mock import patch

from fake_clock import FakeClock
import outer_admission
from outer_admission import (
    OuterAdmissionPolicy,
    OuterAdmissionRejected,
    observe_capacity,
)

class OuterAdmission(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.policy = OuterAdmissionPolicy(
            available_bytes=100,
            continuous_seconds=60,
            observation_seconds=180,
            sample_interval_seconds=1,
            max_sample_gap_seconds=2,
            max_cgroup_bytes=500,
            expected_vm_oom_kill=7,
            expected_cgroup_oom_kill=0,
            minimum_work_seconds=20,
            cleanup_seconds=120,
        )

    def row(self, *, available=100, psi=0.0, timestamp=None, vm_oom=7):
        return {
            "time": self.clock.time() if timestamp is None else timestamp,
            "available": available,
            "psi_full_avg10": psi,
            "vm_oom_kill": vm_oom,
            "memory_current": 50,
            "memory_events": {"oom_kill": 0},
        }

    def observe(self, sample, *, lease_seconds=400, policy=None, verify_identity=None):
        recorded = []
        result = observe_capacity(
            policy or self.policy,
            lease_ends_at=self.clock.time() + lease_seconds,
            sample=sample,
            verify_identity=verify_identity or (lambda: None),
            record=recorded.append,
            wall_time=self.clock.time,
            monotonic=self.clock.monotonic,
            sleep=self.clock.sleep,
        )
        return result, recorded

    def test_initial_miss_then_sixty_continuous_seconds_passes(self):
        calls = 0

        def sample():
            nonlocal calls
            calls += 1
            return self.row(available=99 if calls == 1 else 100)

        result, recorded = self.observe(sample)

        self.assertTrue(result["passed"])
        self.assertEqual(result["continuous_seconds"], 60)
        self.assertEqual(result["resets"], 1)
        self.assertEqual(result["samples"], 62)
        self.assertEqual(len(recorded), 62)

    def test_fluctuation_resets_instead_of_stitching_qualified_samples(self):
        calls = 0

        def sample():
            nonlocal calls
            calls += 1
            return self.row(
                available=99 if calls == 31 else 100,
                psi=0.01 if calls == 61 else 0,
            )

        result, _ = self.observe(sample)

        self.assertEqual(result["observed_seconds"], 121)
        self.assertEqual(result["resets"], 2)
        self.assertEqual(result["samples"], 122)

    def test_observation_expires_at_180_seconds_without_retry(self):
        recorded = []
        with self.assertRaisesRegex(
            OuterAdmissionRejected, "observation deadline"
        ) as caught:
            observe_capacity(
                self.policy,
                lease_ends_at=self.clock.time() + 500,
                sample=lambda: self.row(available=99),
                verify_identity=lambda: None,
                record=recorded.append,
                wall_time=self.clock.time,
                monotonic=self.clock.monotonic,
                sleep=self.clock.sleep,
            )

        self.assertFalse(caught.exception.fatal)
        self.assertEqual(self.clock.monotonic(), 180)
        self.assertEqual(len(recorded), 180)

    def test_qualifying_interval_at_deadline_rejects_without_persistence_budget(self):
        def sample():
            if self.clock.monotonic() == 179:
                self.clock.sleep(1)
            return self.row(available=100 if self.clock.monotonic() >= 120 else 99)

        with self.assertRaisesRegex(
            OuterAdmissionRejected, "observation deadline"
        ) as caught:
            self.observe(sample, lease_seconds=500)

        self.assertFalse(caught.exception.fatal)
        self.assertEqual(len(caught.exception.samples), 180)

    def test_sample_completing_after_deadline_cannot_pass(self):
        policy = replace(
            self.policy,
            continuous_seconds=1,
            observation_seconds=1,
            minimum_work_seconds=1,
            cleanup_seconds=1,
        )
        calls = 0

        def sample():
            nonlocal calls
            calls += 1
            self.clock.sleep(1.1)
            return self.row()

        with self.assertRaisesRegex(OuterAdmissionRejected, "observation deadline"):
            self.observe(sample, lease_seconds=10, policy=policy)

    def test_new_vm_or_cgroup_oom_rejects_immediately_and_preserves_sample(self):
        cases = {
            "VM": lambda: self.row(vm_oom=8),
            "cgroup": lambda: {**self.row(), "memory_events": {"oom_kill": 1}},
        }
        for label, sample in cases.items():
            with self.subTest(label=label):
                self.clock = FakeClock()
                recorded = []
                with self.assertRaisesRegex(
                    OuterAdmissionRejected, "new .* OOM"
                ) as caught:
                    observe_capacity(
                        self.policy,
                        lease_ends_at=self.clock.time() + 400,
                        sample=sample,
                        verify_identity=lambda: None,
                        record=recorded.append,
                        wall_time=self.clock.time,
                        monotonic=self.clock.monotonic,
                        sleep=self.clock.sleep,
                    )
                self.assertTrue(caught.exception.fatal)
                self.assertEqual(len(recorded), 1)
                self.assertEqual(caught.exception.samples, recorded)
                self.assertEqual(self.clock.monotonic(), 0)

    def test_missing_or_stale_telemetry_rejects_immediately(self):
        cases = {
            "missing": lambda: {"time": self.clock.time()},
            "invalid": lambda: {**self.row(), "available": None},
            "stale": lambda: self.row(timestamp=self.clock.time() - 3),
        }
        for label, sample in cases.items():
            with self.subTest(label=label):
                clock = FakeClock()
                self.clock = clock
                recorded = []
                with self.assertRaises(OuterAdmissionRejected) as caught:
                    observe_capacity(
                        self.policy,
                        lease_ends_at=clock.time() + 400,
                        sample=sample,
                        verify_identity=lambda: None,
                        record=recorded.append,
                        wall_time=clock.time,
                        monotonic=clock.monotonic,
                        sleep=clock.sleep,
                    )
                self.assertTrue(caught.exception.fatal)
                self.assertEqual(len(recorded), 1)
                self.assertEqual(clock.monotonic(), 0)

    def test_unavailable_telemetry_rejects_immediately(self):
        def unavailable():
            raise OSError("sampler transport closed")

        with self.assertRaisesRegex(
            OuterAdmissionRejected, "telemetry unavailable"
        ) as caught:
            self.observe(unavailable)

        self.assertTrue(caught.exception.fatal)
        self.assertEqual(caught.exception.samples, [])
        self.assertEqual(self.clock.monotonic(), 0)

    def test_telemetry_gap_rejects_immediately(self):
        calls = 0

        def sample():
            nonlocal calls
            calls += 1
            timestamp = 998 if calls == 1 else self.clock.time()
            return self.row(timestamp=timestamp)

        with self.assertRaisesRegex(OuterAdmissionRejected, "sample gap") as caught:
            self.observe(sample)

        self.assertTrue(caught.exception.fatal)
        self.assertEqual(len(caught.exception.samples), 2)
        self.assertEqual(self.clock.monotonic(), 1)

    def test_identity_or_ownership_drift_rejects_before_another_sample(self):
        checks = 0

        def verify():
            nonlocal checks
            checks += 1
            if checks == 2:
                raise RuntimeError("coordinator UID changed")

        with self.assertRaisesRegex(
            OuterAdmissionRejected, "identity or ownership drift"
        ) as caught:
            self.observe(lambda: self.row(), verify_identity=verify)

        self.assertTrue(caught.exception.fatal)
        self.assertEqual(len(caught.exception.samples), 1)
        self.assertEqual(self.clock.monotonic(), 1)

    def test_identity_check_crossing_deadline_does_not_start_sampling(self):
        cases = {
            "observation": {
                "advance": 181,
                "lease": 500,
                "reason": "observation deadline",
            },
            "work-and-cleanup": {
                "advance": 61,
                "lease": 200,
                "reason": "workload and cleanup reserve",
            },
        }
        for label, case in cases.items():
            with self.subTest(label=label):
                self.clock = FakeClock()
                sampled = False

                def verify():
                    self.clock.sleep(case["advance"])

                def sample():
                    nonlocal sampled
                    sampled = True
                    return self.row()

                with self.assertRaisesRegex(
                    OuterAdmissionRejected, case["reason"]
                ):
                    self.observe(
                        sample,
                        lease_seconds=case["lease"],
                        verify_identity=verify,
                    )

                self.assertFalse(sampled)
                self.assertEqual(self.clock.monotonic(), case["advance"])

    def test_sample_crossing_lease_cutoff_cannot_pass(self):
        def sample():
            self.clock.sleep(61)
            return self.row()

        with self.assertRaisesRegex(
            OuterAdmissionRejected, "workload and cleanup reserve"
        ) as caught:
            self.observe(sample, lease_seconds=200)

        self.assertFalse(caught.exception.fatal)
        self.assertEqual(len(caught.exception.samples), 1)

    def test_cleanup_and_work_reserve_must_fit_before_observation(self):
        called = False

        def sample():
            nonlocal called
            called = True
            return self.row()

        with self.assertRaisesRegex(
            OuterAdmissionRejected, "insufficient capacity lease"
        ) as caught:
            self.observe(sample, lease_seconds=199)

        self.assertTrue(caught.exception.fatal)
        self.assertFalse(called)

    def test_exact_lease_boundary_rejects_without_persistence_budget(self):
        policy = replace(self.policy, observation_seconds=60)

        def sample():
            if self.clock.monotonic() == 59:
                self.clock.sleep(1)
            return self.row()

        with self.assertRaisesRegex(OuterAdmissionRejected, "deadline") as caught:
            self.observe(sample, lease_seconds=200, policy=policy)

        self.assertFalse(caught.exception.fatal)
        self.assertEqual(len(caught.exception.samples), 60)

    def test_blocked_callback_is_interrupted_by_remaining_deadline(self):
        policy = OuterAdmissionPolicy(
            available_bytes=100,
            continuous_seconds=0.01,
            observation_seconds=0.02,
            sample_interval_seconds=0.001,
            max_sample_gap_seconds=1,
            max_cgroup_bytes=500,
            expected_vm_oom_kill=7,
            expected_cgroup_oom_kill=0,
            minimum_work_seconds=0.01,
            cleanup_seconds=0.01,
        )
        started = time.monotonic()
        with self.assertRaisesRegex(OuterAdmissionRejected, "observation deadline"):
            observe_capacity(
                policy,
                lease_ends_at=time.time() + 1,
                sample=lambda: self.row(timestamp=time.time()),
                verify_identity=lambda: time.sleep(1),
                record=lambda _row: None,
            )
        self.assertLess(time.monotonic() - started, 0.5)

    def test_blocked_evidence_write_is_interrupted_and_sample_remains_attached(self):
        policy = OuterAdmissionPolicy(
            available_bytes=100,
            continuous_seconds=0.01,
            observation_seconds=0.02,
            sample_interval_seconds=0.001,
            max_sample_gap_seconds=1,
            max_cgroup_bytes=500,
            expected_vm_oom_kill=7,
            expected_cgroup_oom_kill=0,
            minimum_work_seconds=0.01,
            cleanup_seconds=0.01,
        )
        with self.assertRaisesRegex(
            OuterAdmissionRejected, "observation deadline"
        ) as caught:
            observe_capacity(
                policy,
                lease_ends_at=time.time() + 1,
                sample=lambda: self.row(timestamp=time.time()),
                verify_identity=lambda: None,
                record=lambda _row: time.sleep(1),
            )
        self.assertEqual(len(caught.exception.samples), 1)

    def test_timer_expiry_while_arming_restores_handler_and_cancels_timer(self):
        previous_handler = signal.getsignal(signal.SIGALRM)
        timer_values = []

        def expire_while_arming(_kind, seconds):
            timer_values.append(seconds)
            if seconds > 0:
                signal.getsignal(signal.SIGALRM)(signal.SIGALRM, None)
            return (0.0, 0.0)

        try:
            with patch.object(
                outer_admission.signal,
                "setitimer",
                side_effect=expire_while_arming,
            ):
                with self.assertRaisesRegex(
                    OuterAdmissionRejected, "observation deadline"
                ):
                    self.observe(lambda: self.row())

            self.assertEqual(signal.getsignal(signal.SIGALRM), previous_handler)
            self.assertGreater(timer_values[0], 0)
            self.assertEqual(timer_values[-1], 0)
        finally:
            signal.signal(signal.SIGALRM, previous_handler)

    def test_callback_cannot_swallow_deadline_with_exception_handler(self):
        swallowed = False

        def catches_exception():
            nonlocal swallowed
            try:
                signal.raise_signal(signal.SIGALRM)
            except Exception:
                swallowed = True

        with self.assertRaisesRegex(
            OuterAdmissionRejected, "observation deadline"
        ) as caught:
            self.observe(lambda: self.row(), verify_identity=catches_exception)

        self.assertFalse(caught.exception.fatal)
        self.assertFalse(swallowed)
        self.assertEqual(caught.exception.samples, [])


if __name__ == "__main__":
    unittest.main()
