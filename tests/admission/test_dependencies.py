"""The admission image leaves out the parsing dependencies (#78 C20, #113)."""

import subprocess
import sys

import pytest

PARSING = {"docling", "torch", "torchvision", "rapidocr", "onnxruntime", "pypdfium2"}


def loaded(module: str) -> set[str]:
    """The parsing packages a fresh interpreter has loaded after importing `module`."""
    code = f"import sys, {module}; print(*{{name.split('.')[0] for name in sys.modules}})"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return set(out.stdout.split()) & PARSING


@pytest.mark.parametrize("module", ["kp_admission.cli", "kp_admission.api"])
def test_the_admission_roles_load_no_parsing_dependency(module):
    assert loaded(module) == set()


def test_control_a_parsing_module_is_seen():
    assert loaded("pypdfium2") == {"pypdfium2"}
