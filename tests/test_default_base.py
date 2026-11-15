import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/default-base"


@pytest.mark.parametrize(
    "branch, base",
    [
        ("impl/135-reuse-versioning", "origin/dev\n"),
        ("patch/paper-pdf-12-190-log-fix", "origin/release/paper-pdf-12\n"),
        ("impl/190-patch/paper-pdf-1-notes", "origin/dev\n"),
    ],
)
def test_only_a_patch_branch_is_based_on_its_release_branch(tmp_path, branch, base):
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", branch)
    git("-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-q",
        "--allow-empty", "-m", "first")  # fmt: skip

    done = subprocess.run([SCRIPT], cwd=tmp_path, check=True, capture_output=True, text=True)
    assert done.stdout == base
