"""Retain the reviewed v3 oracle while binding the post-BH failure-only patch."""

import copy
import json
from pathlib import Path

from consumer import canonical, require, sha
from candidate import warm_v3_reference as base


Q04 = Path(__file__).resolve().parent.parent
BI = Q04.parent / "t09a_bounds/BI-MANIFEST.json"
AH = Q04 / "candidate/warm-continuation-v3-ah/MANIFEST.json"


def verify_v3_bundle(bundle: Path):
    reviewed = json.loads(base.ORACLE.read_text())
    current, old = json.loads(BI.read_text()), json.loads(AH.read_text())
    raw = (bundle / "inputs.json").read_bytes()
    inputs = json.loads(raw)
    require(reviewed["status"] == "REVIEWED_EXACT_V3", "v3 oracle status changed")
    require(sha(raw) == current["candidate_inputs_sha256"]
            and sha(base.ORACLE.read_bytes()) == current["exact_oracle_sha256"],
            "BI bundle or reviewed oracle changed")
    require(inputs["base_profile"]["method"]["continuation"] == reviewed["continuation"]
            and inputs["producer"]["continuation.py"] == reviewed["continuation_source_sha256"],
            "v3 parser method changed")
    normalized = copy.deepcopy(inputs)
    normalized["producer"]["warm_child.py"] = old["producer"]["warm_child.py"]
    name = "tests/pdf_processing/q04/test_warm_continuity.py"
    normalized["test_files"][name] = old["test_files"][name]
    normalized["producer"]["continuation.py"] = current["source_continuation"]["sha256"]
    normalized["base_profile"]["method"]["continuation"] = current["source_continuation"]
    require(sha(canonical(normalized).encode()) == current["source_candidate_canonical_sha256"],
            "BI bundle differs beyond reviewed warm-child/test and v3 continuation")
    return reviewed, inputs


base.verify_v3_bundle = verify_v3_bundle
reviewed_reference_checker = base.reviewed_reference_checker
