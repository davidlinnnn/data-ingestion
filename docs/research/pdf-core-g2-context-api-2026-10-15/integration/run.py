"""Apply unchanged whole-item adapter 1 to every fresh output; semantics stay separate."""

from copy import deepcopy
import difflib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = load("context_integration_api_verifier", ROOT / "api/verify.py")
adapter = load("context_integration_frozen_adapter", verify.CANDIDATE / "adapter.py")


def selfcheck():
    rows = verify.inputs()
    row = next(r for r in rows if r["source"] == "controls")
    raw = verify.read(verify.checked(row["provider_document_ref"]))
    scope = adapter.bind_scope(raw, ["#/texts/4"], ["#/texts/12"])
    contract = adapter.bind_input(scope, image_sha256="1" * 64, image_pixels_wh=[100, 100],
                                 request_sha256="2" * 64, manifest_row_sha256="3" * 64)
    output = {"blocks": [{"kind": "paragraph", "bbox": [0, 0, 100, 100], "code_language": None,
                         "segments": [{"kind": "text", "text": "unverified source content "},
                                      {"kind": "math", "text": "x^2"}]}], "uncertainties": []}

    def proposal(document=raw, bound=scope, inputs=contract, data=output, response=None):
        return adapter.apply(document, bound, inputs, response or adapter.bind_response(inputs, data, response_sha256="4" * 64),
                             expected_input_fingerprint=inputs["input_fingerprint"], proposal_id="synthetic")

    accepted = proposal()
    assert accepted["markdown"] == "unverified source content $x^2$"
    assert adapter.render_batch(raw, [accepted])["provider_graph_unchanged"]
    linked = []
    for target, context in (("#/texts/12", "#/texts/13"), ("#/texts/13", "#/texts/12")):
        bound = adapter.bind_scope(raw, [target], [context])
        inputs = adapter.bind_input(bound, image_sha256="1" * 64, image_pixels_wh=[100, 100],
                                    request_sha256="2" * 64, manifest_row_sha256="3" * 64)
        data = deepcopy(output)
        data["blocks"][0].update(kind="code", segments=[{"kind": "code", "text": "unverified_code()"}])
        p = proposal(bound=bound, inputs=inputs, data=data)
        p["id"] = target
        linked.append(p)
    assert len(adapter.render_batch(raw, linked)["replacement_spans"]) == 2
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
    reject("context_consumed_as_target", lambda: adapter.bind_scope(raw, ["#/texts/4"], ["#/texts/4"]))
    reject("nested_target_overlap", lambda: adapter.bind_scope(raw, ["#/pictures/0", "#/texts/6"], []))
    reject("batch_target_overlap", lambda: adapter.render_batch(raw, [accepted, accepted]))
    stale = deepcopy(raw)
    stale["texts"][12]["text"] += "changed context"
    reject("stale_context", lambda: proposal(document=stale))
    shrink = deepcopy(scope)
    shrink["targets"][0]["replacement_charspan"][1] -= 1
    reject("target_span_shrunk", lambda: proposal(bound=shrink))
    bad_scope = deepcopy(scope)
    bad_scope["targets"][0]["item_sha256"] = "0" * 64
    reject("target_item_hash_changed", lambda: proposal(bound=bad_scope))
    consumed = deepcopy(accepted)
    consumed["consumed_item_refs"].append("#/texts/12")
    reject("proposal_consumes_context", lambda: adapter.render_batch(raw, [consumed]))
    for label, update in (("wrong_block_role", {"kind": "caption"}),
                          ("null_segment", {"segments": [{"kind": "text", "text": None}]}),
                          ("unknown_segment", {"segments": [{"kind": "unknown", "text": "maybe"}]})):
        bad = deepcopy(output)
        bad["blocks"][0].update(update)
        reject(label, lambda bad=bad: proposal(data=bad))
    duplicate = deepcopy(output)
    duplicate["blocks"] *= 2
    reject("context_or_duplicate_extra_block", lambda: proposal(data=duplicate))
    old_response = adapter.bind_response(contract, output, response_sha256="4" * 64)
    for name in ("image_sha256", "request_sha256", "manifest_row_sha256", "image_pixels_wh"):
        fields = {key: contract[key] for key in ("image_sha256", "image_pixels_wh", "request_sha256", "manifest_row_sha256")}
        fields[name] = [101, 100] if name == "image_pixels_wh" else "9" * 64
        changed = adapter.bind_input(scope, **fields)
        reject("changed_" + name, lambda changed=changed: proposal(inputs=changed, response=old_response))
    for label, target, context in (("new_context", ["#/texts/4"], []),
                                   ("new_target", ["#/texts/12"], ["#/texts/4"])):
        changed_scope = adapter.bind_scope(raw, target, context)
        changed = adapter.bind_input(changed_scope, image_sha256="1" * 64, image_pixels_wh=[100, 100],
                                     request_sha256="2" * 64, manifest_row_sha256="3" * 64)
        reject("old_response_" + label, lambda changed=changed, changed_scope=changed_scope:
               proposal(bound=changed_scope, inputs=changed, response=old_response))
    extra = deepcopy(output)
    extra["extra"] = True
    reject("extra_contract_field", lambda: proposal(data=extra))
    changed_response = deepcopy(old_response)
    changed_response["data"]["blocks"][0]["segments"][0]["text"] += "changed"
    reject("output_changed_after_binding", lambda: proposal(response=changed_response))
    hidden = adapter.bind_scope(raw, ["#/texts/6"], [])
    hidden_input = adapter.bind_input(hidden, image_sha256="1" * 64, image_pixels_wh=[100, 100],
                                    request_sha256="2" * 64, manifest_row_sha256="3" * 64)
    formula = deepcopy(output)
    formula["blocks"][0].update(kind="formula", segments=[{"kind": "math", "text": "x^2"}])
    reject("hidden_serializer_boundary", lambda: proposal(bound=hidden, inputs=hidden_input, data=formula))
    verify.save(HERE / "selfcheck.json", {"passed": True, "negative_controls": negative,
        "unverified_semantic_content_structurally_allowed": True,
        "unique_target_jobs_can_use_each_others_original_snapshot_context": True,
        "no_lexical_or_source_truth_gate": True, "new_model_outputs_read": 0})
    return len(negative)


def main():
    rows, exchanges = verify.verify_all()
    parsed = verify.read(ROOT / "parsed/summary.json")
    assert parsed["output_count"] == len(rows) == 36
    raw_by_source, proposals_by_source, outcomes = {}, {}, []
    for row, exchange in zip(rows, exchanges, strict=True):
        source, job_id = row["source"], row["job_id"]
        raw_path = verify.checked(row["provider_document_ref"])
        raw = raw_by_source.setdefault(source, verify.read(raw_path))
        proposals_by_source.setdefault(source, [])
        request = verify.read(verify.checked(row["request_contract_ref"]))
        scope = adapter.bind_scope(raw, row["target_item_refs"], row["context_only_refs"])
        assert scope["expected_block_roles"] == [request["native_target_role"]]
        assert [m["item_ref"] for m in scope["members"]] == row["member_item_refs"]
        contract = adapter.bind_input(scope, image_sha256=row["image_ref"]["sha256"], image_pixels_wh=row["image_pixels_wh"],
            request_sha256=exchange["request_description_ref"]["sha256"], manifest_row_sha256=verify.digest(row))
        output = verify.read(verify.checked(exchange["output_ref"]))
        response = adapter.bind_response(contract, output, response_sha256=exchange["response_ref"]["sha256"])
        folder = ROOT / "parsed" / source / job_id
        outcome = {"source": source, "job_id": job_id, "status": "not_applied", "scope": scope,
            "input_contract": contract, "exchange": exchange, "original_input_metadata": row,
            "all_model_blocks": output, "semantic_quality": "unverified; source review is separate",
            "structural_application_is_not_semantic_acceptance": True}
        try:
            if (folder / "failure.json").exists():
                raise ValueError("frozen strict parser rejected this output")
            mapped = verify.read(folder / "render-map.json")
            assert mapped["input_metadata"] == row and mapped["exchange"] == exchange
            assert verify.read(verify.checked(mapped["original_blocks_ref"])) == output
            p = adapter.apply(raw, scope, contract, response,
                              expected_input_fingerprint=contract["input_fingerprint"], proposal_id=source + "/" + job_id)
            assert p["markdown"] == verify.checked(mapped["markdown_ref"]).read_text()
            outcome.update(status="structurally_applied_semantics_unverified", markdown=p["markdown"], proposal=p)
            proposals_by_source[source].append(p)
        except ValueError as error:
            outcome["reason"] = str(error)
            if "dropped or serialized" in str(error):
                outcome["status"] = "unsupported_hidden_serializer_boundary"
        outcomes.append(outcome)
    documents = []
    for source, raw in raw_by_source.items():
        folder = HERE / source
        folder.mkdir(exist_ok=False)
        proposals = proposals_by_source[source]
        rendered = adapter.render_batch(raw, proposals)
        for name in ("baseline", "working"):
            (folder / (name + ".md")).write_text(rendered.pop(name))
        before, after = (folder / "baseline.md").read_text(), (folder / "working.md").read_text()
        (folder / "delta.diff").write_text("".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                                                  fromfile="baseline.md", tofile="working.md")))
        for p in proposals:
            start, end = rendered["replacement_spans"][p["consumed_item_refs"][0]]["charspan"]
            assert after[start:end] == p["markdown"]
            for block in p["segment_offsets"]:
                for segment in block["segments"]:
                    left, right = segment["markdown_charspan"]
                    assert after[start+left:start+right] == segment["rendered_markup"]
        verify.save(folder / "proposals.json", proposals)
        verify.save(folder / "association.json", {**rendered, "applied_ids": [p["id"] for p in proposals],
            "cross_job_original_snapshot_context_links": [{"context_job": p["id"], "target_job": q["id"], "item_ref": r}
                for p in proposals for q in proposals if p is not q
                for r in p["scope"]["context_only_refs"] if r in q["consumed_item_refs"]],
            "baseline_ref": verify.ref(folder / "baseline.md"), "working_ref": verify.ref(folder / "working.md"),
            "delta_ref": verify.ref(folder / "delta.diff"), "proposals_ref": verify.ref(folder / "proposals.json")})
        documents.append({"source": source, "baseline": verify.ref(folder / "baseline.md"),
            "working": verify.ref(folder / "working.md"), "delta": verify.ref(folder / "delta.diff"),
            "association": verify.ref(folder / "association.json"), "proposals": verify.ref(folder / "proposals.json")})
    negative_count = selfcheck()
    verify.inputs()
    verify.save(HERE / "results.json", {"format": "g2-context-fresh-structural-integration-v1", "adapter_number": 1,
        "adapter_ref": verify.ref(verify.CANDIDATE / "adapter.py"), "driver_ref": verify.ref(Path(__file__)),
        "frozen_parser_ref": verify.ref(verify.PARSER), "frozen_renderer_ref": verify.ref(Path(adapter.renderer.__file__)),
        "input_manifest_ref": verify.ref(verify.MANIFEST), "api_verification_ref": verify.ref(ROOT / "api/verification.json"),
        "parse_summary_ref": verify.ref(ROOT / "parsed/summary.json"), "selfcheck_ref": verify.ref(HERE / "selfcheck.json"),
        "inputs": len(rows), "structurally_applied": sum(len(p) for p in proposals_by_source.values()),
        "outcomes": outcomes, "documents": documents, "negative_controls": negative_count,
        "all_original_inputs_and_provider_graphs_unchanged": True,
        "all_outside_serialized_literals_unchanged": True, "lexical_truth_gate": False,
        "candidate_working_markdown_only": True, "canonical_acceptance": False,
        "semantic_quality_assessed": False, "holdout_reads": 0})
    print("Saved all 36 structural outcomes and separate candidate Markdown; semantic source review remains required.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        print("Passed " + str(selfcheck()) + " boundary negative controls without reading new model outputs.")
    else:
        assert not sys.argv[1:]
        main()
