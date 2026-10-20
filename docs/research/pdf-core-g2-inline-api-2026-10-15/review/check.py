"""Independent saved-response review. No API client, credential or inference imports."""

import ast
import base64
from copy import deepcopy
from difflib import SequenceMatcher
from hashlib import sha256
import importlib.util
from html import escape
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parents[1]
OLD = ROOT / "docs/research/pdf-core-g2-inline-2026-10-15"
REGISTRY = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
FROZEN_SHA = "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
spec = importlib.util.spec_from_file_location("prior_independent_review", OLD / "review/check.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    (WORK / "review" / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def block_text(block, latex_delimiters=False):
    return "".join(("$" + s["text"] + "$" if latex_delimiters and s["kind"] == "math" else s["text"] or "") for s in block["segments"])


def output_text(output, latex_delimiters=False):
    return "\n\n".join(block_text(block, latex_delimiters) for block in output["blocks"])


def schema_errors(output, size):
    errors = []
    if not isinstance(output, dict) or set(output) != {"blocks", "uncertainties"}:
        return ["root schema"]
    if not isinstance(output["uncertainties"], list) or not all(isinstance(x, str) for x in output["uncertainties"]):
        errors.append("uncertainties schema")
    if not isinstance(output["blocks"], list):
        return errors + ["blocks schema"]
    for i, block in enumerate(output["blocks"]):
        if set(block) != {"kind", "bbox", "segments", "code_language"} or block["kind"] not in {"paragraph", "heading", "code", "formula", "caption", "footnote", "list_item", "other"}:
            errors.append(f"block{i} schema")
        box = block.get("bbox", [])
        if len(box) != 4 or not all(type(v) in (int, float) for v in box):
            errors.append(f"block{i} bbox schema")
        elif not (0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1]):
            errors.append(f"block{i} bbox outside input")
        if block.get("code_language") is not None and not isinstance(block["code_language"], str):
            errors.append(f"block{i} code language schema")
        for j, segment in enumerate(block.get("segments", [])):
            if set(segment) != {"kind", "text"} or segment["kind"] not in {"text", "math", "code", "unknown"} or (segment["text"] is not None and not isinstance(segment["text"], str)):
                errors.append(f"block{i}/segment{j} schema")
            elif segment["kind"] != "unknown" and segment["text"] is None:
                errors.append(f"block{i}/segment{j} unexplained null")
    return errors


def frozen_inputs():
    manifest = read(WORK / "inputs/input-manifest.json")
    snapshot = read(WORK / "review/input-snapshot.json")
    prior_manifest = read(OLD / "inputs/input-manifest.json")
    assert digest(REGISTRY) == FROZEN_SHA
    assert digest(ROOT / manifest["prior_input_manifest_ref"]["path"]) == manifest["prior_input_manifest_ref"]["sha256"] == snapshot["prior_input_manifest"]["sha256"]
    known = {c["id"]: c for c in snapshot["candidates"]}
    known.update({p["id"]: p for p in snapshot["page_inputs"]})
    assert len(manifest["inputs"]) == 22
    assert len({r["id"] for r in manifest["inputs"]}) == 22
    for row in manifest["inputs"]:
        original = known[row["prior_input_id"]]
        assert row["image_path"] == original["image"]["path"]
        assert digest(ROOT / row["image_path"]) == row["image_sha256"] == original["image"]["sha256"]
        assert prior.png_size(ROOT / row["image_path"]) == row["image_pixels_wh"]
        assert digest(ROOT / row["source"]["pdf_path"]) == row["source"]["pdf_sha256"]
        assert digest(ROOT / row["baseline_document_ref"]["path"]) == row["baseline_document_ref"]["sha256"]
        if row["phase"] == "paragraph":
            candidate = next(c for c in prior_manifest["candidates"] if c["id"] == row["prior_input_id"])
            assert row["physical_pages_1based"] == [f["physical_page_1based"] for f in candidate["fragments"]]
            assert row["replacement_charspan"] == candidate["replacement_charspan"]
    return manifest


def method_system_prompt():
    tree = ast.parse((WORK / "api/run.py").read_text())
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(isinstance(t, ast.Attribute) and t.attr == "COMMON" for t in statement.targets):
            return ast.literal_eval(statement.value)
    raise AssertionError("runner system prompt absent")


def review_run(row, observations):
    folder = WORK / "api" / row["id"]
    if not (folder / "output.json").exists():
        return {"id": row["id"], "status": "pending"}, None
    request, response, output = (read(folder / name) for name in ("request-description.json", "response.json", "output.json"))
    choice = response["choices"][0]
    body = deepcopy(request["body_without_inline_image"])
    body["messages"][1]["content"][1]["image_url"]["url"] = "data:image/png;base64," + base64.b64encode((ROOT / row["image_path"]).read_bytes()).decode()
    body_bytes = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    observation = observations[row["id"]]
    checks = {"exact_input_png": digest(folder / "input.png") == row["image_sha256"] == request["input_sha256"],
        "actual_http_body_hash_reconstructs": sha256(body_bytes).hexdigest() == request["http_body_sha256"],
        "runner_hash_frozen": request["runner_sha256"] == digest(WORK / "api/run.py"),
        "generic_system_prompt_exact": body["messages"][0]["content"] == method_system_prompt(),
        "one_attempt_completed_without_refusal": observation["attempts"] == 1 and observation["http_status"] == 200 and choice["finish_reason"] == "stop" and not choice["message"].get("refusal"),
        "parsed_output_equals_raw_response_json": json.loads(choice["message"]["content"]) == output,
        "recorded_response_hash_matches": digest(folder / "response.json") == observation["response_sha256"],
        "requested_model_and_privacy": body["model"] == "gpt-6-luna" and body["store"] is False and body["reasoning_effort"] == "low" and "temperature" not in body,
        "declared_token_budget": body["max_completion_tokens"] == (4096 if row["phase"] == "paragraph" else 8192),
        "strict_schema": body["response_format"]["type"] == "json_schema" and body["response_format"]["json_schema"]["strict"] is True,
        "high_image_detail": body["messages"][1]["content"][1]["image_url"]["detail"] == "high"}
    assert all(checks.values()), (row["id"], checks)
    errors = schema_errors(output, row["image_pixels_wh"])
    return {"id": row["id"], "status": "completed", "checks": checks, "schema_errors": errors,
        "block_count": len(output["blocks"]), "segment_counts": {kind: sum(s["kind"] == kind for b in output["blocks"] for s in b["segments"]) for kind in ("text", "math", "code", "unknown")},
        "uncertainties": output["uncertainties"], "physical_pages": row["physical_pages_1based"],
        "returned_model": response.get("model"), "finish_reason": choice["finish_reason"], "usage": response.get("usage"),
        "round_trip_seconds": observation["client_round_trip_seconds"], "raw_response_sha256": digest(folder / "response.json"),
        "parsed_output_sha256": digest(folder / "output.json")}, output


def math_score(blocks, case, frozen):
    text = "\n\n".join(block_text(b, True) for b in blocks)
    score = prior.semantic_score(text, case, frozen)
    typed = " ".join(s["text"] or "" for b in blocks for s in b["segments"] if s["kind"] == "math")
    actual = prior.math_occurrences(typed, case)
    score["typed_math_occurrences"] = actual
    score["all_expected_math_typed_in_source_order"] = actual == score["expected_math_occurrences"]
    score["unknown_segments"] = sum(s["kind"] == "unknown" for b in blocks for s in b["segments"])
    score["source_block_count"] = len(blocks)
    score["ordered_segment_kinds"] = [[s["kind"] for s in b["segments"]] for b in blocks]
    score["raw_segment_texts"] = [[s["text"] for s in b["segments"]] for b in blocks]
    score["bounded_F13_delivery_pass"] = (score["math_occurrences_exact_meaning_and_order"] and score["all_expected_math_typed_in_source_order"] and score["prose_words_and_inline_positions_match"] and not score["unknown_segments"] and len(blocks) == 1)
    a, b = score["prose_expected_words"], score["prose_observed_words"]
    score["prose_word_differences"] = [{"change":op,"expected":a[i:j],"observed":b[k:l]} for op,i,j,k,l in SequenceMatcher(None,a,b).get_opcodes() if op != "equal"]
    return score


def anchored(output, prefix):
    return [block for block in output["blocks"] if block_text(block).startswith(prefix)]


def cases_review(outputs):
    cases = {c["id"]: c for c in read(REGISTRY)["cases"]}
    results = {}
    for case, paragraph, page, anchor in (("G1-E14", "wikiskill-texts-363", "wikiskill-p21", "We determine top-performing"), ("G1-E04", "dgm-texts-648", "dgm-p51", "For the same target functionality")):
        result = {}
        for phase, name in (("paragraph", paragraph), ("page", page)):
            key = phase + "--" + name
            if key not in outputs:
                continue
            blocks = outputs[key]["blocks"] if phase == "paragraph" else anchored(outputs[key], anchor)
            if case == "G1-E14":
                result[phase] = math_score(blocks, case, cases[case])
            else:
                result[phase] = prior.semantic_score("\n\n".join(block_text(b) for b in blocks), case, cases[case])
                result[phase]["typed_code_occurrences"] = [s["text"] for b in blocks for s in b["segments"] if s["kind"] == "code"]
                result[phase]["source_block_count"] = len(blocks)
                text = "\n\n".join(block_text(b) for b in blocks)
                reference = next(c["provider_text"] for c in read(OLD / "inputs/input-manifest.json")["candidates"] if c["id"] == paragraph)
                a,b = prior.prose_words(reference),prior.prose_words(text)
                result[phase]["prose_word_differences"] = [{"change":op,"expected":a[i:j],"observed":b[k:l]} for op,i,j,k,l in SequenceMatcher(None,a,b).get_opcodes() if op != "equal"]
                result[phase]["source_linewrap_hyphen_join_only_prose_match"] = prior.prose_words(re.sub(r"(?<=\w)-\n(?=\w)", "", text)) == a
                result[phase]["F14_code_tokens_bindings_numbers_pass"] = all(result[phase][k] for k in ("inline_code_order_correct", "node6_binding", "node24_binding", "printed_performances_preserved"))
        results[case] = result
    seal = {}
    if "paragraph--seal-texts-30" in outputs:
        seal["paragraph"] = math_score(outputs["paragraph--seal-texts-30"]["blocks"], "G1-E13", cases["G1-E13"])
    if all(f"page--seal-p{p}" in outputs for p in (3,4)):
        blocks = anchored(outputs["page--seal-p3"], "Let ") + anchored(outputs["page--seal-p4"], "associated answers about the passage.")
        seal["page_fragments_review_join_only"] = math_score(blocks, "G1-E13", cases["G1-E13"])
        seal["page_fragments_review_join_only"]["producer_logical_cross_page_join_demonstrated"] = False
    results["G1-E13"] = seal
    result = {}
    expected = cases["G1-C02"]["details"]["oracle"]
    if "page--controls-p1" in outputs:
        output = outputs["page--controls-p1"]
        codes = [b for b in output["blocks"] if b["kind"] == "code"]
        result["page"] = {"source_seven_line_code_exact": any(prior.source_code_exact(block_text(b), expected["code_lines"]) for b in codes),
            "code_languages": [b["code_language"] for b in codes],
            "inline_boundary_exact": expected["inline_code"] in output_text(output),
            "inline_code_fragment_exact": any(s["kind"] == "code" and s["text"] == expected["inline_code"].split("Inline code: ")[-1] for b in output["blocks"] for s in b["segments"]),
            "comment_occurrences": output_text(output).count(expected["code_lines"][0]),
            "raw_code_blocks": [block_text(b) for b in codes]}
    result["paragraph"] = {}
    inline_source = next(c["provider_text"] for c in read(OLD / "inputs/input-manifest.json")["candidates"] if c["id"] == "controls-texts-14")
    for number, lines in ((12, expected["code_lines"][:1]), (13, expected["code_lines"][1:]), (14, [inline_source])):
        key = f"paragraph--controls-texts-{number}"
        if key in outputs:
            result["paragraph"][str(number)] = {"source_text_exact": prior.source_code_exact(output_text(outputs[key]), lines), "output": outputs[key]}
    results["G1-C02"] = result
    regressions = {}
    for phase, key in (("paragraph", "paragraph--wikiskill-texts-362"), ("page", "page--wikiskill-p21")):
        if key in outputs:
            text = output_text(outputs[key])
            regressions[phase] = {"statistical_significance_label_present": "Statistical significance testing" in text,
                "source_opening_sentence_present": "We perform paired bootstrap significance tests" in text,
                "iteration_count_1000_present": bool(re.search(r"1\s*,\s*000", text))}
    results["wikiskill_362_omission_regression"] = regressions
    return results


def controls_math(outputs):
    def inline(text):
        return re.sub(r"\s+", "", prior.equivalent_surface(text)) == "y=x^2+1"
    def matrix(text):
        compact = re.sub(r"\s+", "", text)
        return {"values_rows_shape_negative_preserved": "1&-2\\\\3&4" in compact,
            "square_bracket_matrix_preserved": "\\begin{bmatrix}" in compact or ("\\left[" in compact and "\\right]" in compact),
            "raw_latex": text}
    def fraction(text):
        return {"complete_denominator_and_no_added_integral": bool(re.search(r"\\frac\s*\{\s*1\s*\}\s*\{\s*x\s*\+\s*1\s*\}", text)) and r"\int" not in text, "raw_latex": text}
    def piecewise(text):
        return {"two_cases_with_correct_values_and_boundary": r"\begin{cases}" in text and r"\end{cases}" in text and text.count("\\\\") == 1 and bool(re.search(r"x\s*\^\s*(?:\{\s*)?2",text)) and bool(re.search(r"x\s*(?:\\geq?|>=|≥)\s*0",text)) and bool(re.search(r"x\s*<\s*0",text)) and text.count("f(") == 1, "raw_latex": text}
    result = {"frozen_case": "G1-C01", "page": {}, "paragraph": {},
        "matrix_crop_input_limitation": "Independent visual review: provider crop clips square-bracket ends and entire right bracket; only a left vertical stroke and four entries remain visible. Original source reconstruction fails, with producer-crop attribution; not a pure model comparison.",
        "segmentation_or_formatting_not_substituted_for_semantic_score": True}
    if "page--controls-p1" in outputs:
        output = outputs["page--controls-p1"]
        formulas = [block_text(b) for b in output["blocks"] if b["kind"] == "formula"]
        inline_blocks = [b for b in output["blocks"] if block_text(b).startswith("Let ")]
        result["page"] = {"inline_exponent": any(inline(s["text"] or "") for b in inline_blocks for s in b["segments"] if s["kind"] == "math"),
            "matrix": matrix(formulas[0]), "fraction": fraction(formulas[1]), "piecewise": piecewise(formulas[2])}
    for number, function in ((4,inline),(6,matrix),(8,fraction),(10,piecewise)):
        key = f"paragraph--controls-texts-{number}"
        if key in outputs:
            math = " ".join(s["text"] or "" for b in outputs[key]["blocks"] for s in b["segments"] if s["kind"] == "math")
            result["paragraph"][str(number)] = function(math)
    return result


def expected_markup(segment, block_kind):
    text, kind = segment["text"], segment["kind"]
    if text is None or kind == "unknown":
        return "[unknown source span]"
    if block_kind in ("code", "formula"):
        return text
    if kind == "text":
        return re.sub(r"([\\`*_{}\[\]])", r"\\\1", escape(text, quote=False))
    if kind == "math":
        return "$" + text + "$"
    fence = "`" * max(1,max((len(v) for v in re.findall(r"`+",text)),default=0)+1)
    pad = " " if text.startswith(("`"," ")) or text.endswith(("`"," ")) else ""
    return fence+pad+text+pad+fence


def parsed_review(manifest, outputs):
    results = []
    for row in manifest["inputs"]:
        key = row["id"]
        folder = WORK / "parsed" / key
        mapped, original = read(folder / "render-map.json"), read(folder / "original-blocks.json")
        markdown = (folder / "document.md").read_text()
        assert original == outputs[key]
        assert mapped["input_source_metadata"] == row
        assert mapped["api_output_sha256"] == digest(WORK / "api" / key / "output.json")
        assert mapped["document_markdown_sha256"] == digest(folder / "document.md")
        rebuilt = []
        for block, rendered in zip(original["blocks"],mapped["blocks"],strict=True):
            assert rendered["model_bbox_image_pixels"] == block["bbox"]
            pieces = []
            for segment, recorded in zip(block["segments"],rendered["segments"],strict=True):
                assert recorded["raw_text"] == segment["text"] and recorded["kind"] == segment["kind"]
                expected = expected_markup(segment,block["kind"])
                assert expected == recorded["rendered_markup"]
                left,right = recorded["markdown_charspan"]
                assert markdown[left:right] == expected
                pieces.append(expected)
            content = "".join(pieces)
            if block["kind"] == "code":
                fence = "`" * max(3,max((len(v) for v in re.findall(r"`+",content)),default=0)+1)
                content = fence+(block["code_language"] or "")+"\n"+content+("" if content.endswith("\n") else "\n")+fence
            elif block["kind"] == "formula":
                content = "$$\n"+content+"\n$$"
            else:
                content = ("## " if block["kind"] == "heading" else "- " if block["kind"] == "list_item" else "")+content
            left,right = rendered["markdown_charspan"]
            assert markdown[left:right] == content
            rebuilt.append(content)
        assert "\n\n".join(rebuilt) == markdown
        results.append({"id":key,"blocks":len(rebuilt),"raw_output_equals_saved_original_blocks":True,"all_segments_and_entire_markdown_reconstructed":True})
    return {"documents_checked":len(results),"records":results,"semantic_repair_performed":False}


def reinsertion_review():
    old_manifest = read(OLD / "inputs/input-manifest.json")
    candidates = {c["id"]:c for c in old_manifest["candidates"]}
    plan = read(WORK / "reinsertion/plan.json")
    assert len(plan["rows"]) == len(candidates) == 17
    assert plan["api_input_manifest_sha256"] == digest(WORK / "inputs/input-manifest.json")
    documents, count, all_errors = [],0,[]
    for source in old_manifest["sources"]:
        folder = WORK / "reinsertion" / source["name"]
        native = read(ROOT / source["document_path"])
        structure = read(folder / "inline-structure.json")
        rows = [r for r in plan["rows"] if r["source"] == source["name"]]
        proposals = structure["candidates"]
        assert digest(ROOT / source["document_path"]) == source["document_sha256"]
        errors = prior.proposal_errors(native,rows,proposals,candidates)
        errors += prior.audit_markdown((folder / "baseline.md").read_text(),(folder / "candidate.md").read_text(),rows,proposals)
        assert (folder / "baseline.md").read_bytes() == (OLD / "reinsertion/token-aware" / source["name"] / "baseline.md").read_bytes()
        assert {p["candidate_id"] for p in proposals} == {r["candidate_id"] for r in rows}
        for p in proposals:
            assert read(ROOT / p["api_output_ref"]["path"]) == p["original_model_blocks"]
            assert digest(ROOT / p["api_output_ref"]["path"]) == p["api_output_ref"]["sha256"]
            assert read(ROOT / p["original_model_blocks_ref"]["path"]) == p["original_model_blocks"]
            for n in p["neighbors"]:
                assert n["before_sha256"] == n["after_sha256"] == prior.canonical(prior.resolve(native,n["item_ref"]))
            if p["status"] != "not_applied":
                assert p["model_markdown"] == p["markdown"]
                md = (folder / "candidate.md").read_text()
                for segment in p["main_markdown_segment_offsets"]:
                    left,right = segment["main_markdown_charspan"]
                    assert md[left:right] == segment["rendered_markup"]
        accepted = sum(p["status"] != "not_applied" for p in proposals)
        count += accepted
        documents.append({"source":source["name"],"applied":accepted,"errors":errors,
            "outcomes":[{"id":p["candidate_id"],"status":p["status"],"reason":p.get("reason"),"physical_pages":[f["physical_page_1based"] for f in p["source_association"]]} for p in proposals]})
        all_errors += errors
    assert not all_errors,all_errors
    return {"structurally_applied":count,"abstained":17-count,"documents":documents,"errors":all_errors,
        "native_json_bytes_refs_order_graph_and_provenance_preserved":True,
        "all_outside_markdown_exact_except_declared_whole_item_substitutions":True,
        "structural_application_is_semantic_approval":False,
        "controls12_and14": "Faithful model text, but native CodeItem roles disagree with model paragraph roles; abstention is an adapter/provider-role limitation, not content failure.",
        "accepted_seal32_semantic_failure": "Wrong L_{M_{theta'}} model identity/subscript plus stray prose closing brace survive the guards and final substitution."}


def geometry_review(manifest, outputs):
    old_candidates = {c["id"]:c for c in read(OLD / "inputs/input-manifest.json")["candidates"]}
    records = []
    for row in manifest["inputs"]:
        mapped = []
        for i,block in enumerate(outputs[row["id"]]["blocks"]):
            box = block["bbox"]
            fragments = []
            if row["phase"] == "page":
                fragments = [(row["physical_pages_1based"][0],box,row["input_pixels_to_source_top_left_points_3x3"])]
            else:
                for f in old_candidates[row["prior_input_id"]]["fragments"]:
                    x,y,w,h = f["paragraph_canvas_xywh"]
                    clipped = [max(box[0],x),max(box[1],y),min(box[2],x+w),min(box[3],y+h)]
                    if clipped[0] < clipped[2] and clipped[1] < clipped[3]:
                        fragments.append((f["physical_page_1based"],clipped,f["paragraph_pixels_to_source_top_left_points_3x3"]))
            for page,clip,matrix in fragments:
                l,t,r,b = clip
                mapped.append({"block_index":i,"physical_page_1based":page,"polygon_top_left_pdf_points":[prior.point(matrix,x,y) for x,y in ((l,t),(r,t),(r,b),(l,b))]})
        records.append({"id":row["id"],"mapped_block_fragments":mapped})
    return {"scope":"Reviewer-computed geometry associations, not new producer output or measured token alignment.","records":records,
        "precision":"Original producer fragment/page transforms plus model block bounds. Each segment has an inferred output span only; no per-word source boxes.",
        "seal30_whole_block_intersects_both_physical_pages": [m["physical_page_1based"] for r in records if r["id"] == "paragraph--seal-texts-30" for m in r["mapped_block_fragments"]],
        "per_segment_semantic_fragment_alignment_demonstrated":False}


def selected_regressions(outputs):
    seal32 = outputs["paragraph--seal-texts-32"]
    return {"seal32": {"source_review_basis":"Independent visual review of unchanged producer paragraph PNG; original model name is LM with theta-prime subscript.",
        "observed_math_segments":[s["text"] for b in seal32["blocks"] for s in b["segments"] if s["kind"] == "math"],
        "model_name_and_subscript_faithful":False,"stray_prose_closing_brace":any("}" in (s["text"] or "") for b in seal32["blocks"] for s in b["segments"] if s["kind"] == "text"),
        "structurally_applied":True,"not_a_new_frozen_math_denominator":True},
        "seal34": {"source_review_basis":"Independent visual review of unchanged stitched producer PNG: paragraph stops at self-edits, then actual Algorithm1 caption is visible.",
            "observed_block_kinds":[b["kind"] for b in outputs["paragraph--seal-texts-34"]["blocks"]],
            "caption_was_visible_in_input_not_hallucinated":True,"provider_item_crop_is_not_pure_complete_paragraph":True,"safe_multi_root_abstention":True},
        "matrix_crop": {"visible_source_limitation":"Horizontal square-bracket ends and whole right bracket clipped by provider crop.","original_source_matrix_reconstruction_fails":True,"attribution_includes_producer_boundary":True}}


def selfcheck():
    cases = {c["id"]: c for c in read(REGISTRY)["cases"]}
    reference = cases["G1-E14"]["details"]["expected"]["reference_paragraph_with_inline_latex"]
    seal = cases["G1-E13"]["details"]["expected"]["reference_paragraph_with_inline_latex"]
    assert prior.semantic_score(reference, "G1-E14", cases["G1-E14"])["math_occurrences_exact_meaning_and_order"]
    assert prior.semantic_score(seal, "G1-E13", cases["G1-E13"])["math_occurrences_exact_meaning_and_order"]
    controls = {"threshold_strictness": not prior.semantic_score(reference.replace("p<0.05", "p\\ge0.05"), "G1-E14", cases["G1-E14"])["math_occurrences_exact_meaning_and_order"],
        "update_arrow": not prior.semantic_score(seal.replace(r"\leftarrow", r"\rightarrow"), "G1-E13", cases["G1-E13"])["math_occurrences_exact_meaning_and_order"],
        "update_prime": not prior.semantic_score(seal.replace(r"\theta'", r"\theta"), "G1-E13", cases["G1-E13"])["math_occurrences_exact_meaning_and_order"],
        "model_subscript": not prior.semantic_score(seal.replace(r"_{\theta}", r"\theta", 1), "G1-E13", cases["G1-E13"])["math_occurrences_exact_meaning_and_order"],
        "duplicated_cross_page_fragment": not prior.semantic_score(seal + " Given C.", "G1-E13", cases["G1-E13"])["math_occurrences_exact_meaning_and_order"],
        "dropped_critical_prose": not prior.semantic_score(reference.replace("over all competing methods", "over competing methods"), "G1-E14", cases["G1-E14"])["prose_words_and_inline_positions_match"]}
    code = cases["G1-C02"]["details"]["oracle"]["code_lines"]
    controls["code_boundary"] = not prior.source_code_exact("\n".join(code).replace("x <= limit", "x < limit"), code)
    controls["code_nesting"] = not prior.source_code_exact("\n".join(code).replace('        emit("ok")', '    emit("ok")'), code)
    example = {"blocks": [{"kind": "paragraph", "bbox": [1,2,50,10], "segments": [{"kind": "text", "text": "text"}], "code_language": None}], "uncertainties": []}
    assert not schema_errors(example, [100,100])
    bad = deepcopy(example); bad["blocks"][0]["bbox"][2] = 101
    controls["out_of_image_bbox"] = bool(schema_errors(bad,[100,100]))
    bad = deepcopy(example); bad["blocks"][0]["segments"][0]["text"] = None
    controls["unexplained_null_text"] = bool(schema_errors(bad,[100,100]))
    parts = re.split(r"(\$[^$]+\$)",reference)
    good = {"kind":"paragraph","bbox":[0,0,100,100],"code_language":None,"segments":[{"kind":"math" if t.startswith("$") else "text","text":t[1:-1] if t.startswith("$") else t} for t in parts if t]}
    assert math_score([good],"G1-E14",cases["G1-E14"])["bounded_F13_delivery_pass"]
    bad = deepcopy(good)
    next(s for s in bad["segments"] if s["kind"] == "math")["kind"] = "text"
    controls["math_left_in_plain_text"] = not math_score([bad],"G1-E14",cases["G1-E14"])["bounded_F13_delivery_pass"]
    manifest = read(OLD / "inputs/input-manifest.json")
    candidates = {c["id"]:c for c in manifest["candidates"]}
    plan = read(WORK / "reinsertion/plan.json")
    rows = [r for r in plan["rows"] if r["source"] == "wikiskill"]
    document = read(ROOT / rows[0]["document_path"])
    folder = WORK / "reinsertion/wikiskill"
    proposals = read(folder / "inline-structure.json")["candidates"]
    for name in ("wrong_physical_page","missing_fragment","stale_hash","partial_item","duplicate_item","native_order","native_parent","source_geometry"):
        ds,ps = deepcopy(document),deepcopy(proposals)
        if name == "wrong_physical_page":ps[0]["source_association"][0]["physical_page_1based"] = 1
        if name == "missing_fragment":ps[0]["source_association"] = []
        if name == "stale_hash":ps[0]["provider_text_sha256"] = "bad"
        if name == "partial_item":ps[0]["replacement_charspan"][0] = 1
        if name == "duplicate_item":ps.append(deepcopy(ps[0]))
        if name == "native_order":ds["texts"][0],ds["texts"][1] = ds["texts"][1],ds["texts"][0]
        if name == "native_parent":ds["texts"][0]["parent"] = {"$ref":"#/texts/999"}
        if name == "source_geometry":ps[0]["source_association"][0]["provider_provenance"]["bbox"]["l"] += 10
        controls[name] = bool(prior.proposal_errors(ds,rows,ps,candidates))
    baseline,candidate = (folder / "baseline.md").read_text(),(folder / "candidate.md").read_text()
    controls["dropped_outside_markdown"] = bool(prior.audit_markdown(baseline,candidate[1:],rows,proposals))
    bad = deepcopy(proposals)
    bad[0]["main_markdown_charspan"],bad[1]["main_markdown_charspan"] = bad[1]["main_markdown_charspan"],bad[0]["main_markdown_charspan"]
    controls["swapped_output_order"] = bool(prior.audit_markdown(baseline,candidate,rows,bad))
    dgm = candidates["dgm-texts-648"]["provider_text"]
    controls["changed_code_identifier"] = not prior.semantic_score(dgm.replace("str_replace","str_replace_all"),"G1-E04",cases["G1-E04"])["inline_code_order_correct"]
    assert all(controls.values()), controls
    return {"all_rejected": True, "controls": controls, "scope": "In-memory only; no API calls or payload/oracle changes."}


def main():
    manifest = frozen_inputs()
    observations_path = WORK / "api/observations.json"
    observations = {row["name"]: row for row in read(observations_path)} if observations_path.exists() else {}
    runs, outputs = [], {}
    for row in manifest["inputs"]:
        result, output = review_run(row, observations)
        runs.append(result)
        if output is not None:
            outputs[row["id"]] = output
    result = {"format": "g2-inline-api-independent-review-v1", "frozen_cases_sha256": digest(REGISTRY),
        "input_manifest_sha256": digest(WORK / "inputs/input-manifest.json"), "checker_sha256": digest(__file__),
        "prior_semantic_checker_sha256": digest(OLD / "review/check.py"), "expected_runs": 22,
        "completed_runs": len(outputs), "all_outputs_present": len(outputs) == 22, "runs": runs,
        "frozen_case_semantics": cases_review(outputs), "C01_math_regression": controls_math(outputs), "selfchecks": selfcheck(),
        "review_scope": "Saved direct-API component outputs; no official pipeline claim, inference, credentials or prior-file writes."}
    if len(outputs) == 22:
        result.update(parsed=parsed_review(manifest,outputs),reinsertion=reinsertion_review(),geometry=geometry_review(manifest,outputs),selected_item_regressions=selected_regressions(outputs))
    save("output-review.json", result)
    print(json.dumps({"completed": len(outputs), "pending": 22-len(outputs), "selfchecks": len(result["selfchecks"]["controls"]), "schema_errors": {r["id"]:r.get("schema_errors") for r in runs if r.get("schema_errors")}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
