"""Fail-closed graph checks for the v3 continuation warm candidate."""

import copy
import importlib.util
import json
from pathlib import Path

from consumer import canonical, graph_projection, require, sha
import q04_runtime


Q04 = Path(__file__).resolve().parent.parent
ORACLE = Q04 / "diagnosis/continuation-v3/EXACT-ORACLE.json"
DERIVATION = Q04 / "candidate/warm-continuation-v3-ah/MANIFEST.json"


def verify_v3_bundle(bundle: Path):
    manifest = json.loads(ORACLE.read_text())
    derivation = json.loads(DERIVATION.read_text())
    raw = (bundle / "inputs.json").read_bytes()
    inputs = json.loads(raw)
    require(manifest["status"] == "REVIEWED_EXACT_V3", "v3 oracle status changed")
    require(sha(raw) == derivation["candidate_inputs_sha256"]
            and sha(ORACLE.read_bytes()) == derivation["exact_oracle_sha256"],
            "v3 bundle or oracle bytes changed")
    require(
        inputs["base_profile"]["method"]["continuation"] == manifest["continuation"]
        and inputs["producer"]["continuation.py"] == manifest["continuation_source_sha256"],
        "v3 producer or method changed",
    )
    normalized = copy.deepcopy(inputs)
    normalized["producer"]["continuation.py"] = derivation["source_continuation"]["sha256"]
    normalized["base_profile"]["method"]["continuation"] = derivation["source_continuation"]
    require(sha(canonical(normalized).encode()) == derivation["source_candidate_canonical_sha256"],
            "v3 bundle differs beyond the continuation method")
    return manifest, inputs


def reviewed_reference_checker(bundle: Path, original):
    manifest, inputs = verify_v3_bundle(bundle)
    references = {
        sid: json.loads((bundle / "references" / f"{sid}.json").read_text())
        for sid in manifest["local_v3_graph_sha256"]
    }
    require(set(references) == {"native", "06", "07", "08", "09", "10"},
            "v3 fixture oracle set changed")
    spec = importlib.util.spec_from_file_location(
        "q04_v3_exact_oracle", Q04 / "diagnosis/continuation-v2/exact_oracle.py"
    )
    exact = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exact)

    def check(document, reference, out):
        matches = [sid for sid, value in references.items() if value == reference]
        require(len(matches) == 1, "v3 reference is unknown or ambiguous")
        sid = matches[0]
        graph_sha = sha(canonical(graph_projection(document)).encode())
        require(graph_sha == manifest["local_v3_graph_sha256"][sid],
                f"{sid} graph differs from reviewed v3 output")
        if sid in ("native", "06"):
            return exact.check(
                sid, document,
                (bundle / "originals" / f"{sid}.pdf").read_bytes(),
                (bundle / "references" / f"{sid}.json").read_bytes(),
                inputs["base_profile"]["method"], manifest,
            )
        if sid == "08":
            from candidate.aima_image_supplement import compare
            report = compare(document, reference, bundle / "fixtures/08.pdf")
            q04_runtime.write(out / "source-image-supplement.json", report)
            require(report["actual_graph_sha256"] == graph_sha,
                    "AIMA image supplement graph changed")
        elif sid in ("09", "10"):
            require(original(document, reference, out) == graph_sha,
                    "historical exact reference changed")
        else:
            q04_runtime.write(out / "source-reviewed-equivalence-v3.json", {
                "status": "PASS_EXACT_REVIEWED_GRAPH",
                "fixture": sid,
                "graph_sha256": graph_sha,
                "continuation": manifest["continuation"],
            })
        return graph_sha

    return check
