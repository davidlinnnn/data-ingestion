"""#153: freeze the inputs before the first d3 output.

    python3 docs/research/d3-quality-check-2026-11-02/freeze.py OUT

Writes OUT/freeze.json (and a copy next to this script) with the SHA-256 of every file the
protocol depends on; run_d3.py refuses to start when a hash differs. Refuses to run once a
result file exists.
"""

import datetime
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_FILES = (
    "freeze.md",
    "judging-rules.md",
    "questions.json",
    "score.py",
    "run_d3.py",
    "prepare_inputs.py",
    "build_split.py",
    "merge_verdicts.py",
    "weights-d3-nano.json",
    "weights-d3-mini.json",
)
OUT_FILES = (
    "items.jsonl",
    "judging/merged.jsonl",
    "judging/overrides.json",
    "labels.jsonl",
    "split.json",
    "model-inputs.json",
    "test-counts.json",
)


def main(out: Path) -> int:
    results = list((out / "runs").rglob("*.result.json")) if (out / "runs").exists() else []
    assert all(p.parts[-3].startswith("control-") for p in results), (
        "d3 outputs exist"
    )  # the W4b control is not an output
    files = {str(HERE / f): hashlib.sha256((HERE / f).read_bytes()).hexdigest() for f in REPO_FILES}
    files |= {f: hashlib.sha256((out / f).read_bytes()).hexdigest() for f in OUT_FILES}
    data = {
        "frozen_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "d3_outputs_seen": 0,
        "files": files,
    }
    text = json.dumps(data, indent=1) + "\n"
    (out / "freeze.json").write_text(text)
    (HERE / "freeze.json").write_text(
        text.replace(str(HERE) + "/", "repo:").replace(str(out) + "/", "out:")
    )
    print(len(files), "files frozen at", data["frozen_at"])
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
