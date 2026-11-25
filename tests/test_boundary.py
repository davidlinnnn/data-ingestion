"""The boundary between kp_admission and kp_canonicalization (#207), the two release units that
#208 moves into two repos. These checks exist only while both live in this one."""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OTHER = {"kp_admission": "kp_canonicalization", "kp_canonicalization": "kp_admission"}


def imported(source: str) -> set[str]:
    """The top-level packages that `source` imports anywhere, inside functions included."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return names


def importers(paths: list[Path], package: str) -> set[str]:
    return {str(path.relative_to(REPO)) for path in paths if package in imported(path.read_text())}


def test_neither_package_imports_the_other():
    for package, other in OTHER.items():
        assert importers(sorted((REPO / "src" / package).rglob("*.py")), other) == set()


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
        if set(OTHER) <= used(path.read_text())
    }


def test_both_packages_keep_the_same_contract_example():
    copies = {(REPO / "src" / package / "workflow_start.json").read_bytes() for package in OTHER}
    assert len(copies) == 1


# The tests that use both packages, and the repo each goes to when #208 splits them.
CROSSING = {
    # Report intake fed by the workers' HttpStatusReporter: after the split, a report posted
    # from admission's own test client.
    "tests/admission/test_status.py": "kp-admission",
    # The gate against deployments the workers' promoter set current: after the split, set by
    # the Temporal SDK calls promote makes.
    "tests/admission/test_adoption_gate.py": "kp-admission",
    # The gate's test file through a real worker: after the split, a copy of check.pdf.
    "tests/test_workflow.py": "kp-canonicalization",
}


def test_the_crossing_tests_are_the_listed_ones():
    assert crossing() == set(CROSSING)


def test_control_a_resource_read_is_seen():
    assert used('files("kp_admission") / "check.pdf"\n') == {"kp_admission"}
