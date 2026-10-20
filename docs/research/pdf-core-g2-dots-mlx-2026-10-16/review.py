"""Record source-based review; never alter predictions or rerun inference."""
import collections
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUN = HERE / "run"
DIAG = HERE.parent / "pdf-core-g2-dots-mlx-renderer-diagnostic-2026-10-16"


def read(path):
    return json.loads(path.read_text())


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


contract = read(HERE.parent / "pdf-core-g2-official-method-2026-10-15/review/contract.json")
pages = read(HERE / "inputs.json")["pages"]
completed = read(RUN / "completed-pages.json")
assert len(completed) == len(pages) == 12
page_audit = []
for record in completed:
    page = RUN / record["id"]
    doc = read(page / "document.json")
    boxes, invalid, missing = 0, [], 0
    for item in doc["texts"] + doc["tables"] + doc["pictures"]:
        if not item.get("prov"):
            missing += 1
        for prov in item.get("prov", []):
            boxes += 1
            box, size = prov["bbox"], doc["pages"][str(prov["page_no"])]["size"]
            if not (0 <= box["l"] <= box["r"] <= size["width"] and 0 <= min(box["t"], box["b"]) <= max(box["t"], box["b"]) <= size["height"]):
                invalid.append(item["self_ref"])
    generation = read(page / "generation.json")
    page_audit.append({**record, "strict_json_array": read(page / "prediction.json")["strict_nonempty_json_array"],
        "finish_reason": generation["finish_reason"], "generation_tokens": generation["generation_tokens"],
        "native_items": len(doc["texts"]) + len(doc["tables"]) + len(doc["pictures"]),
        "provenance_boxes": boxes, "out_of_page_boxes": invalid, "items_without_provenance": missing,
        "source_render_valid": record["id"] not in {"validation-02-p1", "validation-02-p12"}})

# Fixed pre-output scope and equivalences; exact identifiers are not relaxed.
material = {"wikiskill/ordinary_paragraph--texts-368", "dgm/code_item--texts-646",
            "dgm/ordinary_paragraph--texts-648", "seal/ordinary_paragraph--texts-23",
            "seal/ordinary_paragraph--texts-30"}
f13 = {"wikiskill": {361, 362, 363}, "dgm": set(),
       "seal": {30, 32, 33, 34, 46, 47, 48, 49, 50, 51, 52}, "controls": {0, 1, 2, 4}}
f13_pass = {("wikiskill", 361), ("wikiskill", 362), ("wikiskill", 363), ("seal", 34), ("seal", 49), ("controls", 4)}
f14 = {"dgm": {646, 648, 650, 652}, "controls": {12, 13, 14}, "wikiskill": set(), "seal": set()}
notes = {
    "wikiskill/ordinary_paragraph--texts-357": "Full prose occurs once over p20/p21; two page-local paragraphs remain, not one logical cross-page paragraph.",
    "wikiskill/ordinary_paragraph--texts-361": "Complete source prose and both inline set/k expressions preserved as LaTeX, including both comma-k subscripts.",
    "wikiskill/ordinary_paragraph--texts-362": "Complete opening, two test-set expressions and equal-weight macro-bootstrap prose preserved inline.",
    "wikiskill/ordinary_paragraph--texts-363": "Original E14 full paragraph and all six M-star/threshold expressions preserved in raw, native text and Markdown.",
    "wikiskill/ordinary_paragraph--texts-366": "Complete Trace2Skill analyst/merge/validation chain retained.",
    "wikiskill/ordinary_paragraph--texts-367": "Complete EvoSkill prose, emphasis and SKILL.md literal retained in place; no code-block detachment.",
    "wikiskill/ordinary_paragraph--texts-368": "Frozen rubric requires exact ReflACT capitalization; raw RefLACT differs. Remaining six stages and prose retained; still split across pages.",
    "dgm/code_item--texts-646": "Raw changes test_success to testsuccess/test success, run_tests to run tests and best_attempt to best_attempts. JSON also has invalid escapes; native document empty.",
    "dgm/ordinary_paragraph--texts-648": "Raw edit_actions becomes editActions; other commands, nodes and percentages retained. Native delivery unavailable due whole-page invalid JSON. Original E04 regresses.",
    "dgm/ordinary_paragraph--texts-649": "Raw node6 label complete; native document empty because page JSON invalid.",
    "dgm/code_item--texts-650": "Both raw instruction paragraphs and exact literal names/uniqueness/no-write conditions retained. Native document empty because page JSON invalid.",
    "dgm/ordinary_paragraph--texts-651": "Raw node24 label complete; native document empty because page JSON invalid.",
    "dgm/code_item--texts-652": "Raw complete editor/atomic/context preservation instruction retained. Native document empty because page JSON invalid.",
    "seal/ordinary_paragraph--texts-21": "Complete Knowledge Updating prose across p2/p3 retained once; no native logical cross-page paragraph join.",
    "seal/ordinary_paragraph--texts-23": "First source ICL acronym becomes ICI. The case-specific OpenAI/OpenAl allowance is not extended to a new identifier.",
    "seal/ordinary_paragraph--texts-24": "Complete RL-for-LLMs and self-edit/weight-update distinction retained.",
    "seal/ordinary_paragraph--texts-25": "Complete meta-learning prose/citations and source wording retained.",
    "seal/ordinary_paragraph--texts-26": "Complete Self Improvement comparison with external-data interaction retained.",
    "seal/ordinary_paragraph--texts-28": "Complete two-loop framework prose retained; ordinary SE acronym need not be separately typed math.",
    "seal/ordinary_paragraph--texts-30": "P3 first seven original math occurrences retained as LaTeX; p4 uses HTML/italics and changes source theta to theta_0 in SFT(theta,SE). Original E13 content and cross-page delivery fail.",
    "seal/ordinary_paragraph--texts-32": "LM_theta-prime/reward/tau meanings retained as HTML subscript and italics, without required usable inline LaTeX.",
    "seal/ordinary_paragraph--texts-45": "Complete are-sampled-from/current-model suffix is retained as end of the full left-column paragraph.",
    "seal/ordinary_paragraph--texts-46": "Complete GRPO/PPO/ReST-EM prose; EM is HTML superscript rather than required inline LaTeX.",
    "seal/ordinary_paragraph--texts-47": "Complete EM E-step/M-step prose; ReST-EM again HTML superscript, not inline LaTeX.",
    "seal/ordinary_paragraph--texts-49": "Full gradient/reward/non-differentiability prose and all six inline math expressions retained as usable LaTeX.",
    "seal/ordinary_paragraph--texts-52": "Full prose and mathematical meanings retained, but SE_ij and ReST-EM use HTML rather than complete required inline LaTeX.",
    "seal/ordinary_paragraph--texts-53": "Complete teacher/student paragraph retained.",
    "seal/formula--texts-33": "Raw formula1 meanings/label retained; existing $$ remain inside Formula.text and stock Markdown adds another pair.",
    "seal/ordinary_paragraph--texts-34": "Full left-column paragraph, theta-prime/old/current and continuation45 retained together as one Text; algorithm title separate; inline LaTeX preserved.",
    "seal/formula--texts-48": "Raw cases/reward arguments/label2 retained with adjacent footnote2 context; native Markdown repeats $$ delimiters.",
    "seal/formula--texts-50": "Raw formula3 negative/NM/sums/gradient/conditional and label3 retained; native Markdown repeats $$ delimiters.",
    "seal/formula--texts-51": "Raw and native Formula.text preserve y_<s/history/C_i/label4; stock Markdown repeats $$ delimiters.",
}
units = []
for unit in contract["units"]:
    source, uid = unit["source"], unit["unit_id"]
    number = int(unit["native_target_refs"][0].split("/")[-1])
    f13_applies = number in f13[source] and not (source == "controls" and "paragraph" in unit["job_id"] and number == 1)
    note = notes.get(uid)
    if source == "controls":
        if "formula_envelope" in uid:
            note = "Correct raw source formula; Formula.text includes $$ and stock Markdown emits $$$$ delimiters, so complete F13 delivery unqualified."
        elif number == 4:
            note = "Complete source sentence and y=x^2+1 inline LaTeX retained in Markdown."
        elif number in {12, 13, 14}:
            note = "Source comment/code/operator/meaningful indentation retained; inline items[i] <= limit stays at prose position."
        else:
            note = "Complete source ordinary prose retained."
    assert note
    units.append({"unit_id": uid, "physical_pages": unit["physical_pages_1based"],
        "raw_source_fidelity": "material" if uid in material else "pass",
        "native_content_delivery_available": source != "dgm", "F13_applicable": f13_applies,
        "F13_complete_delivery": (source, number) in f13_pass if f13_applies else None,
        "F14_applicable": number in f14[source],
        "F14_complete_delivery": source == "controls" if number in f14[source] else None,
        "finding": note})
assert len(units) == len(notes) + 9 == 41
assert collections.Counter(x["raw_source_fidelity"] for x in units) == {"pass": 36, "material": 5}
assert sum(x["F13_applicable"] for x in units) == 18
assert sum(x["F13_complete_delivery"] is True for x in units) == 6
assert sum(x["F14_applicable"] for x in units) == 7
assert sum(x["F14_complete_delivery"] is True for x in units) == 3
assert 'editActions' in (RUN / 'dgm-p51/raw.txt').read_text()
assert 'RefLACT' in (RUN / 'wikiskill-p21/raw.txt').read_text()
assert 'with ICI enables' in (RUN / 'seal-p3/raw.txt').read_text()
assert 'θ*<sub>0</sub>' in (RUN / 'seal-p4/raw.txt').read_text()
assert len(read(RUN / 'dgm-p51/document.json')["texts"]) == 0
assert '$$$$ M =' in (RUN / 'controls-p1/document.md').read_text()

validation = read(HERE.parent / "pdf-core-g2-dots-2026-10-16/validation/source-contract.json")
validation_units = []
for unit in validation["positive_units"]:
    uid = unit["id"]
    if uid.startswith("V02"):
        status, delivered, note = "input_render_failure", False, "Native input obscures source in black; not a valid model-accuracy observation. Original outcome retained."
    elif uid == "V01-P001-C01":
        status, delivered, note = "material", False, "Loop nesting retained but actual window image argument replaced by unsupported literal black square, without image mapping/refusal."
    elif uid == "V01-P011-P03":
        status, delivered, note = "material", False, "Source q_tilde-phi becomes q_phi, losing the decoder parameter's tilde."
    elif uid == "V01-P011-P01":
        status, delivered, note = "pass", False, "Math meanings and prose retained, but source 9x9 and16x16 mathematical occurrences emitted as plain Unicode rather than LaTeX."
    else:
        status, delivered, note = "pass", True, "Complete source paragraph math/prose retained under frozen font/macro equivalences; draw identifier retained in place where applicable."
    validation_units.append({"id": uid, "kind": unit["kind"], "raw_source_fidelity": status,
        "complete_required_delivery": delivered, "finding": note})
negative_units = []
for unit in validation["negative_units"]:
    uid = unit["id"]
    status = "input_render_failure" if uid.startswith("V02") else "literal_name_mismatch" if uid in {"V01-P001-N02", "V01-P001-N03"} else "pass"
    negative_units.append({"id": uid, "raw_source_fidelity": status,
        "observed_false_math_or_code_enrichment": None if status == "input_render_failure" else False,
        "finding": "Iizuka citation becomes IIZuka; disclosed, not silently counted fully faithful." if status == "literal_name_mismatch" else "Ordinary prose retained without false math/code role." if status == "pass" else "Invalid source render; no model quality grade."})
assert len(validation_units) == 12 and len(negative_units) == 10
assert collections.Counter(x["raw_source_fidelity"] for x in validation_units) == {"pass": 6, "material": 2, "input_render_failure": 4}
diagnostic_units = [{"id": unit["id"], "raw_source_fidelity": "material" if unit["id"] == "V02-P012-P03" else "pass",
    "complete_required_delivery": unit["id"] != "V02-P012-P03",
    "finding": "Both source gg+gq_S occurrences become gg+gq\\bar{s}; subscript/channel meaning changes." if unit["id"] == "V02-P012-P03" else "Source math and paragraph fragment preserved as inline LaTeX."}
    for unit in validation["positive_units"] if unit["id"].startswith("V02")]
diag_raw = json.loads((DIAG / "run/validation-02-p12/raw.txt").read_text())
assert r'gq\bar{s}' in diag_raw[2]["text"]
assert r'q_{\tilde{\phi}}' not in json.loads((RUN / "validation-01-p11/raw.txt").read_text())[6]["text"]
execution = read(RUN / "execution.json")
good_render_times = [x["seconds"] for x in page_audit if x["source_render_valid"]]
summary = {"model": "dots.ocr pinned BF16 through MLX", "main_inference_calls": 12, "main_completed_calls": 12,
    "runtime_only_import_failure_before_model_instances": 1, "strict_json_arrays": sum(x["strict_json_array"] for x in page_audit),
    "invalid_source_render_pages": 2, "good_render_page_latency_seconds": {"n": len(good_render_times),
        "min": min(good_render_times), "median": statistics.median(good_render_times), "max": max(good_render_times), "sum": sum(good_render_times)},
    "main_total_seconds_including_initialization": execution["seconds"],
    "main_peak_mlx_allocated_bytes": max(x["mlx_peak_bytes"] for x in completed),
    "main_peak_sampled_process_tree_rss_bytes": execution["peak_sampled_tree_rss_bytes"],
    "memory_counters_must_not_be_summed": True, "exposed_raw_content": dict(collections.Counter(x["raw_source_fidelity"] for x in units)),
    "exposed_F13_complete_delivery": {"pass": 6, "total": 18}, "exposed_F14_complete_delivery": {"pass": 3, "total": 7},
    "independent_validation_positive": dict(collections.Counter(x["raw_source_fidelity"] for x in validation_units)),
    "independent_validation_negative": dict(collections.Counter(x["raw_source_fidelity"] for x in negative_units)),
    "renderer_diagnostic_calls": 2, "renderer_diagnostic_math_paragraphs": {"pass": 3, "material": 1, "total": 4},
    "renderer_diagnostic_ordinary_abstract": "pass", "diagnostics_not_substituted_for_main_validation": True,
    "full_challenger_eligible": False, "g2_passed": False, "holdout_reads": 0, "output_repairs": 0}
save("review.json", {"method": "Manual fixed-source review of all41 exposed units and22 validation units; raw content, native delivery and source-render failure remain distinct. Exact identifier rubric retained. No new output repairs or tuned model retry.",
    "summary": summary, "page_audit": page_audit, "exposed_units": units, "validation_positive_units": validation_units,
    "validation_negative_units": negative_units, "renderer_diagnostic_positive_units": diagnostic_units})
print(json.dumps(summary))
