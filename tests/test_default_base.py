import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/default-base"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def commit(repo: Path, message: str) -> None:
    git(repo, "commit", "-q", "--allow-empty", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """origin/dev four commits long, with origin/release/paper-pdf-1 opened at its second."""
    git(tmp_path, "init", "-q", "-b", "dev")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "test")
    commit(tmp_path, "first")
    commit(tmp_path, "release of paper-pdf@1")
    git(tmp_path, "update-ref", "refs/remotes/origin/release/paper-pdf-1", "HEAD")
    commit(tmp_path, "later work")
    commit(tmp_path, "a parallel session's merge")
    git(tmp_path, "update-ref", "refs/remotes/origin/dev", "HEAD")
    return tmp_path


def default_base(repo: Path) -> str:
    return subprocess.run([SCRIPT], cwd=repo, check=True, capture_output=True, text=True).stdout


def test_a_task_branch_is_based_on_dev_even_when_dev_has_moved_on(repo):
    git(repo, "checkout", "-q", "-b", "impl/1-task", "origin/dev~1")
    commit(repo, "task work")

    assert default_base(repo) == "origin/dev\n"


def test_a_patch_branch_is_based_on_the_release_branch_it_started_from(repo):
    git(repo, "checkout", "-q", "-b", "impl/2-patch", "origin/release/paper-pdf-1")
    commit(repo, "patch")

    assert default_base(repo) == "origin/release/paper-pdf-1\n"


def test_a_patch_branch_stays_on_its_release_branch_after_an_earlier_patch(repo):
    git(repo, "checkout", "-q", "-b", "earlier", "origin/release/paper-pdf-1")
    commit(repo, "earlier patch")
    git(repo, "update-ref", "refs/remotes/origin/release/paper-pdf-1", "HEAD")
    git(repo, "checkout", "-q", "-b", "impl/3-patch")
    commit(repo, "patch")

    assert default_base(repo) == "origin/release/paper-pdf-1\n"
