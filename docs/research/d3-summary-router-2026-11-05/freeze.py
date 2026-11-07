"""Write freeze.json: the SHA-256 of every input, question and program the #166 runs depend on.

    .venv/bin/python docs/research/d3-summary-router-2026-11-05/freeze.py FROZEN OUT

run_d3.py refuses to start when any hash differs. Written before any d3 output exists.
"""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCAL = ["questions.json", "build_inputs.py", "run_d3.py", "router.py", "score.py",
         "test_router.py", "weights-d3-flash.json", "inputs-counts.json"]  # fmt: skip


def main(frozen: Path, out: Path) -> None:
    assert not (out / "runs").exists(), "d3 outputs exist; the freeze must come first"
    files = {name: HERE / name for name in LOCAL}
    files |= {str(frozen / f"accuracy-{s}.json"): frozen / f"accuracy-{s}.json"
              for s in ("dev", "held-out")}  # fmt: skip
    files |= {str(out / f"{n}.json"): out / f"{n}.json" for n in ("items", "units", "cases", "steps")}
    digests = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in files.items()}
    home = str(Path.home())
    (HERE / "freeze.json").write_text(json.dumps({
        "frozen": datetime.now(UTC).isoformat(timespec="seconds"), "d3_outputs_seen": 0,
        "files": {k.replace(home, "~", 1): v for k, v in digests.items()},
    }, indent=1) + "\n")  # fmt: skip


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]).expanduser())
