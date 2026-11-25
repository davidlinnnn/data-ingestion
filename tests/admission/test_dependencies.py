"""The admission image leaves out the parsing dependencies (#78 C20, #113, #207); the consumer SDK
and the reference projection load nothing of the platform's packages either (#127)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PARSING = {"docling", "torch", "torchvision", "rapidocr", "onnxruntime", "pypdfium2"}
PLATFORM = {"kp_admission", "kp_canonicalization"}


def loaded(module: str, packages: set[str] = PARSING) -> set[str]:
    """Which of `packages` a fresh interpreter has loaded after importing `module`."""
    code = f"import sys, {module}; print(*{{name.split('.')[0] for name in sys.modules}})"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return set(out.stdout.split()) & packages


@pytest.mark.parametrize("module", ["kp_admission.cli", "kp_admission.api", "kp_sdk"])
def test_the_admission_roles_load_no_parsing_dependency(module):
    assert loaded(module) == set()


@pytest.mark.parametrize("module", ["kp_sdk.projection", "kp_reference_projection.cli"])
def test_the_consumer_sdk_and_the_reference_projection_load_nothing_of_the_platform(module):
    assert loaded(module, PARSING | PLATFORM) == set()


def installed(python: str) -> set[str]:
    """Which of PARSING the interpreter `python` can import."""
    code = f"import importlib.util as u; print(*[m for m in {sorted(PARSING)} if u.find_spec(m)])"
    out = subprocess.run([python, "-c", code], capture_output=True, text=True, check=True)
    return set(out.stdout.split())


def test_kp_admission_starts_in_an_environment_of_the_admission_dependencies_alone(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["UV_PROJECT_ENVIRONMENT"] = str(tmp_path / "venv")
    uv = shutil.which("uv")
    assert uv, "uv builds the environment from the lockfile"
    repo = Path(__file__).resolve().parents[2]
    subprocess.run(
        [uv, "sync", "--frozen", "--no-default-groups"], cwd=repo, env=env, check=True,
        capture_output=True,
    )  # fmt: skip

    started = subprocess.run(
        [tmp_path / "venv/bin/kp-admission", "--help"], capture_output=True, text=True
    )

    assert started.returncode == 0, started.stderr
    assert "dispatcher" in started.stdout
    assert installed(str(tmp_path / "venv/bin/python")) == set()


def test_control_the_full_environment_has_the_parsing_dependencies():
    assert installed(sys.executable) == PARSING


def test_control_a_parsing_module_is_seen():
    assert loaded("pypdfium2") == {"pypdfium2"}


def test_control_a_platform_module_is_seen():
    assert loaded("kp_admission.feed", PLATFORM) == {"kp_admission"}
