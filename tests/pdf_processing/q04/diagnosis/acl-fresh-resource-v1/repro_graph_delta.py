"""Minimal red repro for the retained ACL page-2 graph rejection."""

import json
from pathlib import Path
import tempfile

from consumer import check_reference


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "evidence/page2-split-repro.json"


def main():
    fixture = json.loads(FIXTURE.read_text())
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        try:
            check_reference(fixture["actual"], fixture["reference"], output)
        except ValueError:
            print((output / "graph-delta.json").read_text())
            raise
    raise AssertionError("retained page-2 split no longer reproduces graph rejection")


if __name__ == "__main__":
    main()
