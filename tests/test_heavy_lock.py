"""scripts/heavy-lock: one holder at a time across processes, COMMAND's exit status otherwise."""

import os
import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/heavy-lock"


def run(lock: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "KP_HEAVY_LOCK": str(lock)}
    return subprocess.run([str(SCRIPT), *args], env=env, capture_output=True, text=True)


def test_runs_the_command_and_returns_its_status(tmp_path):
    assert run(tmp_path / "lock", "job", "--", "sh", "-c", "exit 3").returncode == 3
    assert run(tmp_path / "lock", "job").returncode == 2


def test_a_second_job_is_refused_while_the_first_runs(tmp_path):
    lock = tmp_path / "lock"
    env = {**os.environ, "KP_HEAVY_LOCK": str(lock)}
    first = subprocess.Popen([str(SCRIPT), "docling", "--", "sleep", "30"], env=env)
    try:
        deadline = time.monotonic() + 10
        while not (lock.exists() and lock.read_text().startswith("docling")):
            assert time.monotonic() < deadline, "first job never took the lock"
            time.sleep(0.05)

        second = run(lock, "d3", "--", "true")

        assert second.returncode == 75
        assert "taken by docling (pid " in second.stderr
    finally:
        first.kill()
        first.wait()
    assert run(lock, "d3", "--", "true").returncode == 0
