"""Run the exact reviewed v3 warm oracle under the distinct #44 CY identity."""

import importlib.util
import json
from pathlib import Path
import sys

from candidate.warm_v3_reference_cy import reviewed_reference_checker


spec = importlib.util.spec_from_file_location(
    "t09a_warm_cy_engine", Path(__file__).with_name("warm_pod_window_r.py")
)
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
base.reviewed_reference_checker = reviewed_reference_checker
base.SEQUENCE = ("06",)
def validate_scope(args):
    manifest = json.loads(args.integration_manifest.read_text())
    expected = {"sequence": ["06"], "group_requests": 7, "max_requests": 20,
                "expected_parser_generations": 1, "automatic_retry": False,
                "measurement": "first component OCR allocation; deliberate stop after output"}
    base.require(manifest["authorization_scope"] == expected, "CY diagnostic scope changed")
    base.require(base.sha(base.canonical(expected).encode()) == args.authorization_scope_sha256
                 == manifest["authorization_scope_sha256"], "CY scope identity changed")
    base.require(manifest["identity"] == {"phase":args.name,"run_id":args.expected_run_id,
                 "prefix":args.expected_prefix}, "CY runtime identity changed")
    return manifest

base.validate_scope = validate_scope
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
