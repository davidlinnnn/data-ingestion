"""Bounded continuous capacity admission before any workflow or inference starts."""

from dataclasses import dataclass
import math
import signal
import threading
import time


class OuterAdmissionRejected(ValueError):
    """Fail-closed admission outcome with the observations already retained."""

    def __init__(self, reason, *, samples, resets, fatal):
        super().__init__(reason)
        self.reason = reason
        self.samples = samples
        self.resets = resets
        self.fatal = fatal


class _CallbackDeadlineExceeded(BaseException):
    """Internal alarm control flow that ordinary callback handlers cannot swallow."""

    pass


class _CallbackWatchdogUnavailable(RuntimeError):
    pass


def _call_with_timeout(operation, timeout_seconds):
    """Bound one cooperative local callback with the remaining alarm budget."""
    if timeout_seconds <= 0:
        raise _CallbackDeadlineExceeded("no callback budget remains")
    if threading.current_thread() is not threading.main_thread():
        raise _CallbackWatchdogUnavailable("callback watchdog requires main thread")
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise _CallbackWatchdogUnavailable("an existing real-time timer is active")
    previous_handler = signal.getsignal(signal.SIGALRM)

    def expired(_signum, _frame):
        raise _CallbackDeadlineExceeded("capacity callback exceeded remaining budget")

    handler_installed = False
    try:
        signal.signal(signal.SIGALRM, expired)
        handler_installed = True
        signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
        return operation()
    finally:
        if handler_installed:
            try:
                signal.setitimer(signal.ITIMER_REAL, 0)
            finally:
                signal.signal(signal.SIGALRM, previous_handler)


@dataclass(frozen=True)
class OuterAdmissionPolicy:
    available_bytes: int
    continuous_seconds: float
    observation_seconds: float
    sample_interval_seconds: float
    max_sample_gap_seconds: float
    max_cgroup_bytes: int
    expected_vm_oom_kill: int
    expected_cgroup_oom_kill: int
    minimum_work_seconds: float
    cleanup_seconds: float

    def __post_init__(self):
        positive = (
            self.available_bytes,
            self.continuous_seconds,
            self.observation_seconds,
            self.sample_interval_seconds,
            self.max_sample_gap_seconds,
            self.max_cgroup_bytes,
            self.minimum_work_seconds,
            self.cleanup_seconds,
        )
        if not all(
            type(value) in (int, float) and math.isfinite(value) and value > 0
            for value in positive
        ):
            raise ValueError("outer admission policy requires finite positive bounds")
        if self.continuous_seconds > self.observation_seconds:
            raise ValueError("continuous admission exceeds observation bound")


def observe_capacity(
    policy,
    *,
    lease_ends_at,
    sample,
    verify_identity,
    record,
    wall_time=time.time,
    monotonic=time.monotonic,
    sleep=time.sleep,
):
    """Wait for one continuous qualifying interval within fixed lease bounds.

    Memory or PSI misses reset the interval. Transport, telemetry integrity,
    ownership and hard resource guards reject immediately. Every returned sample
    is handed to ``record`` before it is evaluated.
    """
    started_wall = wall_time()
    started_monotonic = monotonic()
    observation_deadline = started_monotonic + policy.observation_seconds
    latest_work_start = started_monotonic + (
        lease_ends_at
        - started_wall
        - policy.cleanup_seconds
        - policy.minimum_work_seconds
    )
    deadline = min(observation_deadline, latest_work_start)
    deadline_reason = (
        "insufficient workload and cleanup reserve after capacity observation"
        if latest_work_start < observation_deadline
        else "outer capacity observation deadline expired"
    )
    rows = []
    resets = 0
    streak_started = None
    previous_timestamp = None

    def reject(reason, *, fatal):
        raise OuterAdmissionRejected(reason, samples=list(rows), resets=resets, fatal=fatal)

    def bounded(operation, unavailable_reason):
        remaining = deadline - monotonic()
        if remaining <= 0:
            reject(deadline_reason, fatal=False)
        try:
            return _call_with_timeout(operation, remaining)
        except _CallbackDeadlineExceeded:
            reject(deadline_reason, fatal=False)
        except _CallbackWatchdogUnavailable as error:
            reject("callback watchdog unavailable: " + str(error), fatal=True)
        except Exception as error:
            reject(unavailable_reason + str(error), fatal=True)

    if deadline - started_monotonic < policy.continuous_seconds:
        reject("insufficient capacity lease for admission, work and cleanup", fatal=True)

    while True:
        now_monotonic = monotonic()
        if now_monotonic > deadline:
            reject(deadline_reason, fatal=False)
        bounded(verify_identity, "identity or ownership drift: ")
        if monotonic() > deadline:
            reject(deadline_reason, fatal=False)
        row = bounded(sample, "telemetry unavailable: ")
        rows.append(row)
        bounded(lambda: record(row), "telemetry persistence unavailable: ")
        now_wall = wall_time()
        observed_monotonic = monotonic()
        required = (
            "time",
            "available",
            "psi_full_avg10",
            "vm_oom_kill",
            "memory_current",
            "memory_events",
        )
        if not isinstance(row, dict) or any(name not in row for name in required):
            reject("telemetry unavailable or incomplete", fatal=True)
        numeric = (
            "time",
            "available",
            "psi_full_avg10",
            "vm_oom_kill",
            "memory_current",
        )
        if any(
            type(row[name]) not in (int, float) or not math.isfinite(row[name])
            for name in numeric
        ):
            reject("telemetry unavailable or invalid", fatal=True)
        timestamp = row["time"]
        age = now_wall - timestamp
        if age < 0 or age > policy.max_sample_gap_seconds:
            reject("telemetry stale or future-dated", fatal=True)
        if previous_timestamp is not None:
            gap = timestamp - previous_timestamp
            if gap <= 0 or gap > policy.max_sample_gap_seconds:
                reject("telemetry sample gap exceeded", fatal=True)
        previous_timestamp = timestamp
        events = row["memory_events"]
        if not isinstance(events, dict) or "oom_kill" not in events:
            reject("telemetry unavailable or incomplete", fatal=True)
        if type(events["oom_kill"]) not in (int, float) or not math.isfinite(
            events["oom_kill"]
        ):
            reject("telemetry unavailable or invalid", fatal=True)
        if row["vm_oom_kill"] != policy.expected_vm_oom_kill:
            reject("new VM OOM", fatal=True)
        if events["oom_kill"] != policy.expected_cgroup_oom_kill:
            reject("new cgroup OOM", fatal=True)
        if row["memory_current"] > policy.max_cgroup_bytes:
            reject("cgroup budget exceeded", fatal=True)
        if observed_monotonic > deadline:
            reject(deadline_reason, fatal=False)

        qualifies = (
            row["available"] >= policy.available_bytes
            and row["psi_full_avg10"] == 0
        )
        if qualifies:
            if streak_started is None:
                streak_started = observed_monotonic
            duration = observed_monotonic - streak_started
            if duration >= policy.continuous_seconds:
                return {
                    "passed": True,
                    "samples": len(rows),
                    "resets": resets,
                    "continuous_seconds": duration,
                    "observed_seconds": observed_monotonic - started_monotonic,
                    "minimum_available": min(item["available"] for item in rows),
                    "maximum_cgroup": max(item["memory_current"] for item in rows),
                    "maximum_psi": max(item["psi_full_avg10"] for item in rows),
                    "oom_values": sorted({item["vm_oom_kill"] for item in rows}),
                }
        else:
            resets += 1
            streak_started = None

        now_monotonic = monotonic()
        if now_monotonic >= deadline:
            reject(deadline_reason, fatal=False)
        sleep(min(policy.sample_interval_seconds, deadline - now_monotonic))
