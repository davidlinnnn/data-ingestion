"""scripts/check-publish-hook as Claude Code runs it: the Bash tool's command arrives as JSON on
stdin, and exit 2 blocks the call. A body file named through a shell variable is checked when the
same command assigns that variable a literal value."""

import json
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).parents[1] / "scripts/check-publish-hook"


def hook(command: str) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run([str(HOOK)], input=payload, capture_output=True, text=True)


@pytest.fixture
def body(tmp_path: Path) -> Path:
    (tmp_path / "body.md").write_text("Results are on the ticket.\n")
    return tmp_path


@pytest.mark.parametrize("use", ["$S/body.md", "${S}/body.md", '"$S/body.md"'])
def test_a_variable_assigned_in_the_same_command_is_expanded(body, use):
    result = hook(f"S={body} && gh issue comment 1 --body-file {use}")

    assert result.returncode == 0, result.stderr


def test_the_expanded_file_is_checked(body):
    (body / "body.md").write_text("blocked by {#COPY" + "_TICKET}\n")

    assert hook(f"S={body} && gh issue comment 1 --body-file $S/body.md").returncode == 2


@pytest.mark.parametrize(
    "command",
    [
        "gh issue comment 1 --body-file $OUT/body.md",  # never assigned here
        "S=$(mktemp -d) && gh issue comment 1 --body-file $S/body.md",  # not a literal
    ],
)
def test_a_variable_without_a_literal_value_is_refused(command):
    result = hook(command)

    assert result.returncode == 2
    assert "literal" in result.stderr
