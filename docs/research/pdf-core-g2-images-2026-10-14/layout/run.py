"""Reuse the frozen stock CPU baseline for two previously unrun source pages."""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("g2_existing_baseline", REPO / "docs/research/pdf-core-g2-local-cpu-2026-10-14/run.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.HERE = HERE
base.JOBS = [("wikiskill-p4", "SRC01", 4, False), ("controls-p2", "SRC05", 2, False)]
base.__file__ = str(Path(__file__).resolve())
if len(sys.argv) == 3 and sys.argv[1] == "--worker":
    base.worker(next(job for job in base.JOBS if job[0] == sys.argv[2]))
else:
    assert sys.argv[1:] == []
    base.main()
