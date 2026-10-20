"""Independent inline saved-artifact checks; no inference or candidate repair."""

from hashlib import sha256
from copy import deepcopy
from html import escape
import json
from math import ceil, floor
from pathlib import Path
import re
import struct
import unicodedata


ROOT = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
FROZEN_SHA = "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
FROZEN_CANDIDATES = {
    "G1-E14": ["wikiskill-texts-363"],
    "G1-E04": ["dgm-texts-648"],
    "G1-E13": ["seal-texts-30"],
    "G1-C02": ["controls-texts-12", "controls-texts-13", "controls-texts-14"],
}


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def png_size(path):
    data = Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return list(struct.unpack(">II", data[16:24]))


def gate(text):
    return sorted({c for c in text if unicodedata.category(c) == "Sm" or
        0x0370 <= ord(c) <= 0x03FF or 0x1D400 <= ord(c) <= 0x1D7FF or c in "_=<>^{}"})


def point(matrix, x, y):
    v = [sum(matrix[r][c] * (x, y, 1)[c] for c in range(3)) for r in range(3)]
    return [v[0] / v[2], v[1] / v[2]]


def equivalent_surface(text):
    """Declared mathematical spelling equivalences; never weakens an operator."""
    text = unicodedata.normalize("NFKC", text).replace("∗", "*").replace("⋆", "*").replace("′", "'")
    for macro, value in [(r"\geqslant", "≥"), (r"\geq", "≥"), (r"\ge", "≥"),
                         (r"\leqslant", "≤"), (r"\leq", "≤"), (r"\le", "≤"),
                         (r"\leftarrow", "←"), (r"\gets", "←"), (r"\theta", "θ"),
                         (r"\tau", "τ"), (r"\prime", "'"), (r"\star", "*"), (r"\ast", "*")]:
        text = re.sub(re.escape(macro) + r"(?![A-Za-z])", lambda _: value, text)
    text = re.sub(r"\\(?:mathrm|operatorname|texttt|mathit|text)\s*\{([^{}]*)\}", r"\1", text)
    text = text.translate(str.maketrans({"$": "", "{": "", "}": ""})).replace(">=", "≥").replace("<=", "≤")
    return text


E14_PATTERN = re.compile(r"M\s*(?:\^\s*)?\*|p\s*(?:[<>≤≥])\s*\d+(?:\s*\.\s*\d+)?")
E13_PATTERN = re.compile(r"θ\s*'\s*←\s*SFT\s*\(\s*θ\s*,\s*SE\s*\)|LM\s*_\s*θ|\(\s*C\s*,\s*τ\s*\)|θ\s*'|θ|τ|\bC\b")


def math_occurrences(text, case):
    pattern = E14_PATTERN if case == "G1-E14" else E13_PATTERN
    surface = equivalent_surface(text)
    return [re.sub(r"\s+", "", match[0]).replace("M^*", "M*") for match in pattern.finditer(surface)]


def prose_words(text, case=None):
    text = equivalent_surface(text).replace("’", "'")
    if case in ("G1-E14", "G1-E13"):
        text = (E14_PATTERN if case == "G1-E14" else E13_PATTERN).sub(" INLINE_MATH ", text)
    return re.findall(r"[A-Za-z_]+(?:['-][A-Za-z_]+)*|\d+(?:\.\d+)?%?", text)


def semantic_score(text, case, frozen):
    expected = frozen["details"].get("expected", frozen["details"].get("oracle"))
    if case in ("G1-E14", "G1-E13"):
        wanted = expected["ordered_inline_math_spans"]
        wanted = [s["latex"] if isinstance(s, dict) else s for s in wanted]
        wanted = [re.sub(r"\s+", "", equivalent_surface(s)).replace("M^*", "M*") for s in wanted]
        actual = math_occurrences(text, case)
        expected_words = prose_words(expected["reference_paragraph_with_inline_latex"], case)
        actual_words = prose_words(text, case)
        result = {"expected_math_occurrences": wanted, "observed_math_occurrences": actual,
            "math_occurrence_count": len(actual), "fixed_expected_math_count": expected["closed_math_span_denominator"],
            "math_occurrences_exact_meaning_and_order": actual == wanted,
            "prose_words_and_inline_positions_match": actual_words == expected_words,
            "prose_expected_words": expected_words, "prose_observed_words": actual_words,
            "actual_inline_latex_fragments": re.findall(r"\$(.+?)\$", text, re.S)}
        if case == "G1-E14":
            result["critical_prose_conditions"] = {phrase: phrase in " ".join(text.split()) for phrase in
                ("if and only if", "over all competing methods", "not statistically distinguishable",
                 "one or more lower-ranked methods", "no single method is declared the sole top performer",
                 "grouped into a top-tier statistical tie")}
        else:
            result["page_join_occurrences"] = text.count("questions and associated answers about the passage.")
            result["p4_fragment_start_occurrences"] = text.count("associated answers about the passage.")
            result["next_paragraph_absent"] = "We optimize the self-edit generation process" not in text
        return result
    if case == "G1-E04":
        reference = next(c["provider_text"] for c in read(WORK / "inputs/input-manifest.json")["candidates"] if c["id"] == "dgm-texts-648")
        actual = re.findall(r"\b(?:edit_type|edit_actions|str_replace|edit)\b", text)
        return {"expected_inline_code_occurrences": expected["inline_tokens_in_reading_order"],
            "observed_inline_code_occurrences": actual, "inline_code_order_correct": actual == expected["inline_tokens_in_reading_order"],
            "complete_source_reviewed_prose_words_match": prose_words(text) == prose_words(reference),
            "prose_reference_basis": "Native baseline paragraph independently visually checked against full source crop; not a new frozen line denominator.",
            "node6_binding": bool(re.search(r"node 6 retained the original edit command and added the parameters edit_type and edit_actions", text)),
            "node24_binding": bool(re.search(r"node 24 replaced the original edit command with a new str_replace command", text)),
            "printed_performances_preserved": "23.3%" in text and "40.5%" in text,
            "inline_code_backtick_occurrences": re.findall(r"`([^`\n]+)`", text),
            "inline_typing_absence_is_delivery_observation_not_F14_failure": True}
    raise AssertionError(case)


def source_code_exact(text, lines):
    return text.splitlines() == lines


def model_run(path):
    generation = read(path / "generation.json")
    decoder = read(path / "decoder-before-rstrip.json")
    before_strip = decoder["texts"][0]
    engine = (path / "engine-output.txt").read_text()
    token = (path / "token-aware-decode.txt").read_text()
    unclean = (path / "unclean-decode.txt").read_text()
    terminal = generation["removed_terminal_special_ids"]
    exact_terminal = unclean
    for _ in terminal:
        exact_terminal = exact_terminal.removesuffix(generation["pad_token"])
    primary_path = path / "document.json" if "/page/" in str(path) else path / "official-parser-component/document.json"
    primary = read(primary_path)
    candidate = read(path / "token-aware-parser-candidate/document.json")
    return {"path": str(path.relative_to(ROOT)),
        "artifact_sha256": {f: digest(path / f) for f in ("source-input.json", "generation.json", "engine-output.txt", "token-aware-decode.txt", "decoder-before-rstrip.json")},
        "generated_tokens": generation["generated_tokens"], "actual_cap": generation["actual_received_max_new_tokens"],
        "ended_eos": generation["last_token_is_eos"], "at_limit": generation["at_token_limit"],
        "generated_ids_match_prefix_split": generation["full_sequence_ids"][generation["input_tokens"]:] == generation["generated_ids"],
        "terminal_id_is_recorded_eos": generation["generated_ids"][-1] in ([generation["eos_token_ids"]] if isinstance(generation["eos_token_ids"], int) else generation["eos_token_ids"]),
        "image_input_cpu_fp32": generation["input_tensors"]["pixel_values"]["device"] == "cpu" and generation["input_tensors"]["pixel_values"]["dtype"] == "torch.float32",
        "engine_rstrip_reproduced_exactly": before_strip.rstrip(generation["pad_token"]) == engine,
        "token_aware_decode_removes_only_terminal_specials": exact_terminal == token,
        "raw_full_closing_doctag": token.endswith("</doctag>"),
        "engine_closing_doctag_damaged": token.endswith("</doctag>") and engine.endswith("</doctag"),
        "engine_and_token_parser_documents_equal": primary == candidate,
        "primary_parser_page_numbers": list(primary["pages"]),
        "primary_items": [{k: t[k] for k in ("self_ref", "label", "text", "prov")} for t in primary["texts"]],
        "token_parser_items": [{k: t[k] for k in ("self_ref", "label", "text", "prov")} for t in candidate["texts"]]}


def case_outputs(cases):
    base = WORK / "vlm"
    output = {}
    selectors = {"G1-E14": ("wikiskill-p21", "We determine top-performing"),
                 "G1-E04": ("dgm-p51", "For the same target functionality")}
    for case, (page_name, anchor) in selectors.items():
        page_doc = read(base / "page/runs" / page_name / "document.json")
        page_items = [t for t in page_doc["texts"] if t["text"].startswith(anchor)]
        para_doc = read(base / "paragraph/runs" / FROZEN_CANDIDATES[case][0] / "official-parser-component/document.json")
        para_text = "\n\n".join(t["text"] for t in para_doc["texts"])
        output[case] = {"page": {"matching_target_items": len(page_items), "score": semantic_score("\n\n".join(t["text"] for t in page_items), case, cases[case])},
                        "paragraph": {"item_count": len(para_doc["texts"]), "score": semantic_score(para_text, case, cases[case])}}
        for mode in ("page", "paragraph"):
            score = output[case][mode]["score"]
            if case == "G1-E04":
                score["F14_bounded_token_binding_prose_fidelity_pass"] = all(score[k] for k in ("inline_code_order_correct", "complete_source_reviewed_prose_words_match", "node6_binding", "node24_binding", "printed_performances_preserved"))
            else:
                score["F13_all_six_inline_latex_delivered"] = False
    page_items = []
    for page, anchor in ((3, "Let θ denote"), (4, "associated answers about the passage.")):
        doc = read(base / f"page/runs/seal-p{page}/document.json")
        page_items.extend(t for t in doc["texts"] if t["text"].startswith(anchor))
    para = read(base / "paragraph/runs/seal-texts-30/official-parser-component/document.json")
    output["G1-E13"] = {"page_fragments_review_join_only": {"fragment_count": len(page_items),
        "pipeline_logical_cross_page_join_present": False,
        "score": semantic_score(" ".join(t["text"] for t in page_items), "G1-E13", cases["G1-E13"])},
        "paragraph": {"item_count": len(para["texts"]), "score": semantic_score("\n\n".join(t["text"] for t in para["texts"]), "G1-E13", cases["G1-E13"])}}
    expected = cases["G1-C02"]["details"]["oracle"]
    page = read(base / "page/runs/controls-p1/document.json")
    block = next(t for t in page["texts"] if t["label"] == "code")
    comment = read(base / "paragraph/runs/controls-texts-12/official-parser-component/document.json")
    code = read(base / "paragraph/runs/controls-texts-13/official-parser-component/document.json")
    inline = read(base / "paragraph/runs/controls-texts-14/official-parser-component/document.json")
    output["G1-C02"] = {"page": {"seven_line_code_exact": source_code_exact(block["text"], expected["code_lines"]),
        "code_language": block.get("code_language"), "inline_boundary_exact": any(expected["inline_code"] in t["text"] for t in page["texts"]),
        "comment_occurrences": sum(t["text"].count(expected["code_lines"][0]) for t in page["texts"])},
        "paragraph": {"comment_exact_once": [t["text"] for t in comment["texts"]] == [expected["code_lines"][0]],
            "six_statement_lines_exact": [t["text"] for t in code["texts"]] == ["\n".join(expected["code_lines"][1:])],
            "code_language": code["texts"][0].get("code_language"), "inline_boundary_exact": any(expected["inline_code"] in t["text"] for t in inline["texts"]),
            "inline_items": [t["text"] for t in inline["texts"]]}}
    return output


def canonical(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def resolve(document, ref):
    collection, index = ref[2:].split("/")
    return document[collection][int(index)]


def proposal_errors(document, rows, proposals, candidates):
    errors, seen = [], set()
    indexed = {r["candidate_id"]: r for r in rows}
    for proposal in proposals:
        key = proposal["candidate_id"]
        if key in seen:
            errors.append("duplicate candidate")
        seen.add(key)
        if key not in indexed:
            errors.append("unknown candidate")
            continue
        row, candidate = indexed[key], candidates[key]
        item = resolve(document, row["item_ref"])
        if proposal["item_ref"] != row["item_ref"] or canonical(document) != row["canonical_document_sha256"]:
            errors.append("reference/document/order mismatch")
        if canonical(item) != row["item_sha256"] or proposal["provider_text_sha256"] != sha256(item["text"].encode()).hexdigest():
            errors.append("native item/hash mismatch")
        if proposal["replacement_charspan"] != [0, len(item["text"])]:
            errors.append("partial replacement")
        if proposal["source_association"] != candidate["fragments"]:
            errors.append("source page/geometry/fragment mismatch")
        if any(resolve(document, n["item_ref"]) != n["item"] or canonical(n["item"]) != n["item_sha256"] for n in row["neighbors"]):
            errors.append("changed neighbor")
    return errors


def original_markdown(row):
    item = row["provider_item"]
    if item["label"] == "code":
        return "```\n" + item["text"] + "\n```"
    return escape(item["text"], quote=False).replace("_", r"\_")


def audit_markdown(baseline, candidate, rows, proposals):
    """Rebuild every accepted substitution independently in exact saved Markdown."""
    errors, replacements = [], []
    by_id = {row["candidate_id"]: row for row in rows}
    for proposal in proposals:
        if proposal["status"] == "not_applied":
            if proposal["main_markdown_charspan"] is not None:
                errors.append("abstained item has output range")
            continue
        original = original_markdown(by_id[proposal["candidate_id"]])
        if baseline.count(original) != 1:
            errors.append("nonunique/missing original block")
            continue
        replacements.append((baseline.index(original), original, proposal))
    rebuilt, cursor, last_stop = "", 0, 0
    for start, original, proposal in sorted(replacements):
        if start < last_stop:
            errors.append("overlapping/out-of-order replacement")
        rebuilt += baseline[cursor:start]
        offset = len(rebuilt)
        rebuilt += proposal["markdown"]
        if proposal["main_markdown_charspan"] != [offset, len(rebuilt)]:
            errors.append("wrong main output range/order")
        cursor = last_stop = start + len(original)
    rebuilt += baseline[cursor:]
    if rebuilt != candidate:
        errors.append("changed/dropped/duplicated content outside exact replacements")
    return errors


def reinsertion_review():
    manifest, plan = read(WORK / "inputs/input-manifest.json"), read(WORK / "reinsertion/plan.json")
    candidates = {c["id"]: c for c in manifest["candidates"]}
    assert plan["input_manifest_sha256"] == digest(WORK / "inputs/input-manifest.json")
    assert len(plan["rows"]) == len(candidates) == len({r["candidate_id"] for r in plan["rows"]})
    result = {"variants": {}, "plan_sha256": digest(WORK / "reinsertion/plan.json"), "errors": []}
    for variant in ("component", "token-aware"):
        details, applied = [], 0
        for source in manifest["sources"]:
            folder = WORK / "reinsertion" / variant / source["name"]
            structure, document = read(folder / "inline-structure.json"), read(ROOT / source["document_path"])
            rows = [r for r in plan["rows"] if r["source"] == source["name"]]
            proposals = structure["candidates"]
            errors = proposal_errors(document, rows, proposals, candidates)
            errors += audit_markdown((folder / "baseline.md").read_text(), (folder / "candidate.md").read_text(), rows, proposals)
            assert digest(ROOT / source["document_path"]) == source["document_sha256"]
            assert {p["candidate_id"] for p in proposals} == {r["candidate_id"] for r in rows}
            for p in proposals:
                assert digest(ROOT / p["raw_output_path"]) == p["raw_output_sha256"]
                parsed = read(ROOT / p["parsed_document_path"])
                assert digest(ROOT / p["parsed_document_path"]) == p["parsed_document_sha256"]
                assert p["parsed_structure"] == parsed["texts"]
                assert all(n["before_sha256"] == n["after_sha256"] == canonical(resolve(document, n["item_ref"])) for n in p["neighbor_checks"])
                for span in p.get("inline_spans", []):
                    a, b = span["markdown_charspan"]
                    assert p["markdown"][a:b] == span["raw_markup"]
            count = sum(p["status"] != "not_applied" for p in proposals)
            applied += count
            details.append({"source": source["name"], "applied": count, "errors": errors,
                "outcomes": [{"id": p["candidate_id"], "status": p["status"], "reason": p.get("reason"),
                    "explicit_inline_span_count": len(p.get("inline_spans", [])), "physical_pages": [f["physical_page_1based"] for f in p["source_association"]]} for p in proposals]})
            result["errors"] += errors
        result["variants"][variant] = {"structurally_applied": applied, "abstained": len(candidates) - applied, "documents": details}
    result["provider_json_objects_rewritten"] = False
    result["native_preservation_basis"] = "All original file hashes, full native objects/refs/order/provenance/neighbor hashes; exact Markdown reconstruction permits only accepted complete-item substitutions."
    result["semantic_acceptance_implied_by_structural_application"] = False
    result["applied_wikiskill_362_drops_source_opening"] = not ("We perform paired bootstrap significance tests" in (WORK / "reinsertion/token-aware/wikiskill/candidate.md").read_text())
    return result


def geometry_review():
    records, errors = [], []
    for path in sorted((WORK / "vlm").glob("*/runs/*/**/source-mapped-geometry.json")):
        mapped = read(path)
        document = read(path.parent / "document.json")
        run = path.parent if (path.parent / "source-mapping.json").exists() else path.parent.parent
        page_job = "/page/" in str(path)
        source = read(run / "source-mapping.json") if page_job else read(run / "source-input.json")
        count = 0
        for item in mapped["items"]:
            prov = item["parser_provenance"]
            if prov not in resolve(document, item["item_ref"])["prov"]:
                errors.append("parser provenance mismatch: " + str(path))
            l, t, r, b = item["parser_bbox_top_left_pixels"]
            expected = []
            if page_job:
                w, h = source["pipeline_page_image_pixels_wh"]
                size = source["source_page_size_points"]
                expected = [(source["original_physical_page_1based"], [l, t, r, b], [[size["width"]/w,0,0],[0,size["height"]/h,0],[0,0,1]])]
            else:
                for frag in source["fragments"]:
                    x, y, w, h = frag["paragraph_canvas_xywh"]
                    overlap = [max(l, x), max(t, y), min(r, x+w), min(b, y+h)]
                    if overlap[0] < overlap[2] and overlap[1] < overlap[3]:
                        expected.append((frag["physical_page_1based"], overlap, frag["paragraph_pixels_to_source_top_left_points_3x3"]))
            if len(expected) != len(item["source_fragments"]):
                errors.append("fragment count mismatch: " + str(path))
            for (page, box, matrix), actual in zip(expected, item["source_fragments"]):
                a, b0, c, d = box
                polygon = [point(matrix,x,y) for x,y in [(a,b0),(c,b0),(c,d),(a,d)]]
                if actual["original_physical_page_1based"] != page or any(abs(a-b)>1e-7 for xy, uv in zip(polygon,actual["polygon_top_left_points"]) for a,b in zip(xy,uv)):
                    errors.append("incorrect source inverse mapping/page: " + str(path))
                count += 1
        records.append({"path": str(path.relative_to(ROOT)), "items": len(mapped["items"]), "mapped_fragments": count})
    seal = read(WORK / "vlm/paragraph/runs/seal-texts-30/official-parser-component/source-mapped-geometry.json")
    return {"documents_checked": len(records), "records": records, "errors": errors,
        "precision": "Model block boxes in parser pixels, independently transformed into physical-page points; no token/glyph measurement or semantic character alignment.",
        "seal_full_paragraph_first_block_mapped_only_to_page": [f["original_physical_page_1based"] for f in seal["items"][0]["source_fragments"]],
        "seal_first_block_contains_p4_text_despite_p3_geometry": True,
        "geometry_intersection_does_not_establish_semantic_alignment": True}


def controls_math():
    page = read(WORK / "vlm/page/runs/controls-p1/document.json")
    formulas = [t["text"] for t in page["texts"] if t["label"] == "formula"]
    paragraphs = {str(i): read(WORK / f"vlm/paragraph/runs/controls-texts-{i}/official-parser-component/document.json")["texts"][0]["text"] for i in (4,6,8,10)}
    return {"frozen_case": "G1-C01", "scope": "Four source structures; equivalent mathematical notation allowed; no OCR percentage invented.",
        "page": {"formulas": formulas, "matrix_values_shape_negative_and_square_brackets_correct": "\\left [" in formulas[0] and "1 & - 2 \\\\ 3 & 4" in formulas[0],
            "fraction_no_added_integral_and_complete_denominator": "\\int" not in formulas[1] and r"\frac { 1 } { x + 1 }" in formulas[1],
            "piecewise_two_branches_and_boundary_meaning_correct": r"\begin{cases}" in formulas[2] and r"x\geq 0" in formulas[2] and "x<0" in formulas[2],
            "inline_exponent_semantic_pass": False, "inline_output": next(t["text"] for t in page["texts"] if t["text"].startswith("Let y"))},
        "paragraph": {"outputs": paragraphs, "inline_exponent_semantic_pass": False, "matrix_changed_to_determinant": "\\left |" in paragraphs["6"],
            "fraction_added_integral": "\\int" in paragraphs["8"], "piecewise_duplicate_function_definition": paragraphs["10"].count("f ( x ) =") == 2,
            "piecewise_well_formed_cases": False},
        "reinsertion": "Display-math candidates 6/8/10 abstain as hidden picture children; scalar x 2 output for candidate4 applies and remains wrong."}


def tamper_checks(cases):
    reference = cases["G1-E14"]["details"]["expected"]["reference_paragraph_with_inline_latex"]
    seal = cases["G1-E13"]["details"]["expected"]["reference_paragraph_with_inline_latex"]
    assert semantic_score(reference, "G1-E14", cases["G1-E14"])["math_occurrences_exact_meaning_and_order"]
    assert semantic_score(seal, "G1-E13", cases["G1-E13"])["math_occurrences_exact_meaning_and_order"]
    controls = {"wrong_strict_threshold": not semantic_score(reference.replace("p<0.05", "p\\ge0.05"), "G1-E14", cases["G1-E14"])["math_occurrences_exact_meaning_and_order"],
        "changed_assignment_arrow": not semantic_score(seal.replace(r"\leftarrow", r"\rightarrow"), "G1-E13", cases["G1-E13"])["math_occurrences_exact_meaning_and_order"],
        "lost_model_subscript": not semantic_score(seal.replace(r"_{\theta}", r"\theta", 1), "G1-E13", cases["G1-E13"])["math_occurrences_exact_meaning_and_order"],
        "duplicated_cross_page_fragment": not semantic_score(seal + " associated answers about the passage. Given C.", "G1-E13", cases["G1-E13"])["math_occurrences_exact_meaning_and_order"],
        "dropped_prose": not semantic_score(reference.replace("over all competing methods", "over competing methods"), "G1-E14", cases["G1-E14"])["prose_words_and_inline_positions_match"]}
    controls["lost_update_prime"] = not semantic_score(seal.replace(r"\theta'", r"\theta"), "G1-E13", cases["G1-E13"])["math_occurrences_exact_meaning_and_order"]
    code = "\n".join(cases["G1-C02"]["details"]["oracle"]["code_lines"])
    controls["code_equality_boundary"] = not source_code_exact(code.replace("x <= limit", "x < limit"), code.splitlines())
    controls["code_nested_block_lost"] = not source_code_exact(code.replace('        emit("ok")', '    emit("ok")'), code.splitlines())
    manifest, plan = read(WORK / "inputs/input-manifest.json"), read(WORK / "reinsertion/plan.json")
    candidates = {c["id"]: c for c in manifest["candidates"]}
    rows = [r for r in plan["rows"] if r["source"] == "wikiskill"]
    document = read(ROOT / rows[0]["document_path"])
    folder = WORK / "reinsertion/token-aware/wikiskill"
    proposals = read(folder / "inline-structure.json")["candidates"]
    for name in ("wrong_physical_page", "missing_source_fragment", "changed_fragment_geometry", "partial_charspan", "stale_hash", "duplicate_item", "reordered_native_items"):
        ds, ps = deepcopy(document), deepcopy(proposals)
        if name == "wrong_physical_page": ps[0]["source_association"][0]["physical_page_1based"] = 1
        if name == "missing_source_fragment": ps[0]["source_association"] = []
        if name == "changed_fragment_geometry": ps[0]["source_association"][0]["provider_provenance"]["bbox"]["l"] += 10
        if name == "partial_charspan": ps[0]["replacement_charspan"][0] += 1
        if name == "stale_hash": ps[0]["provider_text_sha256"] = "bad"
        if name == "duplicate_item": ps.append(deepcopy(ps[0]))
        if name == "reordered_native_items": ds["texts"][0],ds["texts"][1] = ds["texts"][1],ds["texts"][0]
        controls[name] = bool(proposal_errors(ds, rows, ps, candidates))
    baseline, candidate = (folder / "baseline.md").read_text(), (folder / "candidate.md").read_text()
    controls["dropped_outside_markdown"] = bool(audit_markdown(baseline, candidate[1:], rows, proposals))
    swapped = deepcopy(proposals)
    swapped[0]["main_markdown_charspan"],swapped[1]["main_markdown_charspan"] = swapped[1]["main_markdown_charspan"],swapped[0]["main_markdown_charspan"]
    controls["swapped_output_order"] = bool(audit_markdown(baseline, candidate, rows, swapped))
    assert all(controls.values()), controls
    return {"all_rejected": all(controls.values()), "controls": controls,
        "producer_guard_saved_selfcheck": read(WORK / "reinsertion/selfcheck.json"),
        "basis": "Reviewer checks mutate only in-memory copies; no source, output or oracle changes and no model calls."}


def inputs_review():
    path = WORK / "inputs/input-manifest.json"
    manifest = read(path)
    errors, documents, source_rows, inventory_expected = [], {}, [], {}
    for source in manifest["sources"]:
        name = source["name"]
        document = read(ROOT / source["document_path"])
        documents[name] = document
        checks = {"source_hash": digest(ROOT / source["source"]["path"]) == source["source"]["sha256"],
                  "baseline_document_hash": digest(ROOT / source["document_path"]) == source["document_sha256"],
                  "snapshots": all(digest(ROOT / row["path"]) == row["sha256"] == digest(ROOT / row["original_path"])
                                   for row in source["snapshots"]),
                  "page_render_hashes_and_dimensions": all(digest(ROOT / row["path"]) == row["sha256"] and
                      png_size(ROOT / row["path"]) == row["pixels_wh"] for row in source["full_page_renders"])}
        source_rows.append({"source": name, "checks": checks})
        errors.extend(f"{name}: {key}" for key, value in checks.items() if not value)
        selected = set(source["selected_physical_pages"])
        for item in document["texts"]:
            if item["label"] == "text" and item["content_layer"] == "body" and selected.intersection(p["page_no"] for p in item["prov"]):
                inventory_expected[(name, item["self_ref"])] = item
    actual_inventory = {(row["source"], row["item_ref"]): row for row in manifest["ordinary_paragraph_inventory"]}
    if set(actual_inventory) != set(inventory_expected):
        errors.append("ordinary-body inventory incomplete or expanded")
    for key, row in actual_inventory.items():
        item = inventory_expected[key]
        if row["provider_text"] != item["text"] or row["provider_provenance"] != item["prov"]:
            errors.append(f"inventory content/provenance changed: {key}")
        if row["gate_characters"] != gate(item["text"]) or row["selected_by_gate"] != bool(gate(item["text"])):
            errors.append(f"character gate disagrees: {key}")
    candidates = {row["id"]: row for row in manifest["candidates"]}
    selected_expected = {(name, ref) for (name, ref), row in actual_inventory.items() if row["selected_by_gate"]}
    selected_actual = set()
    candidate_results = []
    for row in candidates.values():
        name = row["id"].split("-texts-")[0]
        item = documents[name]["texts"][int(row["item_ref"].split("/")[-1])]
        checks = {"native_item_content_and_label": row["provider_text"] == item["text"] and row["provider_label"] == item["label"],
                  "native_item_text_hash": sha256(item["text"].encode()).hexdigest() == row["provider_text_sha256"],
                  "candidate_image_hash": digest(ROOT / row["image_path"]) == row["image_sha256"],
                  "replacement_is_full_exact_item": row["replacement_charspan"] == [0, len(item["text"])],
                  "all_provider_fragments_retained_in_order": [frag["provider_provenance"] for frag in row["fragments"]] == item["prov"]}
        if row["selection_reason"] == "ordinary_body_text_character_gate":
            selected_actual.add((name, row["item_ref"]))
            checks["automatic_gate_positive"] = bool(gate(item["text"])) and row["gate_characters"] == gate(item["text"])
        else:
            checks["declared_controls_label_regression"] = name == "controls" and item["label"] in ("formula", "code")
        previous_bottom = 0
        for fragment in row["fragments"]:
            prov = fragment["provider_provenance"]
            width, height = (fragment["source_page_size_points"][key] for key in ("width", "height"))
            box = prov["bbox"]
            expected_tl = [box["l"], height - box["t"], box["r"], height - box["b"]] if box["coord_origin"] == "BOTTOMLEFT" else [box[k] for k in ("l", "t", "r", "b")]
            scale, pad = manifest["render_scale"], manifest["padding_points"]
            expected_crop = [max(0, floor((expected_tl[0] - pad) * scale)), max(0, floor((expected_tl[1] - pad) * scale)),
                             min(ceil(width * scale), ceil((expected_tl[2] + pad) * scale)),
                             min(ceil(height * scale), ceil((expected_tl[3] + pad) * scale))]
            canvas_x, canvas_y, canvas_w, canvas_h = fragment["paragraph_canvas_xywh"]
            matrix = fragment["paragraph_pixels_to_source_top_left_points_3x3"]
            checks[f"fragment_{fragment['fragment_index']}_geometry"] = (
                fragment["physical_page_1based"] == prov["page_no"] and fragment["provider_bbox_top_left_points"] == expected_tl and
                fragment["render_crop_pixel_box"] == expected_crop and
                fragment["fragment_pixels_wh"] == [expected_crop[2] - expected_crop[0], expected_crop[3] - expected_crop[1]] and
                png_size(ROOT / fragment["fragment_image_path"]) == fragment["fragment_pixels_wh"] and
                digest(ROOT / fragment["fragment_image_path"]) == fragment["fragment_image_sha256"] and
                all(abs(a - b) < 1e-8 for a, b in zip(point(matrix, canvas_x, canvas_y), [expected_crop[0] / scale, expected_crop[1] / scale])) and
                canvas_y >= previous_bottom and canvas_w == fragment["fragment_pixels_wh"][0] and canvas_h == fragment["fragment_pixels_wh"][1])
            previous_bottom = canvas_y + canvas_h
        candidate_results.append({"id": row["id"], "checks": checks,
            "physical_pages": [frag["physical_page_1based"] for frag in row["fragments"]],
            "provider_charspans": [frag["provider_provenance"]["charspan"] for frag in row["fragments"]],
            "precision": "provider paragraph/fragment boxes plus render-derived crop transform; no measured token boxes"})
        errors.extend(f"{row['id']}: {key}" for key, value in checks.items() if not value)
    if selected_actual != selected_expected:
        errors.append("inference candidates disagree with ordinary character gate")
    frozen_cases = {case: {"candidate_ids": ids, "all_selected": all(name in candidates for name in ids),
        "selection_reasons": [candidates[name]["selection_reason"] for name in ids],
        "physical_pages": sorted({frag["physical_page_1based"] for name in ids for frag in candidates[name]["fragments"]})}
        for case, ids in FROZEN_CANDIDATES.items()}
    return {"manifest_sha256": digest(path), "counts": manifest["counts"], "sources": source_rows,
            "candidate_checks": candidate_results, "frozen_case_selection": frozen_cases, "errors": errors,
            "selection_scope": "Producer text gate within the explicitly selected physical-page inventory, not document-wide inline coverage or semantic span detection.",
            "oracle_content_or_boxes_used_for_selection_declared": manifest["oracle_content_or_boxes_used_for_selection"]}


def main():
    assert digest(REGISTRY) == FROZEN_SHA
    cases = {case["id"]: case for case in read(REGISTRY)["cases"]}
    runs = [model_run(path) for kind in ("page", "paragraph") for path in sorted((WORK / "vlm" / kind / "runs").iterdir()) if path.is_dir()]
    models = {"run_count": len(runs), "runs": runs,
        "all_ended_eos_without_cap": all(r["ended_eos"] and not r["at_limit"] for r in runs),
        "all_22_rstrip_damage_reproduced": all(r["engine_rstrip_reproduced_exactly"] and r["engine_closing_doctag_damaged"] for r in runs),
        "all_token_aware_decode_only_removes_terminal_specials": all(r["token_aware_decode_removes_only_terminal_specials"] for r in runs),
        "all_recorded_id_splits_and_terminal_eos_match": all(r["generated_ids_match_prefix_split"] and r["terminal_id_is_recorded_eos"] for r in runs),
        "all_image_inputs_cpu_fp32": all(r["image_input_cpu_fp32"] for r in runs),
        "all_component_and_token_parser_documents_equal": all(r["engine_and_token_parser_documents_equal"] for r in runs)}
    assembly = read(WORK / "vlm/assembly-replay/verification.json")
    for variant in ("engine-output", "token-aware"):
        doc = read(WORK / "vlm/assembly-replay" / variant / "document.json")
        assert list(doc["pages"]) == ["1", "2"]
        assert not any(len({p["page_no"] for p in t["prov"]}) > 1 for t in doc["texts"])
    assembly["independent_boundary_review"] = "Actual official assembly replay keeps physical3/4 paragraph fragments as separate items; sidecar maps parser1/2 to physical3/4. Zero inference."
    result = {"format": "g2-inline-independent-review-v1", "frozen_cases_sha256": digest(REGISTRY),
              "checker_sha256": digest(__file__), "inputs": inputs_review(),
              "input_pixel_checks": read(WORK / "review/input-pixel-check.json"),
              "model_outputs": models, "frozen_case_semantics": case_outputs(cases),
              "C01_math_regression": controls_math(), "geometry": geometry_review(),
              "reinsertion": reinsertion_review(), "official_assembly_replay": assembly,
              "selfchecks": tamper_checks(cases)}
    (WORK / "review/output-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    assert not result["inputs"]["errors"], result["inputs"]["errors"]
    assert not result["geometry"]["errors"], result["geometry"]["errors"]
    assert not result["reinsertion"]["errors"], result["reinsertion"]["errors"]
    assert models["run_count"] == 22 and all(models[k] for k in models if k.startswith("all_"))
    print(json.dumps({"input_errors": result["inputs"]["errors"], "counts": result["inputs"]["counts"],
        "model_runs": len(runs), "geometry_documents": result["geometry"]["documents_checked"],
        "reinsertion_errors": result["reinsertion"]["errors"], "selfchecks": result["selfchecks"]["controls"]}, indent=2))


if __name__ == "__main__":
    main()
