"""The admission image leaves out the parsing dependencies (#78 C20, #113); the consumer SDK and
the reference projection load nothing of the platform's packages either (#127)."""

import subprocess
import sys

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


def test_control_a_parsing_module_is_seen():
    assert loaded("pypdfium2") == {"pypdfium2"}


def test_control_a_platform_module_is_seen():
    assert loaded("kp_admission.feed", PLATFORM) == {"kp_admission"}
