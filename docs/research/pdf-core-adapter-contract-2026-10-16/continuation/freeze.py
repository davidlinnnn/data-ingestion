"""Freeze continuation controls before executing the unchanged policy."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def identity(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def e(cid, page, text, box, label="text", size=(600, 800)):
    return {"cid": cid, "ref": f"#/{cid}", "page_no": page, "text": text,
            "label": label, "box_top_left": list(box), "page_size": list(size)}


cases = []


def case(name, elements, expected, rationale, origin="existing_test_equivalent"):
    cases.append({"id": name, "required": True, "origin": origin,
                  "input_order": elements, "expected": expected, "rationale": rationale})


owner = e(0, 1, "unfinished prose", (100, 700, 500, 750))
next_body = e(1, 2, "Continuation.", (100, 60, 500, 100))
case("margin_before_body", [e(0, 1, "We travel toward", (100, 700, 500, 750)),
     e(1, 2, "SIDE NOTE", (20, 400, 70, 430)), e(2, 2, "North Harbor.", (100, 60, 500, 100))],
     {"0": [2]}, "Margin-sized note must not displace the true continuation.")
case("cross_column_uppercase", [e(0, 1, "A route toward", (30, 700, 270, 750)),
     e(1, 1, "East Harbor.", (320, 60, 560, 100))], {"0": [1]}, "Uppercase words can continue a paragraph.")
case("container_barrier", [owner, e(1, 2, "", (110, 60, 420, 100), "key_value_region"),
     e(2, 2, "Figure 8.1 Sample", (120, 140, 490, 190))], {}, "First container entrance is a barrier.")
case("cross_page_chain", [e(0, 1, "first fragment", (100, 680, 500, 750)),
     e(1, 2, "second fragment", (100, 60, 500, 750)),
     e(2, 3, "last fragment.", (100, 60, 500, 100))], {"0": [1, 2]}, "Preserve an ordered multi-page chain.")
for name, target in [
    ("margin_target", e(1, 2, "SIDE", (20, 60, 70, 100))),
    ("skipped_page", e(1, 3, "next text", (100, 60, 500, 100))),
    ("interior_target", e(1, 2, "mid page", (100, 350, 500, 400))),
    ("heading_target", e(1, 2, "Heading", (100, 60, 500, 100), "section_header")),
]:
    case(name, [owner, target], {}, "Reject the non-continuation target.")
case("finished_sentence", [e(0, 1, "Finished.", (100, 700, 500, 750)), next_body], {}, "Sentence-complete source does not merge.")
case("interior_source", [e(0, 1, "unfinished", (100, 200, 500, 300)), next_body], {}, "Interior source is not a page boundary.")
case("ambiguous_targets", [owner, e(1, 2, "First", (100, 60, 500, 100)),
     e(2, 2, "Second", (100, 60, 500, 100))], {}, "Same entrance rank is ambiguous.")
case("duplicate_ownership", [e(0, 1, "first unfinished", (100, 690, 500, 750)),
     e(1, 1, "second unfinished", (100, 700, 500, 750)), e(2, 2, "Continuation.", (100, 60, 500, 100))], {}, "Ambiguous ownership must produce no edge.")
case("inline_chain", [e(0, 1, "for each", (100, 200, 140, 210)),
     e(1, 1, "action", (145, 200, 180, 210)), e(2, 1, "in", (185, 200, 200, 210))],
     {"0": [1, 2]}, "Retain genuine same-line fragments from upstream.")
case("overlapping_entrances", [owner, e(1, 2, "First.", (100, 60, 500, 100)),
     e(2, 2, "Second.", (101, 61, 499, 101))], {}, "Overlapping candidates cannot establish a unique entrance.")
for label in ("text", "key_value_region"):
    for target_page, target_box in ((2, (100, 60, 500, 100)), (1, (320, 60, 560, 100))):
        box = (100, 650, 500, 700) if target_page == 2 else (30, 650, 270, 700)
        barrier = (box[0], 710, box[2], 760)
        case(f"exit_barrier_{label}_{target_page}", [e(0, 1, "unfinished prose", box),
             e(1, 1, "Following content.", barrier, label), e(2, target_page, "Continuation.", target_box)],
             {}, "Following body content blocks a page/column exit.")
for label in ("caption", "section_header"):
    case(f"explicit_{label}_barrier", [owner, e(1, 2, "Figure 1" if label == "caption" else "Results", (100, 60, 500, 100), label),
         e(2, 2, "A new paragraph.", (100, 130, 500, 180))], {}, "Typed caption/heading cannot be swallowed or bypassed.", "new_authored_control")
case("ordinary_next_paragraph", [e(0, 1, "The first experiment is complete.", (100, 700, 500, 750)),
     e(1, 2, "A separate experiment starts here.", (100, 60, 500, 100))], {}, "Different authored paragraphs must remain separate.", "new_authored_control")
case("ordinary_unpunctuated_next_paragraph", [e(0, 1, "Method A uses a fixed schedule", (100, 700, 500, 750)),
     e(1, 2, "Results improve on the held-out set.", (100, 60, 500, 100))], {},
     "Authored truth declares two complete independent paragraphs; punctuation absence alone does not authorize merging.", "new_authored_control")

snapshot_path = ROOT / "docs/research/pdf-core-g2-inline-boundary-2026-10-15/review/source-snapshot.json"
snapshot = json.loads(snapshot_path.read_text())
native = next(v["object"] for v in snapshot["relevant_native_objects"] if v["source"] == "seal" and v["ref"] == "#/texts/34")
fragments = []
for cid, prov in enumerate(native["prov"]):
    box = prov["bbox"]
    start, end = prov["charspan"]
    fragment = e(cid, prov["page_no"], native["text"][start:end],
                 (box["l"], 792 - box["t"], box["r"], 792 - box["b"]), native["label"], (612, 792))
    fragment["native_binding"] = {"item_ref": "#/texts/34", "provenance_index": cid, "charspan": [start, end]}
    fragments.append(fragment)
assert len(fragments) == 2 and fragments[1]["text"].startswith("Algorithm 1")
case("retained_tall_body_right_title_text_label", fragments, {},
     "Previously reviewed native body and algorithm-title fragments are distinct; actual native labels both remain text. Splitting only reconstructs the two explicit provenance fragments for policy input, not a production mapper.",
     "preserved_native_geometry_text_fragments")
typed_fragments = json.loads(json.dumps(fragments))
typed_fragments[1]["label"] = "section_header"
case("tall_body_title_typed_counterfactual", typed_fragments, {},
     "Counterfactual control only: a correctly typed heading is a barrier. Cannot replace or count as fixing the actual text-labelled title case.", "counterfactual_role_control")

predictor = ROOT / "docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling_ibm_models/reading_order/reading_order_rb.py"
source_paths = [ROOT / "src/pdf_processing/continuation.py", predictor,
                ROOT / "tests/pdf_processing/q01/test_continuation.py", ROOT / "tests/pdf_processing/q01/replay.py",
                ROOT / "docs/research/pdf-core-g2-inline-boundary-2026-10-15.md", snapshot_path, Path(__file__), OUT / "run.py"]
manifest = {
    "format": "adapter-continuation-controls-v1", "frozen_before_policy_execution": True,
    "scope": "Pure rule-based continuation only; no model load, inference, network, PDF/image/holdout reads, package install or environment creation.",
    "runtime": {"executable": sys.executable, "packages": {name: importlib.metadata.version(name) for name in ("docling", "docling-core", "docling-ibm-models")}},
    "source_identities": [identity(path) for path in source_paths],
    "constructor_review": "Package __init__ files are empty; ReadingOrderPredictor imports geometry/dataclasses/regex/rtree and constructor sets two rule parameters only; no weights or learned model call.",
    "fixture_input_coordinates": "TOPLEFT points; runner converts mathematically to BOTTOMLEFT before calling unchanged policy.",
    "stop_threshold": "Any required expected-merge mismatch, input mutation, invalid output ownership/cycle, source/runtime identity mismatch is material failure. Do not tune rules or implement mapper after failure.",
    "case_truth_policy": "Expected relations authored/frozen before policy execution; native title separation uses prior reviewed evidence. Counterfactual typed title cannot cancel actual native-label failure.",
    "invariants": ["input element model dumps unchanged", "output IDs exist in input", "no self-edge or chain cycle", "each target belongs to at most one output chain", "source and frozen fixture hashes unchanged"],
    "existing_replay_availability": {"path": "/private/tmp/t09a-r2-20260914/checkpoints", "exists": Path("/private/tmp/t09a-r2-20260914/checkpoints").is_dir(), "consequence_if_absent": "Two existing tests requiring replay.load() are explicitly unexecuted; never fabricate missing checkpoints."},
    "cases": cases,
}
OUT.mkdir(parents=True, exist_ok=True)
path = OUT / "controls.json"
assert not path.exists(), "Do not replace frozen controls"
path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
digest = hashlib.sha256(path.read_bytes()).hexdigest()
(OUT / "controls.sha256").write_text(digest + "\n")
print(json.dumps({"controls": len(cases), "sha256": digest, "policy_executed": False}))
