"""Offline legacy regression using each response's original image/request/scope."""

import base64
from copy import deepcopy
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[2]
OLD = REPO / "docs/research/pdf-core-g2-inline-api-2026-10-15"
FROZEN = REPO / "docs/research/pdf-core-g2-eval-freeze-2026-10-15/regression-manifest.json"
spec = importlib.util.spec_from_file_location("legacy_context_adapter", ROOT / "adapter.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def read(path):
    return json.loads(path.read_text(), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path):
    return {"path": str(path.relative_to(REPO)), "sha256": sha(path)}


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def original_contract(row, raw):
    folder = OLD / "api" / row["id"]
    request = read(folder / "request-description.json")
    image = folder / "input.png"
    if sha(image) != row["image_sha256"] or sha(REPO / row["image_path"]) != sha(image):
        raise ValueError("original image bytes no longer match frozen manifest")
    if request["input_sha256"] != sha(image) or request["source_input"] != row["image_path"] or request["case"] != row["id"]:
        raise ValueError("original request/image/input identities differ")
    body = deepcopy(request["body_without_inline_image"])
    body["messages"][1]["content"][1]["image_url"]["url"] = "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode()
    if hashlib.sha256(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest() != request["http_body_sha256"]:
        raise ValueError("reconstructed original HTTP request hash differs")
    scope = adapter.bind_scope(raw, [row["provider_item_ref"]], [])
    target = scope["targets"][0]
    if row["replacement_charspan"] != target["replacement_charspan"]:
        raise ValueError("original target span differs from whole bound native item")
    native = adapter.item(raw, row["provider_item_ref"])
    if hashlib.sha256(native["text"].encode()).hexdigest() != row["provider_text_sha256"]:
        raise ValueError("original native target text hash differs")
    contract = adapter.bind_input(scope, image_sha256=sha(image), image_pixels_wh=row["image_pixels_wh"],
                                 request_sha256=sha(folder / "request-description.json"), manifest_row_sha256=adapter.digest(row))
    response, output = read(folder / "response.json"), read(folder / "output.json")
    choices = response["choices"]
    if len(choices) != 1 or choices[0]["finish_reason"] != "stop" or choices[0]["message"].get("refusal"):
        raise ValueError("original response is incomplete or refused")
    if json.loads(choices[0]["message"]["content"]) != output:
        raise ValueError("saved output differs from original response message")
    record = adapter.bind_response(contract, output, response_sha256=sha(folder / "response.json"))
    return scope, contract, record, {"frozen_manifest": ref(OLD / "inputs/input-manifest.json"),
            "original_input_row": row, "input_image": ref(image),
            "request_description": ref(folder / "request-description.json"),
            "http_body_sha256": request["http_body_sha256"],
            "response": ref(folder / "response.json"), "output": ref(folder / "output.json")}


def selfcheck(raw):
    scope = adapter.bind_scope(raw, ["#/texts/4"], ["#/texts/12"])
    contract = adapter.bind_input(scope, image_sha256="1" * 64, image_pixels_wh=[100, 100],
                                 request_sha256="2" * 64, manifest_row_sha256="3" * 64)
    output = {"blocks": [{"kind": "paragraph", "bbox": [0, 0, 100, 100], "code_language": None,
                         "segments": [{"kind": "text", "text": "unverified prose "},
                                      {"kind": "math", "text": "x^2"}]}], "uncertainties": []}

    def proposal(document=raw, bound=scope, inputs=contract, data=output, response=None):
        return adapter.apply(document, bound, inputs, response or adapter.bind_response(inputs, data, response_sha256="4" * 64),
                             expected_input_fingerprint=inputs["input_fingerprint"], proposal_id="synthetic")

    accepted = proposal()
    assert accepted["markdown"] == "unverified prose $x^2$"
    assert adapter.render_batch(raw, [accepted])["provider_graph_unchanged"]
    crosslinked = []
    for reference, context in (("#/texts/12", "#/texts/13"), ("#/texts/13", "#/texts/12")):
        bound = adapter.bind_scope(raw, [reference], [context])
        inputs = adapter.bind_input(bound, image_sha256="1" * 64, image_pixels_wh=[100, 100],
                                    request_sha256="2" * 64, manifest_row_sha256="3" * 64)
        data = deepcopy(output)
        data["blocks"][0].update(kind="code", segments=[{"kind": "code", "text": "unverified_code()"}])
        crosslinked.append(proposal(bound=bound, inputs=inputs, data=data))
    assert len(adapter.render_batch(raw, crosslinked)["replacement_spans"]) == 2
    negative = {}

    def reject(name, action):
        try:
            action()
        except (ValueError, KeyError, TypeError) as error:
            negative[name] = str(error)
        else:
            raise AssertionError(name + " unexpectedly accepted")

    stale = deepcopy(raw)
    stale["texts"][0]["text"] += "changed outside scope"
    reject("stale_outside_document", lambda: proposal(document=stale))
    reject("foreign_ref", lambda: adapter.bind_scope(raw, ["#/texts/999999"], []))
    reject("duplicate_ref", lambda: adapter.bind_scope(raw, ["#/texts/4", "#/texts/4"], []))
    reject("overlap_context_consumed", lambda: adapter.bind_scope(raw, ["#/texts/4"], ["#/texts/4"]))
    reject("overlap_nested_target", lambda: adapter.bind_scope(raw, ["#/pictures/0", "#/texts/6"], []))
    reject("overlap_batch", lambda: adapter.render_batch(raw, [accepted, accepted]))
    stale_context = deepcopy(raw)
    stale_context["texts"][12]["text"] += "changed context"
    reject("stale_context", lambda: proposal(document=stale_context))
    shrink = deepcopy(scope)
    shrink["targets"][0]["replacement_charspan"][1] -= 1
    reject("target_shrink", lambda: proposal(bound=shrink))
    bad_hash = deepcopy(scope)
    bad_hash["targets"][0]["item_sha256"] = "0" * 64
    reject("changed_target_hash", lambda: proposal(bound=bad_hash))
    consumed_context = deepcopy(accepted)
    consumed_context["consumed_item_refs"].append("#/texts/12")
    reject("context_consumed_by_proposal", lambda: adapter.render_batch(raw, [consumed_context]))
    role = deepcopy(output)
    role["blocks"][0]["kind"] = "caption"
    reject("role_change", lambda: proposal(data=role))
    for label, segment in (("null", {"kind": "text", "text": None}), ("unknown", {"kind": "unknown", "text": "maybe"})):
        bad = deepcopy(output)
        bad["blocks"][0]["segments"] = [segment]
        reject(label, lambda bad=bad: proposal(data=bad))
    for label, key in (("changed_image", "image_sha256"), ("changed_prompt", "request_sha256")):
        fields = {name: contract[name] for name in ("image_sha256", "image_pixels_wh", "request_sha256", "manifest_row_sha256")}
        fields[key] = "9" * 64
        changed = adapter.bind_input(scope, **fields)
        old_response = adapter.bind_response(contract, output, response_sha256="4" * 64)
        reject(label, lambda changed=changed, old_response=old_response: proposal(inputs=changed, response=old_response))
    changed_scope = adapter.bind_scope(raw, ["#/texts/4"], [])
    changed_inputs = adapter.bind_input(changed_scope, image_sha256="1" * 64, image_pixels_wh=[100, 100],
                                       request_sha256="2" * 64, manifest_row_sha256="3" * 64)
    old_response = adapter.bind_response(contract, output, response_sha256="4" * 64)
    reject("old_response_new_context", lambda: proposal(bound=changed_scope, inputs=changed_inputs, response=old_response))
    changed_scope = adapter.bind_scope(raw, ["#/texts/12"], ["#/texts/4"])
    changed_inputs = adapter.bind_input(changed_scope, image_sha256="1" * 64, image_pixels_wh=[100, 100],
                                       request_sha256="2" * 64, manifest_row_sha256="3" * 64)
    reject("old_response_new_target", lambda: proposal(bound=changed_scope, inputs=changed_inputs, response=old_response))
    bad = deepcopy(output)
    bad["extra"] = True
    reject("extra_contract_field", lambda: proposal(data=bad))
    hidden = adapter.bind_scope(raw, ["#/texts/6"], [])
    hidden_inputs = adapter.bind_input(hidden, image_sha256="1" * 64, image_pixels_wh=[100, 100],
                                      request_sha256="2" * 64, manifest_row_sha256="3" * 64)
    formula = deepcopy(output)
    formula["blocks"][0].update(kind="formula", segments=[{"kind": "math", "text": "x^2"}])
    reject("hidden_serialized_target", lambda: proposal(bound=hidden, inputs=hidden_inputs, data=formula))
    save(HERE / "selfcheck.json", {"passed": True, "negative_controls": negative,
        "nonlexical_structure_accepts_unverified_content": True,
        "independent_unique_targets_may_share_original_snapshot_context": True,
        "semantic_quality": "not checked by structural adapter"})


def main():
    manifest_path = OLD / "inputs/input-manifest.json"
    manifest, frozen = read(manifest_path), read(FROZEN)
    registration = read(ROOT / "experiment.json")
    assert sha(FROZEN) == registration["frozen_regression_ref"]["sha256"]
    assert sha(REPO / manifest["prior_input_manifest_ref"]["path"]) == registration["provider_input_manifest_ref"]["sha256"]
    frozen_inputs = read(OLD / "inputs/artifact-sha256.json")
    assert sha(manifest_path) == frozen_inputs["input-manifest.json"]
    rows = [r for r in manifest["inputs"] if r["phase"] == "paragraph"]
    assert [r["id"] for r in rows] == frozen["paragraph_output_ids"] and len(rows) == 17
    prior_path = REPO / frozen["prior_paragraph_outputs_ref"]["path"]
    assert sha(prior_path) == frozen["prior_paragraph_outputs_ref"]["sha256"]
    prior = read(prior_path)
    raw_by_source, proposals_by_source, outcomes = {}, {}, []
    unchanged = {}
    for row in rows:
        raw_path = REPO / row["baseline_document_ref"]["path"]
        assert sha(raw_path) == row["baseline_document_ref"]["sha256"]
        source = raw_path.parent.name
        raw = raw_by_source.setdefault(source, read(raw_path))
        proposals_by_source.setdefault(source, [])
        scope, contract, response, evidence = original_contract(row, raw)
        record = {"id": row["id"], "source": source, "status": "not_applied", "legacy_only": True,
                  "scope": scope, "input_contract": contract, "original_evidence": evidence,
                  "original_blocks": response["data"], "semantic_quality": "unverified; frozen source review remains separate"}
        old_result = next(r for r in prior["prior_17"] if r["id"] == row["id"])
        record["previous_adapter_status"] = old_result["prior_adapter_status"]
        record["current_status_basis"] = "Exact whole-item scope, compatible native role and serializer reachability only; excludes lexical/content-truth gates"
        for entry in evidence.values():
            if isinstance(entry, dict) and set(entry) == {"path", "sha256"}:
                unchanged[entry["path"]] = entry["sha256"]
        unchanged[str(raw_path.relative_to(REPO))] = sha(raw_path)
        try:
            proposal = adapter.apply(raw, scope, contract, response,
                expected_input_fingerprint=contract["input_fingerprint"], proposal_id=row["id"])
            record.update(status="structurally_applied_semantics_unverified", markdown=proposal["markdown"],
                          segment_offsets=proposal["segment_offsets"])
            proposals_by_source[source].append(proposal)
        except ValueError as error:
            record["reason"] = str(error)
            if "dropped or serialized" in str(error):
                record["status"] = "unsupported_hidden_serializer_boundary"
        outcomes.append(record)
    selfcheck(raw_by_source["controls"])
    documents = []
    for source, raw in raw_by_source.items():
        folder = HERE / source
        folder.mkdir(exist_ok=True)
        rendered = adapter.render_batch(raw, proposals_by_source[source])
        for name in ("baseline", "working"):
            (folder / (name + ".md")).write_text(rendered.pop(name))
        before, after = (folder / "baseline.md").read_text(), (folder / "working.md").read_text()
        (folder / "delta.diff").write_text("".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                                                  fromfile="baseline.md", tofile="working.md")))
        save(folder / "association.json", {**rendered, "applied_ids": [p["id"] for p in proposals_by_source[source]],
            "cross_job_target_context_links": [{"context_job": p["id"], "target_job": q["id"], "item_ref": r}
                for p in proposals_by_source[source] for q in proposals_by_source[source] if p is not q
                for r in p["scope"]["context_only_refs"] if r in q["consumed_item_refs"]],
            "baseline_ref": ref(folder / "baseline.md"), "working_ref": ref(folder / "working.md"), "delta_ref": ref(folder / "delta.diff")})
        documents.append({"source": source, "baseline": ref(folder / "baseline.md"), "working": ref(folder / "working.md"),
                          "delta": ref(folder / "delta.diff"), "association": ref(folder / "association.json")})
    positives = []
    for anchor in frozen["protected_positive_anchors"]:
        outcome = next(r for r in outcomes if r["id"] == anchor["id"])
        assert outcome["status"] == "structurally_applied_semantics_unverified", anchor
        positives.append({**anchor, "structurally_eligible": True, "semantic_rubric_retested": False})
    for path, expected in unchanged.items():
        assert sha(REPO / path) == expected, path
    save(HERE / "original-artifact-hashes.json", unchanged)
    save(HERE / "results.json", {"format": "g2-context-legacy-adapter-regression-v1", "scope": "All17 saved paragraph outputs under original frozen request/image/target; no candidate inference",
        "adapter_ref": ref(ROOT / "adapter.py"), "driver_ref": ref(Path(__file__)), "frozen_regression_manifest_ref": ref(FROZEN),
        "frozen_parser_ref": ref(Path(adapter.parser.__file__)), "frozen_renderer_ref": ref(Path(adapter.renderer.__file__)),
        "prior_regression_ref": ref(prior_path), "prior_regression_artifact_unchanged": True,
        "new_model_calls": 0, "holdout_reads": 0, "lexical_gate": False,
        "structurally_applied": sum(r["status"] == "structurally_applied_semantics_unverified" for r in outcomes),
        "outcomes": outcomes, "protected_positive_anchors": positives, "documents": documents,
        "provider_graphs_and_original_model_artifacts_unchanged": True,
        "candidate_context_jobs_replay_compatible": False,
        "new_context_job_policy": "needs_new_inference unless exact original image/request/target/context fingerprint is proven identical",
        "known_source_quality_limit": "SEAL32 remains known bad despite structural eligibility; semantic quality is independently reviewed",
        "selfcheck_ref": ref(HERE / "selfcheck.json")})
    print(json.dumps({"legacy_count": len(outcomes), "applied": sum(r["status"] == "structurally_applied_semantics_unverified" for r in outcomes),
                      "positive_anchors_eligible": len(positives), "adapter_sha256": sha(ROOT / "adapter.py"), "results_sha256": sha(HERE / "results.json")}))


if __name__ == "__main__":
    main()
