"""Run the exact reviewed v3 warm oracle under the distinct #44 CC identity."""

import importlib.util
from pathlib import Path
import sys

from candidate.warm_v3_reference_cc import reviewed_reference_checker


spec = importlib.util.spec_from_file_location(
    "t09a_warm_cc_engine", Path(__file__).with_name("warm_pod_window_r.py")
)
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
base.reviewed_reference_checker = reviewed_reference_checker
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
