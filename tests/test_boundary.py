"""The boundary between kp_admission and kp_canonicalization (#207), the two release units that
#208 moves into two repos. These checks exist only while both live in this one."""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COUNTERPART = {"kp_admission": "kp_canonicalization", "kp_canonicalization": "kp_admission"}


def imported(source: str) -> set[str]:
    """The top-level packages that `source` imports anywhere, inside functions included."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return names


def test_neither_package_imports_the_other():
    for package, other in COUNTERPART.items():
        paths = sorted((REPO / "src" / package).rglob("*.py"))
        assert paths, package
        assert [str(p.relative_to(REPO)) for p in paths if other in imported(p.read_text())] == []


def test_control_an_import_inside_a_function_is_seen():
    assert imported("def f():\n    from kp_admission.dispatcher import x\n") == {"kp_admission"}


def used(source: str) -> set[str]:
    """The packages `source` imports or reads a resource of with importlib.resources.files."""
    names = imported(source)
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "files"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            names.add(str(node.args[0].value).split(".")[0])
    return names


def crossing() -> set[str]:
    return {
        str(path.relative_to(REPO))
        for path in sorted((REPO / "tests").rglob("*.py"))
        if set(COUNTERPART) <= used(path.read_text())
    }


def test_both_packages_keep_the_same_contract_example():
    copies = {
        (REPO / "src" / package / "workflow_start.json").read_bytes() for package in COUNTERPART
    }
    assert len(copies) == 1


# The tests that use both packages, and the repo each goes to when #208 splits them.
CROSSING = {
    "tests/admission/test_status.py": "kp-admission",  # posts with the workers' reporter
    "tests/admission/test_adoption_gate.py": "kp-admission",  # the workers' promoter sets builds
    "tests/test_workflow.py": "kp-canonicalization",  # runs the gate's check.pdf
}


def test_the_crossing_tests_are_the_listed_ones():
    assert crossing() == set(CROSSING)


def test_control_a_resource_read_is_seen():
    assert used('files("kp_admission") / "check.pdf"\n') == {"kp_admission"}
