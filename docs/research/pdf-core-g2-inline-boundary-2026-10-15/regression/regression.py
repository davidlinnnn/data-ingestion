"""Shadow only: frozen native-token guard against existing saved paragraph outputs."""

from collections import Counter
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[3]
PRIOR = REPO / "docs/research/pdf-core-g2-inline-api-2026-10-15"
GUARD = ROOT / "reinsertion/apply.py"
GUARD_SHA256 = "5bca03c6ec5e30d324f92b9678733ba09152d1a9b93f2e2e8317fc62860064ef"
DECISION = "do_not_promote_as_global_rejection_gate"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def pointer(data, path):
    for part in path.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def load_guard():
    assert sha(GUARD) == GUARD_SHA256, "Frozen guard changed; no tuning in this regression"
    spec = importlib.util.spec_from_file_location("frozen_shadow_conservation", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.conservation  # No producer/adapter main, parser or application calls.


def probe(conservation, native, block):
    original = copy.deepcopy(block)
    try:
        evidence = conservation(native, block)
    except ValueError as error:
        result = {"decision": "abstain", "reason": str(error)}
    else:
        result = {"decision": "pass", "evidence": evidence}
    assert block == original, "Guard mutated the frozen model block"
    return result


def selfchecks(conservation):
    block = lambda text, kind="text": {"segments": [{"kind": kind, "text": text}]}
    checks = {
        "identical_repeated_tokens_pass": probe(conservation, "token token", block("token token"))["decision"] == "pass",
        "lost_repeated_token_abstains": probe(conservation, "token token", block("token"))["decision"] == "abstain",
        "latex_command_arguments_retained": probe(conservation, "AB", block(r"\mathrm{AB}_{\theta'}", "math"))["decision"] == "pass",
        "split_multiletter_identifier_abstains": probe(conservation, "AB", block("A_{B_x}", "math"))["decision"] == "abstain",
        "greek_identity_change_is_unchecked": probe(conservation, "θ τ", block(r"\alpha \beta", "math"))["decision"] == "pass",
        "single_letter_operator_change_is_unchecked": probe(conservation, "x <= y", block("x > y", "math"))["decision"] == "pass",
    }
    assert all(checks.values())
    return {"passed": True, "checks": checks, "scope": "In-memory behavior/limitation checks; passing a guard is not source-quality approval"}


def verify_frozen():
    verified = {}
    def checked(reference):
        path = REPO / reference["path"]
        assert sha(path) == reference["sha256"], str(path)
        verified[str(path.relative_to(REPO))] = reference["sha256"]
        return path
    manifest = read(ROOT / "inputs/input-manifest.json")
    prior_count = 0
    for reference in manifest["prior_payload_manifests"]:
        snapshot = read(checked(reference))
        assert len(snapshot["files"]) == reference["payload_count"]
        for reference in snapshot["files"]:
            checked(reference)
            prior_count += 1
    assert prior_count == 846
    for folder in (ROOT / "inputs", ROOT / "parsed", ROOT / "reinsertion"):
        path = folder / "artifact-sha256.json"
        for name, expected in read(path).items():
            checked({"path": str((folder / name).relative_to(REPO)), "sha256": expected})
        verified[str(path.relative_to(REPO))] = sha(path)
    api_verification_path = ROOT / "api/verification.json"
    api = read(checked({"path": str(api_verification_path.relative_to(REPO)),
        "sha256": "07a0530469eacae41208b36c6e80fcdad0d1bf4f9c9739a58f241b7bfdb5e821"}))
    assert api["all_selected_completed_contract_valid"] and len(api["jobs"]) == 6
    for row in api["jobs"]:
        folder = ROOT / "api" / row["id"]
        response_path = checked({"path": str((folder / "response.json").relative_to(REPO)), "sha256": row["response_sha256"]})
        response = read(response_path)
        assert json.loads(response["choices"][0]["message"]["content"]) == read(folder / "output.json")
        for name in ("output.json", "request-description.json", "input.png"):
            verified[str((folder / name).relative_to(REPO))] = sha(folder / name)
    for reference in read(ROOT / "source-audit.json")["source_files"]:
        checked(reference)
    verified[str((ROOT / "source-audit.json").relative_to(REPO))] = sha(ROOT / "source-audit.json")
    return manifest, verified, prior_count


def main():
    manifest, verified, prior_count = verify_frozen()
    conservation = load_guard()
    checks = selfchecks(conservation)
    old_manifest = read(PRIOR / "inputs/input-manifest.json")
    review = read(PRIOR / "review/output-review.json")
    reviewed_runs = {row["id"]: row for row in review["runs"]}
    old_outcomes = {row["api_input_id"]: row for row in read(PRIOR / "reinsertion/summary.json")["outcomes"]}
    rows = []
    for selected in [row for row in old_manifest["inputs"] if row["phase"] == "paragraph"]:
        reference = selected["prior_candidate_ref"]
        candidate = pointer(read(REPO / reference["path"]), reference["json_pointer"])
        native = candidate["provider_text"]
        assert hashlib.sha256(native.encode()).hexdigest() == selected["provider_text_sha256"]
        output_path = PRIOR / "api" / selected["id"] / "output.json"
        assert sha(output_path) == reviewed_runs[selected["id"]]["parsed_output_sha256"]
        data = read(output_path)
        assert data["blocks"]
        per_block = [probe(conservation, native, block) for block in data["blocks"]]
        rows.append({"id": selected["id"], "provider_ref": selected["provider_item_ref"],
            "source_id": selected["source"]["id"], "output_ref": {"path": str(output_path.relative_to(REPO)), "sha256": sha(output_path)},
            "native_text_sha256": selected["provider_text_sha256"], "source_fragments": selected["source_fragment_count"],
            "raw_block_count": len(data["blocks"]), "single_target_block_eligible": len(data["blocks"]) == 1,
            "prior_adapter_status": old_outcomes[selected["id"]]["status"],
            "first_block_shadow": per_block[0], "all_raw_block_probes_against_complete_native_item": per_block,
            "quality_approval_from_guard": False})
    assert len(rows) == 17
    by_id = {row["id"]: row for row in rows}
    anchors = [
        ("E14", "paragraph--wikiskill-texts-363", "/frozen_case_semantics/G1-E14/paragraph/bounded_F13_delivery_pass", "F13 math/prose pass"),
        ("E13", "paragraph--seal-texts-30", "/frozen_case_semantics/G1-E13/paragraph/bounded_F13_delivery_pass", "F13 cross-page paragraph pass"),
        ("E04", "paragraph--dgm-texts-648", "/frozen_case_semantics/G1-E04/paragraph/F14_code_tokens_bindings_numbers_pass", "F14 selected token/binding/number pass; hyphenation difference remains visible"),
        ("WikiSkill362", "paragraph--wikiskill-texts-362", "/frozen_case_semantics/wikiskill_362_omission_regression/paragraph/source_opening_sentence_present", "Opening-sentence omission regression restored"),
    ]
    positives = []
    for label, name, path, meaning in anchors:
        assert pointer(review, path) is True
        positives.append({"anchor": label, "id": name, "existing_source_review_positive": True,
            "review_json_pointer": path, "positive_scope": meaning,
            "guard_decision": by_id[name]["first_block_shadow"]["decision"],
            "guard_reason": by_id[name]["first_block_shadow"].get("reason")})
    new_targets = []
    for name in ("seal-paragraph-formula-context", "seal-prose-continuation"):
        selected = next(row for row in manifest["inputs"] if row["id"] == name)
        native_doc = read(REPO / selected["baseline_document_ref"]["path"])
        def text(reference):
            collection, index = reference[2:].split("/")
            return native_doc[collection][int(index)]["text"]
        references = selected["consumed_item_refs"]
        native = " ".join(text(reference) for reference in references)
        if "retained_spatial_fragment_reuse" in selected:
            first = native_doc["texts"][int(references[0].rsplit("/", 1)[1])]
            native = first["text"][slice(*first["prov"][0]["charspan"])] + " " + text(references[1])
        output_path = ROOT / "api" / name / "output.json"
        output = read(output_path)
        new_targets.append({"id": name, "consumed_refs": references, "context_only_refs_excluded_from_guard": selected["context_only_refs"],
            "retained_foreign_title_excluded_from_guard": "retained_spatial_fragment_reuse" in selected,
            "raw_block_count": len(output["blocks"]), "target_block_index": 0,
            "native_target_text_sha256": hashlib.sha256(native.encode()).hexdigest(),
            "guard": probe(conservation, native, output["blocks"][0]), "quality_approval_from_guard": False})
    rejected_positives = [row for row in positives if row["guard_decision"] == "abstain"]
    # This frozen rule loses approved cases: accidental adoption or hidden omission must fail.
    assert DECISION == "do_not_promote_as_global_rejection_gate"
    assert {row["anchor"] for row in rejected_positives} == {"E14", "E04"}
    assert len(positives) == 4 and all(row["existing_source_review_positive"] for row in positives)
    assert by_id["paragraph--seal-texts-32"]["first_block_shadow"]["decision"] == "abstain"
    assert all(row["guard"]["decision"] == "abstain" for row in new_targets)
    single = [row for row in rows if row["single_target_block_eligible"]]
    previously_applied = [row for row in rows if row["prior_adapter_status"] == "structurally_applied_semantic_quality_unverified"]
    counts = lambda values: dict(Counter(row["first_block_shadow"]["decision"] for row in values))
    for name, expected in verified.items():
        assert sha(REPO / name) == expected, "Frozen payload changed during shadow regression: " + name
    save(HERE / "selfchecks.json", checks)
    result = {"format": "g2-inline-boundary-conservation-shadow-regression-v1", "decision": DECISION,
        "global_adoption_allowed": False, "no_guard_regex_or_threshold_changes": True,
        "scope": "17 existing selected paragraph outputs are regression data, not unseen holdout; target-only new32/34 diagnostics; no application, inference/API/key access",
        "quality_vs_eligibility": "Guard pass is lexical eligibility only; independent source review remains separate. E04 positive scope does not assert an exact full transcript.",
        "source_policy_scope": "Six declared crop/context prototype jobs only; no general detector coverage; fresh cross-source holdout missing",
        "guard_ref": {"path": str(GUARD.relative_to(REPO)), "sha256": GUARD_SHA256}, "runner_sha256": sha(Path(__file__)),
        "review_ref": {"path": str((PRIOR / "review/output-review.json").relative_to(REPO)), "sha256": sha(PRIOR / "review/output-review.json")},
        "frozen_hash_checks": {"prior_payload_entries_checked": prior_count, "unique_files_checked_before_and_after": len(verified), "all_passed": True,
            "verified_files": [{"path": name, "sha256": expected} for name, expected in sorted(verified.items())]},
        "prior_17_summary": {"selected": len(rows), "first_block_shadow_decisions": counts(rows),
            "single_target_block_eligible": len(single), "single_target_block_decisions": counts(single),
            "multi_root_ineligible_count": len(rows)-len(single),
            "previously_structurally_applied": len(previously_applied), "previously_applied_guard_decisions": counts(previously_applied)},
        "existing_positive_anchor_summary": {"review_positive_anchors": 4, "guard_passes": 4-len(rejected_positives),
            "false_abstentions": len(rejected_positives), "all_existing_positive_labels_retained": True},
        "positive_anchors": positives, "prior_17": rows, "new_target_only": new_targets,
        "negative_old_seal32": by_id["paragraph--seal-texts-32"]["first_block_shadow"],
        "limitations": ["ASCII multiletter occurrence coverage ignores Greek/single-letter/prime/operator semantics and ordering", "Hyphenation can reject source-positive transcripts", "A pass can retain a source-wrong matrix structure", "One multi-root provider item has no valid whole-item/one-block association; first-block probes are diagnostic only", "No fresh cross-source holdout or document-wide detector coverage"],
        "api_calls": 0, "new_inference": 0, "old_payload_writes": 0}
    save(HERE / "results.json", result)
    print(json.dumps({"decision": DECISION, "summary": result["prior_17_summary"], "positives": result["existing_positive_anchor_summary"],
        "new_targets": [{"id": row["id"], "guard": row["guard"]} for row in new_targets],
        "frozen_files_checked": len(verified), "results_sha256": sha(HERE / "results.json")}))


if __name__ == "__main__":
    main()
