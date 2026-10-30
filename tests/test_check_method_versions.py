import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/check-method-versions"
PROFILE = "src/kp_processing/profiles/demo@1.yaml"
FORMULA = "src/kp_processing/methods/formula/"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def write(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "dev")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "test")
    write(tmp_path, PROFILE, "profile: demo@1\nreleased: true\nmethods:\n  formula@1: {}\n")
    write(
        tmp_path,
        "src/kp_processing/profiles/draft@1.yaml",
        "released: false\nmethods:\n  code@1: {}\n",
    )
    write(tmp_path, FORMULA + "__init__.py", 'ID = "formula"\nVERSION = 1\n')
    write(tmp_path, FORMULA + "prompt.txt", "Transcribe.\n")
    write(tmp_path, "src/kp_processing/methods/code/__init__.py", 'ID = "code"\nVERSION = 1\n')
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "work")
    return tmp_path


def check(repo: Path) -> subprocess.CompletedProcess[str]:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", "change")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "dev"], cwd=repo, capture_output=True, text=True
    )


def test_changing_a_released_method_without_a_version_bump_fails(repo):
    write(repo, FORMULA + "prompt.txt", "Transcribe as LaTeX.\n")

    result = check(repo)
    assert result.returncode == 1
    assert "formula" in result.stdout


def test_changing_a_released_method_with_a_version_bump_passes(repo):
    write(repo, FORMULA + "prompt.txt", "Transcribe as LaTeX.\n")
    write(repo, FORMULA + "__init__.py", 'ID = "formula"\nVERSION = 2\n')

    assert check(repo).returncode == 0


def test_modifying_a_released_profile_fails(repo):
    write(repo, PROFILE, "profile: demo@1\nreleased: true\nmethods:\n  formula@2: {}\n")

    result = check(repo)
    assert result.returncode == 1
    assert "demo@1.yaml" in result.stdout


def test_deleting_a_released_profile_fails(repo):
    (repo / PROFILE).unlink()

    assert check(repo).returncode == 1


def test_adding_a_new_profile_passes(repo):
    write(
        repo,
        "src/kp_processing/profiles/demo@2.yaml",
        "profile: demo@2\nreleased: true\nmethods:\n  formula@1: {}\n",
    )

    assert check(repo).returncode == 0


def test_methods_and_profiles_still_in_draft_may_change(repo):
    write(repo, "src/kp_processing/methods/code/extra.py", "X = 1\n")
    write(
        repo, "src/kp_processing/profiles/draft@1.yaml", "released: true\nmethods:\n  code@1: {}\n"
    )

    assert check(repo).returncode == 0
