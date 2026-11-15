"""Write freeze.json: the SHA-256 of every input, question and program the #174 runs depend on.

    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/freeze.py OUT

run_d3.py refuses to start when any hash differs. Written before any d3 output exists.
"""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCAL = ["questions.json", "inputs.py", "review.py", "run_d3.py", "router.py", "test_router.py",
         "weights-d3-flash.json", "inputs-dev.json"]  # fmt: skip
V1 = [f"../d3-summary-router-2026-11-05/{n}" for n in ("build_inputs.py", "router.py", "score.py", "blind.py")]
DEV = ["requests", "units", "cases", "steps", "format-subset", "review/key"]


def main(out: Path) -> None:
    assert not (out / "runs").exists(), "d3 outputs exist; the freeze must come first"
    files = {name: HERE / name for name in LOCAL + V1}
    files |= {str(out / "dev" / f"{n}.json"): out / "dev" / f"{n}.json" for n in DEV}
    home = str(Path.home())
    (HERE / "freeze.json").write_text(json.dumps({
        "frozen": datetime.now(UTC).isoformat(timespec="seconds"), "d3_outputs_seen": 0,
        "files": {k.replace(home, "~", 1): hashlib.sha256(p.read_bytes()).hexdigest()
                  for k, p in files.items()},
    }, indent=1) + "\n")  # fmt: skip


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser())
