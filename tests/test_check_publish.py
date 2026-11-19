"""scripts/check-publish both ways: what must be refused before publishing, and code that
must pass. Test strings are assembled at runtime so this file passes the check itself."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/check-publish"
AT = "@"


def check(text: str, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *flags, "-"], input=text + "\n", capture_output=True, text=True
    )


@pytest.mark.parametrize(
    "line",
    [
        "+" + AT + "pytest.fixture",  # a decorator on an added diff line
        "    " + AT + "pytest.mark.parametrize",
        "load paper-pdf" + AT + "1.yaml",  # Processing Profile file names
        "noreply" + AT + "anthropic.com",
        "12345+someone" + AT + "users.noreply.github.com",
        "alice" + AT + "example.com",
        "GET /v1/documents/{document_id}",
    ],
)
def test_code_and_allowed_addresses_pass(line):
    assert check(line, "--no-placeholders").returncode == 0


@pytest.mark.parametrize(
    "line,rule",
    [
        ("alice" + AT + "corp.com.tw", "email"),
        ("+bob.smith" + AT + "gmail.com", "email"),
        ("x" + AT + "163.com", "email"),
        ("see /Us" + "ers/someone/work", "local-path"),
        ("in /priv" + "ate/tmp/x", "local-path"),
        ("key AK" + "IA" + "ABCDEFGHIJKLMNOP", "secret"),
    ],
    # Spelled-out ids would join the text again, and .test_durations stores test ids.
    ids=["email-tw", "email-gmail", "email-163", "path-users", "path-private", "secret-aws"],
)
def test_private_text_is_refused(line, rule):
    result = check(line, "--no-placeholders")

    assert result.returncode == 1
    assert f": {rule}: " in result.stdout


def test_placeholders_are_refused_only_where_checked():
    text = "blocked by {#COPY" + "_TICKET}"

    assert check(text).returncode == 1
    assert check(text, "--no-placeholders").returncode == 0


@pytest.mark.parametrize(
    "line",
    [
        "the plain C is read as `\\mathcal{C}`",  # the argument of a LaTeX command
        "\\frac{N}{K} with x^{T} and a_{N}",  # several arguments, scripts
        "the hook expands ${NAME} and ${S}",  # shell expansions
    ],
)
def test_latex_arguments_and_shell_expansions_are_no_placeholders(line):
    assert check(line).returncode == 0


def test_a_placeholder_beside_a_latex_argument_is_reported_with_its_line():
    line = "`\\mathcal{C}` is fixed by {#COPY" + "_TICKET}"

    result = check("first line\n" + line)

    assert result.returncode == 1
    assert f":2: placeholder: {line}" in result.stdout
