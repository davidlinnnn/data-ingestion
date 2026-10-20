"""Small working Markdown delta; immutable provider graph and model responses stay in custody."""

import collections
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import statistics
import sys

from docling_core.transforms.serializer.base import BasePictureSerializer
from docling_core.transforms.serializer.common import create_ser_result
from docling_core.transforms.serializer.markdown import MarkdownDocSerializer, MarkdownPictureSerializer
from docling_core.types.doc import DoclingDocument

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ROOT = HERE.parent
OLD = REPO / "docs/research/pdf-core-g2-inline-2026-10-15/reinsertion/apply.py"
API_OLD = REPO / "docs/research/pdf-core-g2-inline-api-2026-10-15"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("frozen_boundary_provider_guards", OLD)
prior_api = load("frozen_boundary_api_association", API_OLD / "reinsertion/apply.py")
parser = load("frozen_boundary_json_contract", API_OLD / "parsed/parse.py")
read, save, sha, digest = old.read, old.save, old.sha, old.digest


def ref(path):
    return {"path": str(path.relative_to(REPO)), "sha256": sha(path)}


def checked(reference):
    path = REPO / reference["path"]
    if sha(path) != reference["sha256"]:
        raise ValueError("stale evidence: " + reference["path"])
    return path


def item(raw, reference):
    collection, index = reference[2:].split("/")
    result = raw[collection][int(index)]
    if result["self_ref"] != reference:
        raise ValueError("unknown provider reference")
    return result


def normalized(text):
    return re.sub(r"\s+", "", text)


def segment_text(block):
    return "".join(s["text"] or "" for s in block["segments"])


def identifiers(text, latex=False):
    if latex:
        # Command names are syntax; their braced contents (including text/identifiers) remain.
        text = re.sub(r"\\+[A-Za-z]+", " ", text)
    return collections.Counter(re.findall(r"[A-Za-z]{2,}", text))


def conservation(native, target_block):
    before = identifiers(native)
    after = collections.Counter()
    for segment in target_block["segments"]:
        after.update(identifiers(segment["text"] or "", segment["kind"] == "math"))
    missing = before - after
    if missing:
        raise ValueError("native multiletter identifier/word occurrence loss: " + json.dumps(dict(missing), sort_keys=True))
    return {"native_multiletter_counts": dict(before), "target_multiletter_counts": dict(after),
        "limit": "Conservative occurrence coverage only; no general math equivalence, single-letter/prime/operator or spelling proof; hyphenation may abstain"}


def scope_guard(raw, plan, consumed):
    if consumed != plan["consumed_item_refs"] or len(set(consumed)) != len(consumed):
        raise ValueError("changed, duplicate, or out-of-scope consumed refs")
    if set(consumed) & set(plan.get("context_only_refs", [])):
        raise ValueError("context-only item cannot be consumed")
    if digest(raw) != plan["canonical_document_sha256"]:
        raise ValueError("stale document or outside-scope content changed")
    rows, proposals = [], []
    for reference in consumed:
        current = item(raw, reference)
        if digest(current) != plan["item_hashes"][reference]:
            raise ValueError("stale consumed item")
        if reference.startswith("#/texts/"):
            common = {"candidate_id": reference, "item_ref": reference,
                "replacement_charspan": [0, len(current["text"])],
                "provider_text_sha256": hashlib.sha256(current["text"].encode()).hexdigest()}
            rows.append({**common, "canonical_document_sha256": plan["canonical_document_sha256"],
                "item_sha256": digest(current), "neighbors": []})
            proposals.append(common)
    old.validate_batch(raw, rows, proposals)


def code_guard(raw, row, block, cells):
    bounds = row["source_fragments"][0]["bbox_top_left_points"]
    selected = []
    for cell in cells["textline_cells"]:
        r = cell["rect"]
        box = [min(r[f"r_x{i}"] for i in range(4)), min(r[f"r_y{i}"] for i in range(4)),
            max(r[f"r_x{i}"] for i in range(4)), max(r[f"r_y{i}"] for i in range(4))]
        if box[0] >= bounds[0]-.1 and box[2] <= bounds[2]+.1 and box[1] >= bounds[1]-.1 and box[3] <= bounds[3]+.1:
            selected.append((cell, box))
    selected.sort(key=lambda value: (value[1][1], value[1][0]))
    native = " ".join(item(raw, r)["text"] for r in row["consumed_item_refs"])
    if not selected or normalized(" ".join(c["text"] for c, _ in selected)) != normalized(native):
        raise ValueError("native code cells do not completely cover the consumed items")
    widths = [(box[2]-box[0])/len(c["text"]) for c, box in selected if c["text"]]
    pitch = statistics.median(widths)
    if pitch <= 0 or any(abs(w-pitch) > .01 for w in widths) or len({c["font_key"] for c, _ in selected}) != 1:
        raise ValueError("native code is not demonstrably one monospace cell run")
    lines = segment_text(block).splitlines()
    if len(lines) != len(selected):
        raise ValueError("code line count changed")
    left = min(box[0] for _, box in selected)
    evidence = []
    for output, (cell, box) in zip(lines, selected, strict=True):
        indent_float = (box[0]-left)/pitch
        indent = round(indent_float)
        if abs(indent_float-indent) > .01 or output != " "*indent+cell["text"]:
            raise ValueError("code characters/operators/order/indentation differ from native line evidence")
        evidence.append({"native_cell_index": cell["index"], "text": cell["text"], "source_left_points": box[0], "indent_spaces": indent})
    return {"native_character_pitch_points": pitch, "lines": evidence, "native_code_font_key": selected[0][0]["font_key"]}


class PictureSubstitution(BasePictureSerializer):
    def __init__(self, replacements):
        self.replacements, self.seen = replacements, []

    def serialize(self, *, item, doc_serializer, doc, **kwargs):
        if item.self_ref in self.replacements:
            self.seen.append(item.self_ref)
            return create_ser_result(text=self.replacements[item.self_ref], span_source=item)
        return MarkdownPictureSerializer().serialize(item=item, doc_serializer=doc_serializer, doc=doc, **kwargs)


def render(document, proposals):
    replacements = {}
    for p in proposals:
        for i, reference in enumerate(p["consumed_item_refs"]):
            if reference in replacements:
                raise ValueError("two working proposals consume the same provider item")
            replacements[reference] = (p["id"], p["markdown"] if i == 0 else "")
    markers = {r: "BOUNDARYOUTPUT"+hashlib.sha256(r.encode()).hexdigest() for r in replacements}
    text = old.SubstitutionSerializer(markers)
    picture = PictureSubstitution(markers)
    template = MarkdownDocSerializer(doc=document, text_serializer=text, picture_serializer=picture).serialize().text
    if collections.Counter(text.seen+picture.seen) != collections.Counter(markers.keys()):
        raise ValueError("consumed boundary dropped or serialized more than once")
    matches = sorted((template.index(marker), r, marker) for r, marker in markers.items() if template.count(marker) == 1)
    if len(matches) != len(markers):
        raise ValueError("nonunique boundary marker")
    result, cursor, spans, outside = "", 0, {}, []
    for position, reference, marker in matches:
        literal = template[cursor:position]
        start = len(result)
        result += literal
        outside.append({"working_charspan": [start, len(result)], "sha256": hashlib.sha256(literal.encode()).hexdigest()})
        identifier, replacement = replacements[reference]
        start = len(result)
        result += replacement
        spans[reference] = {"proposal_id": identifier, "charspan": [start, len(result)], "suppressed_serialized_duplicate": not replacement}
        cursor = position+len(marker)
    literal = template[cursor:]
    start = len(result)
    result += literal
    outside.append({"working_charspan": [start, len(result)], "sha256": hashlib.sha256(literal.encode()).hexdigest()})
    return result, spans, outside


def native_boundary(raw, row):
    first_ref, tail_ref = row["consumed_item_refs"]
    first, tail = item(raw, first_ref), item(raw, tail_ref)
    a, b = first["prov"]
    left, title = first["text"][slice(*a["charspan"])], first["text"][slice(*b["charspan"])]
    reuse = row["retained_spatial_fragment_reuse"]
    reused = read(checked(reuse))
    reused_block = reused
    for part in reuse["json_pointer"].strip("/").split("/"):
        reused_block = reused_block[int(part)] if isinstance(reused_block, list) else reused_block[part]
    if normalized(segment_text(reused_block)) != normalized(title) or reuse["provider_provenance"] != b:
        raise ValueError("parallel title evidence does not match native source fragment")
    gap = [a["charspan"][1], b["charspan"][0]]
    chunks = [(first_ref, a["charspan"], left), (first_ref, gap, first["text"][slice(*gap)]),
        (tail_ref, [0, len(tail["text"])], tail["text"]), (first_ref, b["charspan"], title)]
    if not all(c.isspace() for c in chunks[1][2]):
        raise ValueError("unaccounted nonwhitespace source gap")
    for reference in row["consumed_item_refs"]:
        ranges = sorted((span, value) for r, span, value in chunks if r == reference)
        cursor = 0
        for span, value in ranges:
            if span[0] != cursor or value != item(raw, reference)["text"][slice(*span)]:
                raise ValueError("native boundary missing/duplicate source span")
            cursor = span[1]
        if cursor != len(item(raw, reference)["text"]):
            raise ValueError("native boundary drops source suffix")
    body = "".join(value for _, _, value in chunks[:3])
    title_markup = parser.text_markup(title)
    markdown = parser.text_markup(body)+"\n\n"+title_markup
    offsets, cursor = [], 0
    for index, (reference, span, value) in enumerate(chunks):
        if index == 3:
            cursor += 2
        markup = parser.text_markup(value)
        offsets.append({"item_ref": reference, "source_charspan": span, "markdown_charspan": [cursor, cursor+len(markup)],
            "exact_native_text": value, "rendered_markup": markup})
        cursor += len(markup)
    assert cursor == len(markdown)
    return {"id": row["id"]+"-native-boundary", "method": "native_boundary_fallback", "status": "applied_native_boundary_only",
        "consumed_item_refs": row["consumed_item_refs"], "markdown": markdown,
        "native_blocks": [{"kind": "paragraph", "text": body}, {"kind": "spatially_separate_unknown_title", "text": title,
            "inferred_role_lineage": row["retained_spatial_fragment_reuse"], "native_label": "text"}],
        "source_charspan_accounting": [{"item_ref": r, "charspan": span, "exact_native_text": value} for r, span, value in chunks],
        "native_output_segment_offsets": offsets,
        "native_characters_accounted_exactly_once": True, "AI_transcription_used": False, "math_completion_claim": False}


def model_proposal(raw, row, cells):
    folder = ROOT / "parsed" / row["id"]
    if (folder / "failure.json").exists():
        return {"id": row["id"], "method": "new_API_response", "status": "not_applied", "consumed_item_refs": row["consumed_item_refs"],
            "reason": "response contract/parse failed", "parse_failure_ref": ref(folder / "failure.json")}
    mapped = read(folder / "render-map.json")
    data = read(folder / "original-blocks.json")
    if checked(mapped["api_output_ref"]).read_bytes() != (folder / "original-blocks.json").read_bytes():
        if read(checked(mapped["api_output_ref"])) != data:
            raise ValueError("parsed blocks differ from raw response")
    result = {"id": row["id"], "method": "new_API_response", "status": "not_applied", "consumed_item_refs": row["consumed_item_refs"],
        "model_blocks_ref": ref(folder / "original-blocks.json"), "render_map_ref": ref(folder / "render-map.json"),
        "model_markdown": (folder / "document.md").read_text(), "all_model_blocks": data, "uncertainties": data["uncertainties"],
        "source_fragments": row["source_fragments"], "context_only_refs": row["context_only_refs"]}
    try:
        if mapped["input_metadata"] != row or not mapped["eligible_for_association"]:
            raise ValueError("stale input metadata or unresolved source segments")
        if sha(folder / "document.md") != mapped["markdown_sha256"]:
            raise ValueError("stale parsed Markdown")
        target = data["blocks"]
        if row["context_only_refs"]:
            expected = [item(raw, r)["label"] for r in row["context_only_refs"]]
            if len(target) != 1+len(expected) or [b["kind"] for b in target[1:]] != expected:
                raise ValueError("context block shape does not match declared context refs")
            result["context_blocks_retained_supplementally"] = target[1:]
            target = target[:1]
        label = "formula" if row["member_item_refs"] else item(raw, row["consumed_item_refs"][0])["label"]
        references = row["member_item_refs"] or row["consumed_item_refs"]
        native = " ".join(item(raw, r).get("text", "") for r in references)
        if "retained_spatial_fragment_reuse" in row:
            first = item(raw, references[0])
            native = first["text"][slice(*first["prov"][0]["charspan"])] + " " + item(raw, references[1])["text"]
        old.check_shape({"provider_label": label, "provider_text": native}, prior_api.guard_view(target))
        result["conservation"] = conservation(native, target[0])
        if label == "code":
            result["code_character_operator_indentation_evidence"] = code_guard(raw, row, target[0], cells)
        if label == "formula":
            before = collections.Counter(re.findall(r"-?\d+(?:\.\d+)?", native))
            after = collections.Counter(re.findall(r"-?\d+(?:\.\d+)?", segment_text(target[0])))
            if before-after:
                raise ValueError("native signed numeric occurrences lost")
            result["native_signed_numeric_coverage"] = dict(before)
        markdown, offsets = parser.render({"blocks": target, "uncertainties": data["uncertainties"]})
        result.update(status="applied_model_structure_semantics_unverified", markdown=markdown, segment_offsets=offsets)
    except ValueError as error:
        result["reason"] = str(error)
    return result


def inline_reuse(raw, reuse, code_font):
    data = read(checked(reuse))
    reference = reuse["target_ref"]
    native = item(raw, reference)
    blocks = data["blocks"]
    if native["label"] != reuse["original_role"] or len(blocks) != 1 or blocks[0]["kind"] != reuse["working_role"]:
        raise ValueError("role override differs from frozen evidence")
    segments = blocks[0]["segments"]
    words = reuse["native_word_styles"]
    if {s["kind"] for s in segments} != {"text", "code"} or len({w["font_key"] for w in words}) < 2:
        raise ValueError("role override lacks mixed prose/code evidence")
    native_code = " ".join(w["text"] for w in words if w["font_key"] == code_font)
    native_prose = " ".join(w["text"] for w in words if w["font_key"] != code_font)
    for kind, source in (("code", native_code), ("text", native_prose)):
        if normalized("".join(s["text"] or "" for s in segments if s["kind"] == kind)) != normalized(source):
            raise ValueError("role override token/operator/style run mismatch")
    if normalized(segment_text(blocks[0])) != normalized(native["text"]):
        raise ValueError("role override changes native characters")
    markdown, offsets = parser.render(data)
    return {"id": "controls-inline-role-reuse", "method": "prior_API_role_reuse", "status": "applied_frozen_role_override",
        "consumed_item_refs": [reference], "markdown": markdown, "frozen_reuse_evidence": reuse,
        "all_model_blocks": data, "segment_offsets": offsets, "original_provider_role": native["label"], "working_role": blocks[0]["kind"]}


def main():
    assert not (HERE / "artifact-sha256.json").exists(), "frozen working outputs; use verify.py"
    manifest = read(ROOT / "inputs/input-manifest.json")
    for name, expected in read(ROOT / "inputs/artifact-sha256.json").items():
        assert sha(ROOT / "inputs" / name) == expected
    for prior in manifest["prior_payload_manifests"]:
        for payload in read(checked(prior))["files"]:
            checked(payload)
    checked(manifest["registry_ref"])
    cells = read(checked(manifest["native_cells_ref"]))
    plans, proposals, sources = [], [], {}
    for row in manifest["inputs"]:
        raw = read(checked(row["baseline_document_ref"]))
        checked(row["source"])
        source = Path(row["baseline_document_ref"]["path"]).parent.name
        sources[source] = (raw, row["baseline_document_ref"])
        plan = {"id": row["id"], "source": source, "canonical_document_sha256": digest(raw),
            "consumed_item_refs": row["consumed_item_refs"], "member_item_refs": row["member_item_refs"], "context_only_refs": row["context_only_refs"],
            "item_hashes": {r: digest(item(raw, r)) for r in row["consumed_item_refs"]}}
        scope_guard(raw, plan, row["consumed_item_refs"])
        plans.append(plan)
        proposal = model_proposal(raw, row, cells)
        proposal.update(source=source, original_input_metadata=row)
        proposals.append(proposal)
        if "retained_spatial_fragment_reuse" in row:
            checked(row["retained_spatial_fragment_reuse"])
            fallback = native_boundary(raw, row)
            fallback.update(source=source, source_fragments=row["source_fragments"], original_input_metadata=row)
            proposals.append(fallback)
    code = next(p for p in proposals if p["id"] == "controls-code-context")
    raw = sources[code["source"]][0]
    try:
        reuse = inline_reuse(raw, manifest["reused_without_inference"]["inline_role"], code["code_character_operator_indentation_evidence"]["native_code_font_key"])
    except (ValueError, KeyError) as error:
        reuse = {"id": "controls-inline-role-reuse", "method": "prior_API_role_reuse", "status": "not_applied",
            "consumed_item_refs": [manifest["reused_without_inference"]["inline_role"]["target_ref"]], "reason": str(error)}
    reuse["source"] = code["source"]
    proposals.append(reuse)
    plans.append({"id": reuse["id"], "source": reuse["source"], "canonical_document_sha256": digest(raw),
        "consumed_item_refs": reuse["consumed_item_refs"], "context_only_refs": [], "item_hashes": {r: digest(item(raw, r)) for r in reuse["consumed_item_refs"]}})
    for source, (raw, reference) in sources.items():
        folder = HERE / source
        folder.mkdir(exist_ok=True)
        document = DoclingDocument.model_validate(raw)
        before = digest(raw)
        accepted = [p for p in proposals if p["source"] == source and p["status"] != "not_applied"]
        for p in accepted:
            plan_id = p["original_input_metadata"]["id"] if "original_input_metadata" in p else p["id"]
            scope_guard(raw, next(r for r in plans if r["id"] == plan_id), p["consumed_item_refs"])
        baseline = document.export_to_markdown()
        assert render(document, [])[0] == baseline
        markdown, spans, outside = render(document, accepted)
        assert digest(raw) == before
        for chunk in outside:
            assert hashlib.sha256(markdown[slice(*chunk["working_charspan"])].encode()).hexdigest() == chunk["sha256"]
        for p in accepted:
            start, stop = spans[p["consumed_item_refs"][0]]["charspan"]
            assert markdown[start:stop] == p["markdown"]
            local = p.get("native_output_segment_offsets", [s for b in p.get("segment_offsets", []) for s in b["segments"]])
            p["main_markdown_segment_offsets"] = [{**s, "main_markdown_charspan": [start+s["markdown_charspan"][0], start+s["markdown_charspan"][1]]} for s in local]
            for s in p["main_markdown_segment_offsets"]:
                assert markdown[slice(*s["main_markdown_charspan"])] == s["rendered_markup"]
        (folder / "baseline.md").write_text(baseline)
        (folder / "working.md").write_text(markdown)
        save(folder / "working-delta.json", {"format": "g2-boundary-working-delta-v1", "provider_document_ref": reference,
            "original_provider_graph_and_assets_unchanged": True, "new_Docling_document_claim": False,
            "model_acceptance_is_not_semantic_approval": True, "scope_and_literal_order_checks_passed": True,
            "proposals": [p for p in proposals if p["source"] == source], "working_serialization_spans": spans,
            "unchanged_outside_literal_spans": outside,
            "source_precision": "Original native fragment/component bounds plus render affine maps; no measured output-token/glyph source boxes"})
    save(HERE / "plan.json", {"rows": plans, "input_manifest_ref": ref(ROOT / "inputs/input-manifest.json"), "immutable_guard_ref": ref(OLD)})
    save(HERE / "summary.json", {"proposal_count": len(proposals), "status_counts": dict(collections.Counter(p["status"] for p in proposals)),
        "outcomes": [{k: p[k] for k in ("id", "method", "status", "reason") if k in p} for p in proposals],
        "adapter_ref": ref(Path(__file__)), "reused_parser_ref": ref(API_OLD / "parsed/parse.py"),
        "api_calls": 0, "new_inference": 0, "prior_646_plus_200_payloads_unchanged": True})
    print("Saved guarded working Markdown and all rejected model proposals without provider mutation.")


def selfcheck():
    passed = []
    def reject(name, function):
        try:
            function()
        except (ValueError, KeyError, IndexError):
            passed.append(name)
        else:
            raise AssertionError("negative control accepted: " + name)
    block = {"kind": "paragraph", "segments": [{"kind": "math", "text": "AB_{x}"}]}
    conservation("AB", block)
    reject("balanced_split_identifier", lambda: conservation("AB", {**block, "segments": [{"kind": "math", "text": "A_{B_x}"}]}))
    reject("prose_occurrence_loss", lambda: conservation("parameters parameters", {**block, "segments": [{"kind": "text", "text": "parameters"}]}))
    native_example = "alpha beta gamma delta epsilon zeta"
    repeat_block = {"kind": "paragraph", "segments": [{"kind": "text", "text": (native_example+" ")*2}]}
    reject("new_repeated_prose_run", lambda: old.check_shape({"provider_label": "text", "provider_text": native_example}, prior_api.guard_view([repeat_block])))
    reject("multiple_root_blocks", lambda: old.check_shape({"provider_label": "text", "provider_text": native_example}, prior_api.guard_view([block, block])))
    manifest = read(ROOT / "inputs/input-manifest.json")
    reject("stale_evidence_hash", lambda: checked({**manifest["registry_ref"], "sha256": "0"*64}))
    for r in manifest["inputs"]:
        raw = read(checked(r["baseline_document_ref"]))
        plan = {**r, "canonical_document_sha256": digest(raw), "item_hashes": {x: digest(item(raw, x)) for x in r["consumed_item_refs"]}}
        scope_guard(raw, plan, r["consumed_item_refs"])
        reject("scoped_refs:"+r["id"], lambda: scope_guard(raw, plan, r["consumed_item_refs"]+["#/texts/9999"]))
    row = next(r for r in manifest["inputs"] if "retained_spatial_fragment_reuse" in r)
    raw = read(checked(row["baseline_document_ref"]))
    fallback = native_boundary(raw, row)
    assert fallback["native_characters_accounted_exactly_once"]
    broken = copy.deepcopy(raw)
    first = item(broken, row["consumed_item_refs"][0])
    first["prov"][1]["charspan"][1] -= 1
    reject("missing_title_char", lambda: native_boundary(broken, row))
    reject("missing_title_evidence", lambda: native_boundary(raw, {k: v for k, v in row.items() if k != "retained_spatial_fragment_reuse"}))
    reject("duplicate_consumed_continuation", lambda: scope_guard(raw, {**row, "canonical_document_sha256": digest(raw)}, row["consumed_item_refs"]*2))
    old32 = read(API_OLD / "api/paragraph--seal-texts-32/output.json")
    native32 = read(checked(row["baseline_document_ref"]))["texts"][32]["text"]
    reject("prior_saved_wrong_target_identifier", lambda: conservation(native32, old32["blocks"][0]))
    context_row = next(r for r in manifest["inputs"] if r["context_only_refs"])
    current = read(ROOT / "api" / context_row["id"] / "output.json")
    reject("context_cannot_satisfy_target_identity", lambda: conservation(native32, current["blocks"][0]))
    code_row = next(r for r in manifest["inputs"] if r["id"] == "controls-code-context")
    raw = read(checked(code_row["baseline_document_ref"]))
    cells = read(checked(manifest["native_cells_ref"]))
    code = read(ROOT / "api" / code_row["id"] / "output.json")["blocks"][0]
    evidence = code_guard(raw, code_row, code, cells)
    for name, text in (("operator_changed", segment_text(code).replace("<=", "<")),
        ("indent_changed", segment_text(code).replace("    total", "total")),
        ("duplicate_continuation", segment_text(code)+"\n"+segment_text(code).splitlines()[-1])):
        reject(name, lambda text=text: code_guard(raw, code_row, {**code, "segments": [{"kind": "code", "text": text}]}, cells))
    reuse = manifest["reused_without_inference"]["inline_role"]
    inline_reuse(raw, reuse, evidence["native_code_font_key"])
    reject("unfrozen_role_override", lambda: inline_reuse(raw, {**reuse, "working_role": "code"}, evidence["native_code_font_key"]))
    bad = copy.deepcopy(raw)
    bad["texts"][0]["text"] += "outside"
    plan = {**code_row, "canonical_document_sha256": digest(raw), "item_hashes": {r: digest(item(raw, r)) for r in code_row["consumed_item_refs"]}}
    reject("outside_scope_mutation", lambda: scope_guard(bad, plan, code_row["consumed_item_refs"]))
    save(HERE / "selfcheck.json", {"passed": True, "negative_controls": passed, "native_boundary_char_coverage_checked": True,
        "positive_code_native_characters_operators_indentation_checked": True, "generic_identifier_guard_not_math_equivalence": True})
    print("Boundary guard self-check passed.")


if __name__ == "__main__":
    selfcheck() if sys.argv[1:] == ["--selfcheck"] else main()
