"""Read-only entry point: current controls, artifact identity and old-input seals."""
from hashlib import sha256
import json
from pathlib import Path
import unittest
import test_gates

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    seal=json.loads((HERE/"artifact-seal-v2.json").read_text())
    for name,expected in seal.items():
        assert sha256((HERE/name).read_bytes()).hexdigest()==expected,name
    inputs=json.loads((HERE/"input-verification.json").read_text())["files"]
    for name,expected in inputs.items():
        if not name.startswith(str(HERE.relative_to(ROOT))+"/"):
            assert sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    suite=unittest.defaultTestLoader.loadTestsFromModule(test_gates)
    assert suite.countTestCases()>0
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    print("Current offline controls and historical-input seals: PASS")


if __name__=="__main__":main()
