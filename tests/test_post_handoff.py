"""scripts/post-handoff against a stand-in for gh that serves one ticket body and records what
it is asked to write."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/post-handoff"
BODY = "## Index\n\n- [first](url-1): holds.\n\nSuperseded: none.\n\n<details>\n{old}\n</details>\n"
GH = """#!/bin/sh
case "$1 $2" in
  "issue view") cat "$GH_DIR/body" ;;
  "issue edit") cp "$5" "$GH_DIR/edited" ;;
  "issue comment") cp "$5" "$GH_DIR/commented" ;;
esac
"""


@pytest.fixture
def ticket(tmp_path):
    """Run post-handoff with `old` as the ticket's previous body, kept in <details>."""

    def run(old: str, *args: str) -> subprocess.CompletedProcess[str]:
        (tmp_path / "body").write_text(BODY.format(old=old))
        (tmp_path / "gh").write_text(GH)
        (tmp_path / "gh").chmod(0o755)
        env = os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}", "GH_DIR": str(tmp_path)}
        return subprocess.run([str(SCRIPT), *args], env=env, capture_output=True, text=True)

    (tmp_path / "line.md").write_text("- [second](url-2): holds.\n")
    return run, tmp_path


def test_insert_adds_the_lines_after_the_one_line_that_contains_the_anchor(ticket):
    run, tmp_path = ticket

    done = run("an older body", "insert", "204", "(url-1)", str(tmp_path / "line.md"))

    assert done.returncode == 0, done.stderr
    assert (tmp_path / "edited").read_text() == BODY.format(old="an older body").replace(
        "holds.\n", "holds.\n- [second](url-2): holds.\n", 1
    )


@pytest.mark.parametrize("old, anchor", [("- [first](url-1): holds.", "(url-1)"), ("x", "(url-9)")])
def test_insert_refuses_an_anchor_on_several_lines_or_none(ticket, old, anchor):
    run, tmp_path = ticket

    done = run(old, "insert", "204", anchor, str(tmp_path / "line.md"))

    assert done.returncode == 1 and "exactly 1 is needed" in done.stderr
    assert not (tmp_path / "edited").exists()


def test_a_file_that_must_not_be_published_is_not_posted(ticket):
    run, tmp_path = ticket
    (tmp_path / "line.md").write_text("see {" + "TICKET}\n")

    done = run("x", "comment", "204", str(tmp_path / "line.md"))

    assert done.returncode != 0 and not (tmp_path / "commented").exists()


def test_a_comment_that_passes_the_check_is_posted(ticket):
    run, tmp_path = ticket

    done = run("x", "comment", "204", str(tmp_path / "line.md"))

    assert done.returncode == 0, done.stderr
    assert (tmp_path / "commented").read_text() == "- [second](url-2): holds.\n"
