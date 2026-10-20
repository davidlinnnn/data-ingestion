"""Compare saved evidence and run offline regressions; never reseal or infer."""
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def compare_hashes(base, records):
    for name, expected in records.items():
        path = Path(base) / name
        if sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("saved evidence changed: " + str(path))
    return len(records)


def run(arguments):
    result = subprocess.run([sys.executable, "-B", *arguments], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("offline check failed: " + " ".join(arguments) + "\n" + result.stdout + result.stderr)
    return result.stdout + result.stderr


def main():
    old = HERE.parent / "pdf-core-stage1-2026-10-17"
    history = json.loads((old / "artifact-hashes.json").read_text())
    historical = compare_hashes(old, {record["path"]: record["sha256"] for record in history})
    live = json.loads((HERE / "B/live-artifact-hashes.json").read_text())
    live_count = compare_hashes(HERE / "B", {record["path"]: record["sha256"] for record in live})
    grader = json.loads((HERE / "B/rescore-v2/verification.json").read_text())
    compare_hashes(ROOT, grader["inputs"])
    compare_hashes(HERE / "B/rescore-v2", grader["outputs"])
    audit = json.loads((HERE / "contract-audit-verification.json").read_text())
    compare_hashes(ROOT, audit["inputs"])
    compare_hashes(HERE, audit["outputs"])
    current = json.loads((HERE / "ABC-followup-verification.json").read_text())
    compare_hashes(ROOT, current["files"])
    run([str(HERE / "B/runner.py"), "--verify"])
    run([str(HERE / "C/controls.py"), "--check"])
    tests = {}
    for folder, pattern in (("A", "test_*.py"), ("B", "test_*.py"), ("B-padding", "test_*.py"),
                            ("C", "test_*.py"), (".", "test_cross_component.py")):
        if not list((HERE / folder).glob(pattern)):
            raise ValueError("missing regression entry: " + folder)
        log = run(["-m", "unittest", "discover", "-s", str(HERE / folder), "-p", pattern])
        count = re.search(r"Ran (\d+) tests?\b", log)
        if count is None or int(count[1]) == 0:
            raise ValueError("empty regression suite: " + folder)
        tests[folder] = int(count[1])
    print(json.dumps(dict(status="offline_evidence_and_regressions_passed", tests=tests,
        total_tests=sum(tests.values()), historical_artifacts_unchanged=historical,
        live_artifacts_unchanged=live_count, new_model_calls=0,
        quality_acceptance="Use the branch source reviews; checks and hashes do not establish model accuracy.")))


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit("No options: this command only compares saved evidence and runs offline tests.")
    main()
