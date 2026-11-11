import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/check-method-versions"
PROFILE = "src/kp_canonicalization/profiles/demo@1.yaml"
DEV_PROFILE = "tests/profiles/demo-dev.yaml"
FORMULA = "src/kp_canonicalization/methods/formula/"


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
    write(tmp_path, PROFILE, "profile: demo@1\nmethods:\n  formula@1: {}\n")
    write(tmp_path, DEV_PROFILE, "profile: demo@1\nmethods:\n  code@1: {}\n")
    write(tmp_path, "src/kp_canonicalization/profiles/README.md", "How to release.\n")
    write(tmp_path, FORMULA + "__init__.py", 'ID = "formula"\nVERSION = 1\n')
    write(tmp_path, FORMULA + "prompt.txt", "Transcribe.\n")
    write(
        tmp_path, "src/kp_canonicalization/methods/code/__init__.py", 'ID = "code"\nVERSION = 1\n'
    )
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "work")
    return tmp_path


def check(repo: Path, base: str = "dev") -> subprocess.CompletedProcess[str]:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", "change")
    return subprocess.run(
        [sys.executable, str(SCRIPT), base], cwd=repo, capture_output=True, text=True
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
    write(repo, PROFILE, "profile: demo@1\nmethods:\n  formula@2: {}\n")

    result = check(repo)
    assert result.returncode == 1
    assert "demo@1.yaml" in result.stdout


def test_deleting_a_released_profile_fails(repo):
    (repo / PROFILE).unlink()

    assert check(repo).returncode == 1


def test_adding_a_new_profile_passes(repo):
    write(
        repo,
        "src/kp_canonicalization/profiles/demo@2.yaml",
        "profile: demo@2\nmethods:\n  formula@1: {}\n",
    )

    assert check(repo).returncode == 0


def test_the_dev_profile_its_methods_and_the_operating_document_may_change(repo):
    write(repo, "src/kp_canonicalization/methods/code/extra.py", "X = 1\n")
    write(repo, DEV_PROFILE, "profile: demo@1\nmethods:\n  code@2: {}\n")
    write(repo, "src/kp_canonicalization/profiles/README.md", "How to release and retire.\n")

    assert check(repo).returncode == 0


def test_a_patch_to_a_release_branch_may_not_touch_a_method_even_with_a_version_bump(repo):
    git(repo, "branch", "release/demo-1", "dev")
    write(repo, FORMULA + "prompt.txt", "Transcribe as LaTeX.\n")
    write(repo, FORMULA + "__init__.py", 'ID = "formula"\nVERSION = 2\n')

    assert check(repo).returncode == 0  # control: the same diff passes against dev
    result = check(repo, "release/demo-1")
    assert result.returncode == 1
    assert FORMULA + "prompt.txt: a release branch takes no method change" in result.stdout


def test_a_patch_to_a_release_branch_may_change_shared_code(repo):
    git(repo, "branch", "release/demo-1", "dev")
    write(repo, "src/kp_canonicalization/worker.py", "LOG = True\n")

    assert check(repo, "release/demo-1").returncode == 0


def test_released_lists_the_ids_of_the_profiles_released_at_a_revision(repo):
    listed = subprocess.run(
        [sys.executable, str(SCRIPT), "--released", "dev"], cwd=repo, capture_output=True, text=True
    )

    assert (listed.returncode, listed.stdout.split()) == (0, ["demo@1"])
