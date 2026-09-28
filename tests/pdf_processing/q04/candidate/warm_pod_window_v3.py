"""Run the retained 29-group warm window with exact v3 graph checks."""

import importlib.util
from pathlib import Path
import sys

from candidate.warm_v3_reference import reviewed_reference_checker


_spec = importlib.util.spec_from_file_location(
    "q04_warm_pod_window_v3_engine", Path(__file__).with_name("warm_pod_window_r.py")
)
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base
_spec.loader.exec_module(base)
base.reviewed_reference_checker = reviewed_reference_checker
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
