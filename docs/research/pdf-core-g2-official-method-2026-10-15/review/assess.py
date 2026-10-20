"""Freeze manually adjudicated source findings; assert identities and selected evidence."""
import collections
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "docs/research/pdf-core-g2-official-method-2026-10-15"
OUT = BASE / "review"


def reference(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


contract_path = OUT / "contract.json"
assert reference(contract_path)["sha256"] == "22ee81e79db28cf07d14ddd1f53269aada08d8b6480633ef67046a3e955777f2"
contract = json.loads(contract_path.read_text())
docs = {s: json.loads((BASE / "documents" / s / "document.json").read_text()) for s in ("wikiskill", "dgm", "seal", "controls")}
md = {s: (BASE / "documents" / s / "document.md").read_text() for s in docs}
raw = {p.parent.name: p.read_text() for p in sorted((BASE / "api").glob("*/raw-doctags.txt"))}
assert len(raw) == 8

# Source-unit mappings are evaluator observations, never production repair or model input.
mapping = {
    "wikiskill": {357: [5, 8], 361: list(range(10, 13)), 362: list(range(13, 18)), 363: list(range(18, 27)), 366: [29], 367: [30], 368: [31, 34]},
    "dgm": {646: [0], 648: [2], 649: [3], 650: [4], 651: [5], 652: [6]},
    "seal": {21: [7, 9], 23: [10], 24: [11], 25: [12], 26: [13], 28: [15], 30: list(range(17, 32)) + list(range(33, 44)), 32: [44], 45: [46], 46: [49], 47: [50], 49: [52], 52: [55], 53: [56], 33: [45], 34: [46, 47], 48: [51], 50: [53], 51: [54]},
    "controls": {0: [8], 1: [10], 2: [12], 1001: [1], 4: [4, 5, 6], 12: [14], 13: [14], 14: [15, 16], 15: [17, 18]},
}
f13 = {"wikiskill": {361, 362, 363}, "dgm": set(), "seal": {30, 32, 33, 34, 46, 47, 48, 49, 50, 51, 52}, "controls": {0, 1, 2, 4}}
f13_pass = {("wikiskill", 362), ("controls", 0), ("controls", 1), ("controls", 2)}
f14 = {"wikiskill": set(), "dgm": {646, 648, 650, 652}, "seal": set(), "controls": {12, 13, 14}}

findings = {
    ("wikiskill", 357): ["All source words across pages20/21 retained once. Official assembly leaves two root text items and two Markdown paragraphs at represent / the average; one logical paragraph delivery fails."],
    ("wikiskill", 361): ["Complete prose, sample/train subset with both comma-k subscripts,8/5/3/15,000 preserved. Iteration variable k remains plain text rather than required inline math; full-expression F13 delivery incomplete."],
    ("wikiskill", 362): ["Complete lead-in/opening sentence,1,000 iterations and both D_test/cardinality formulas retained inline; original opening-omission positive retained."],
    ("wikiskill", 363): ["All prose,6 mathematical meanings and winner/tie quantifiers retained. Only4 formula children emitted: M-star3 times and p<0.05 once; both p>=0.05 stay plaintext. Original6-inline-LaTeX positive regresses."],
    ("wikiskill", 366): ["Complete Trace2Skill paragraph, author/year, parallel analysts and recursive consolidation/validation chain preserved."],
    ("wikiskill", 367): ["Complete EvoSkill paragraph, failure-only input, SKILL.md and bounded-frontier validation preserved."],
    ("wikiskill", 368): ["Source ReflACT becomes RefACT, dropping lowercase l. Full remaining prose and ordered6stage expansion preserved across pages21/22, but remains two root paragraphs."],
    ("dgm", 646): ["Extensive source-code changes: test_stats becomes test_state in assignment/default/log/final condition; removed diff line gains comma; tie-break attempt.error_messages or [] becomes attempt.test_state.get(...), likewise best_attempt; exact string quotes change; === log marker becomes ---; Test Success log omitted. Context/diff indentation also rewritten. Literal-preserving F14 fails without any proposed answer repair."],
    ("dgm", 648): ["All prose and ordered edit/edit_type/edit_actions/edit/str_replace preserved inline as ordinary text; node6 retains/adds/23.3%, node24 replaces/40.5%. Original E04 passes; absence of typed inline code/backticks is not a product failure."],
    ("dgm", 649): ["Exact node6 label retained separately from its instruction block."],
    ("dgm", 650): ["Both complete quoted instruction paragraphs and tools/edit.py/edit/str_replace/old_str/new_str preserved; uniqueness/no-write conditions intact. Printer wraps reflow, allowed by frozen source rule; Python language metadata is misleading but no textual repair occurred."],
    ("dgm", 651): ["Exact node24 label retained separately from its instruction block."],
    ("dgm", 652): ["Complete quoted editor instructions retained, with source-authorized wrap reflow. Python language metadata is misleading for instruction prose; content/block F14 preserved."],
    ("seal", 21): ["Complete Knowledge Updating paragraph retained across pages2/3; question-answer dash variant is allowed typography. Official assembly leaves two separate paragraphs at or / other output formats."],
    ("seal", 23): ["Full Test-Time Training prose preserved; redundant outer text/inline markup did not remove words from parsed output."],
    ("seal", 24): ["Full Reinforcement Learning for LLMs prose preserved, including self-edit generation versus final-answer optimization."],
    ("seal", 25): ["Complete meaning/references retained; source comma after Schmidhuber[46] becomes period and parametrize becomes parameterize. Named minor punctuation/orthographic variants, not material model-claim changes."],
    ("seal", 26): ["Complete Self-Improvement prose and citations preserved."],
    ("seal", 28): ["Complete two-loop framework prose retained. Standalone SE need not gain a custom typed math role; historical minor grade remains untouched in prior results."],
    ("seal", 30): ["All original prose/mathematical meanings from both pages present once in raw and parsed text, but raw p3 puts inline inside text, splits LM plus orphan _theta, and official parser emits multiple detached display blocks. Fourteen matched p3 child items lack provenance. Page4 is a separate inline group; original one-paragraph/11-inline-math/both-fragment delivery fails."],
    ("seal", 32): ["Raw HTML subscript retains theta-prime correctly and all prose/math meaning; model emits no formula elements for r,LM_theta-prime,tau. Official parser drops subscript markup, Markdown LMtheta-prime lacks source subscript attachment; F13 fails. This is not the prior prime-deletion error."],
    ("seal", 45): ["Complete are sampled from...the current model suffix preserved once, legitimately joined into the full left-column paragraph46; native item boundary need not be copied."],
    ("seal", 46): ["Full GRPO/PPO/ReST paragraph retained; raw ReST<sup>EM</sup> correctly conveys superscript, official parser flattens to ReSTEM with no formula. F13 notation delivery fails."],
    ("seal", 47): ["Full EM E-step/M-step paragraph retained; raw ReST superscript retained but parsed as ReSTEM without LaTeX."],
    ("seal", 49): ["Complete prose/gradient/reward/N/M meanings present in raw HTML/text. Parsed Markdown flattens gradient/subscripts, and reward term remains plaintext; no required inline LaTeX delivered."],
    ("seal", 52): ["Complete prose and raw HTML sub/sup associations present; official parser loses mathematical attachments in p_theta_t,y_s^(i,j),SE_ij,C_i,ReST^EM and leaves r=0 plaintext. F13 fails."],
    ("seal", 53): ["Complete teacher-student paragraph preserved."],
    ("seal", 33): ["Newly attempted formula1 preserves nested expectations, distributions, conditional C, negative sign and reward arguments, but source equation label(1) is omitted in raw and parsed output. Core math is available; full frozen target fails."],
    ("seal", 34): ["Native erroneously merged paragraph/title is correctly separated; complete heading and substantive prose retained, but of this omitted from The implication of this is that. Minor meaning-preserving omission named. Raw HTML subscript old/current is flattened by parser and most math stays plaintext; F13 fails. Unit45 suffix is part of the same output paragraph and not counted twice."],
    ("seal", 48): ["Newly attempted formula2 preserves cases1/0, condition and theta_t; source equation label(2) omitted. Raw XML &amp; is left literally in parsed LaTeX rather than alignment &, breaking usable cases syntax. Superscript2 links visible footnote context, not evidence that source performance is squared."],
    ("seal", 50): ["Newly attempted formula3 preserves negative1/NM, i/j sums, r_ij, gradient and conditional self-edit; source equation label(3) omitted. Core LaTeX is usable; full target fails."],
    ("seal", 51): ["Newly attempted formula4 preserves negative1/NM, i/j/s sums, gradient and conditional token/history; source equation label(4) omitted. Raw XML &lt; in history condition is left literally in parsed LaTeX, so required y_<s notation is not usable as delivered."],
    ("controls", 0): ["Matrix M,2x2 structure,1,-2,3,4 faithfully delivered in display LaTeX."],
    ("controls", 1): ["Fraction g(x)=1/(x+1) faithfully delivered in display LaTeX."],
    ("controls", 2): ["Piecewise f(x),x^2 for x>=0,0 for x<0 faithfully delivered; source two-character >= preserved in text within LaTeX, allowed by source contract."],
    ("controls", 1001): ["Complete original-toy-source disclaimer preserved."],
    ("controls", 4): ["Complete sentence and equation meaning retained inline, but y= is text while only x^2+1 is LaTeX. Frozen required expression y=x^2+1 is only partially represented as math; source-content pass and full-expression F13 delivery differ."],
    ("controls", 12): ["Source comment retained once as first line of legitimate combined code block, followed by unit13 body; full-page method has no old target-only context leakage."],
    ("controls", 13): ["All six source body lines retained with indent0/4/4/8/0/4 and <=, +=, quoted ok/skip preserved; grouped with comment once, allowed by frozen fullpage rule."],
    ("controls", 14): ["Source prose label plus inline code items[i] <= limit correctly delivered; native code-item mislabel not reproduced as detached block."],
    ("controls", 15): ["Complete source-faithful instruction sentence and[1] reference retained."],
}

material = {("wikiskill", 368), ("dgm", 646), ("seal", 33), ("seal", 48), ("seal", 50), ("seal", 51)}
minor = {("seal", 25), ("seal", 34)}
page_lookup = {s: {i + 1: p for i, p in enumerate(sorted(x["physical_page_1based"] for x in contract["scope"]["page_manifest"] if x["source"] == s))} for s in docs}
units = []
for unit in contract["units"]:
    s = unit["source"]
    n = int(unit["native_target_refs"][0].split("/")[-1])
    if s == "controls" and n == 1 and "paragraph" in unit["job_id"]:
        n = 1001
    key = (s, n)
    matched = [docs[s]["texts"][i] for i in mapping[s][n]]
    prov = [p for item in matched for p in item.get("prov", [])]
    inferred_boxes_valid = True
    for p in prov:
        size = docs[s]["pages"][str(p["page_no"])]["size"]
        box = p["bbox"]
        inferred_boxes_valid &= 0 <= box["l"] <= box["r"] <= size["width"] and 0 <= box["t"] <= box["b"] <= size["height"]
    record = {
        "unit_id": unit["unit_id"], "source": s, "job_id": unit["job_id"], "prior_prepared": unit["prior_prepared"],
        "executed": True, "source_clear": True, "source_ambiguous": False,
        "raw_source_fidelity_status": "material" if key in material else "minor" if key in minor else "pass",
        "raw_target_content_complete_under_allowed_minor_equivalence": key not in material,
        "raw_core_mathematical_meaning_preserved": key not in {("wikiskill", 368), ("dgm", 646)},
        "raw_source_equation_label_present": False if s == "seal" and n in {33, 48, 50, 51} else None,
        "content_observed_in_raw_and_parsed": True,
        "parsed_item_refs": [x["self_ref"] for x in matched],
        "parsed_formula_item_count": sum(x["label"] == "formula" for x in matched),
        "matched_output_local_pages": sorted({p["page_no"] for p in prov}),
        "matched_output_physical_pages_via_input_order_sidecar": sorted({page_lookup[s][p["page_no"]] for p in prov}),
        "expected_physical_pages": unit["physical_pages_1based"],
        "all_matched_items_have_provenance": all(x.get("prov") for x in matched),
        "all_available_inferred_boxes_inside_page_bounds": bool(inferred_boxes_valid),
        "inferred_boxes_are_ground_truth": False,
        "page_bounds_pass_proves_correct_localization": False,
        "F13_applicable": n in f13[s],
        "F13_complete_source_expression_and_required_presentation_delivered": key in f13_pass if n in f13[s] else None,
        "F14_applicable": n in f14[s],
        "F14_content_and_block_delivery_pass": key != ("dgm", 646) if n in f14[s] else None,
        "original_single_logical_paragraph_preserved": False if key in {("wikiskill", 357), ("wikiskill", 368), ("seal", 21), ("seal", 30)} else None,
        "custom_typed_JSON_contract_applies": False,
        "findings": findings[key],
    }
    assert record["matched_output_physical_pages_via_input_order_sidecar"] == record["expected_physical_pages"], record
    units.append(record)

assert len(units) == 41 and len({x["unit_id"] for x in units}) == 41
counts = dict(collections.Counter(x["raw_source_fidelity_status"] for x in units))
assert counts == {"pass": 33, "material": 6, "minor": 2}, counts
assert sum(x["F13_applicable"] for x in units) == 18
assert sum(x["F13_complete_source_expression_and_required_presentation_delivered"] is True for x in units) == 4
assert sum(x["F14_applicable"] for x in units) == 7
assert sum(x["F14_content_and_block_delivery_pass"] is True for x in units) == 6
assert "RefACT" in docs["wikiskill"]["texts"][31]["text"] and "ReflACT" not in raw["wikiskill-p21"]
assert raw["wikiskill-p21"].split("We determine", 1)[1].split("</inline>", 1)[0].count("<formula>") == 4
assert "test_state = self.run_tests()" in docs["dgm"]["texts"][0]["text"]
assert 'Test Success:' not in docs["dgm"]["texts"][0]["text"]
assert docs["controls"]["texts"][14]["text"].splitlines() == ["# keep the boundary and block nesting", "if x <= limit:", "    total += x", "    if ready:", '        emit("ok")', "else:", '    emit("skip")']
assert "&amp;" in docs["seal"]["texts"][51]["text"] and "&lt;" in docs["seal"]["texts"][54]["text"]
assert not any(x.get("prov") for x in docs["seal"]["texts"][18:32])

redactions = []
for page, value in raw.items():
    for line in value.splitlines():
        if "[REDACTED]" in line:
            at = line.index("[REDACTED]")
            redactions.append({"page": page, "context": line[max(0, at - 75):at + 110], "selected41_scope_affected": False, "attribution": "Existing credential scrub regex matches ordinary sk-specific suffix in task-specific; saved evidence mutation, not model error. Original text independently present in live official parsed document; no raw restoration made."})
assert len(redactions) == 1 and redactions[0]["page"] == "seal-p2"
assert "task-specific data augmentation" in md["seal"]

anchors = [
    {"case": "G1-E14", "unit_id": "wikiskill/ordinary_paragraph--texts-363", "original_content_math_meanings_pass": True, "original_full_delivery_pass": False, "reason": "Only4/6 inlineLaTeX occurrences, two p>=0.05 plaintext."},
    {"case": "G1-E13", "unit_id": "seal/ordinary_paragraph--texts-30", "original_content_math_meanings_pass": True, "original_full_delivery_pass": False, "reason": "Detached display formula blocks, crosspage paragraph split,14sourcechilditemswithoutprovenance; original11span/oneparagraph/bothfragment delivery not met."},
    {"case": "G1-E04", "unit_id": "dgm/ordinary_paragraph--texts-648", "original_content_math_meanings_pass": True, "original_full_delivery_pass": True, "reason": "All5 literalcode tokens,bindings/nodeattributions and23.3%/40.5% preserved inline; no additionaltypedsegment requirement."},
    {"case": "WikiSkill362", "unit_id": "wikiskill/ordinary_paragraph--texts-362", "original_content_math_meanings_pass": True, "original_full_delivery_pass": True, "reason": "Complete lead-in/opening sentence and remainingprose/math retained."},
]
evidence = [reference(contract_path), reference(OUT / "prior-review-reference.json")]
evidence += [reference(BASE / "api" / p / "raw-doctags.txt") for p in raw]
evidence += [reference(BASE / "documents" / s / f) for s in docs for f in ("document.json", "document.md")]
result_path = OUT / "results.json"
completed_at = json.loads(result_path.read_text())["completed_at_utc"] if result_path.exists() else datetime.datetime.now(datetime.timezone.utc).isoformat()
result = {
    "format": "g2-official-fullpage-independent-source-review-v1", "completed_at_utc": completed_at,
    "frozen_source_contract_unchanged": True, "holdout_reads": 0, "reviewer_model_calls": 0, "response_repairs": 0, "candidate_reruns": 0,
    "method": "Whole-target manual comparison of all41units against pre-outputsourcecontract; rawDocTags,officialdocument andstockMarkdown inspected separately. Asserted output identities and named critical observations. No source-onlyoracle/modelinput overlap.",
    "summary": {
        "selected_source_units": 41, "source_clear_units": 41, "attempted_units": 41, "technical_missing_outputs": 0,
        "raw_source_fidelity_counts": counts,
        "raw_counts_scope": "33pass/2minor/6material is a new full-source rawtranscription rubric, not the priorcustomtyped25/5/6 and not CanonicalAcceptance. Fourmaterialcases are omittedsourceequationlabels; two are substantive identifier/codechanges.",
        "by_source": {s: {"units": sum(x["source"] == s for x in units), "raw_source_fidelity_counts": dict(collections.Counter(x["raw_source_fidelity_status"] for x in units if x["source"] == s))} for s in docs},
        "F13_required_expression_delivery": {"applicable_units": 18, "fully_delivered_units": 4, "counting_note": "Case-level full expression/presentation incl.sourceequationlabel; not a formulaOCRaccuracy metric. Failures include missingLaTeX roles,partialexpressions,officialparserloss,missinglabels andcrosspageassembly."},
        "F14_content_and_block_delivery": {"applicable_units": 7, "passed_units": 6, "failed_units": 1, "counting_note": "Overlappingtask slices cannot be summed. Sourcebboxdelivery not part of this content/block subtotal; invalidgeometry separately blocksadoption."},
        "protected_original_positives": {"original_content_math_meanings_preserved": 4, "original_full_delivery_preserved": 2, "required_total": 4},
        "previously_unprepared_units": {"units": 5, "all_attempted": True, "raw_source_fidelity_counts": dict(collections.Counter(x["raw_source_fidelity_status"] for x in units if not x["prior_prepared"])), "note": "FourSEALdisplayequationcoremathrecoveredbutallnumberlabelsomitted; nativeparagraph/titlemergecorrectlyseparatedwithminortwo-wordomission. No5/5productionpassclaim."},
        "units_with_any_available_inferred_box_outside_page_bounds": sum(not x["all_available_inferred_boxes_inside_page_bounds"] for x in units),
        "units_with_missing_item_provenance": sum(not x["all_matched_items_have_provenance"] for x in units),
        "all_unit_coarse_page_associations_recoverable_from_input_order": True,
        "source_bbox_fidelity_proven": False, "whole_candidate_adoptable": False, "CanonicalAcceptance": False, "G2_passed": False,
        "historical25pass5minor6material_unchanged": True,
    },
    "protected_positives": anchors, "saved_evidence_redaction_falsepositives": redactions,
    "supplemental_collateral_findings": [
        "SEALAlgorithm1 body outside41selectedunits is readable but sourceindex/subscripts flatten and extra set appears in Generate self-edit set; no comprehensivealgorithmgrade claimed.",
        "WikiSkillp22 tables/captions outside41selectedunits include mathematical LaTeX strings in plain tablecells/caption; nofullpagetableF13passclaim.",
        "Bold/italic tags inordinaryprose areflattened byofficialparser; sourceheading associations mostly retained but nofullpageheading/ordercertification.",
    ],
    "evidence_refs": evidence, "units": units,
    "limits": ["Fixed41selectedunits across8fullpages,notallpageinventory orindependentvalidation.", "Rawmathematicalmeaning review may read XML entities asmarkup; officialdeliveredLaTeX is assessed asactuallysaved,withoutunescapingrepair.", "Modelbboxcoordinates areinferred; boundschecks cannotprove correctlocalization. Existinginputorder sidecar onlycoarsephysicalpageassociation.", "No companyQwen3/GPU/highfrequencyload/holdoutvalidation; nocausalmodelaccuracycomparison topriorcrops."]
}
if result_path.exists():
    assert json.loads(result_path.read_text()) == result, "Frozen review differs; do not overwrite."
else:
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
assert all(reference(ROOT / entry["path"]) == entry for entry in evidence)
print(json.dumps({"result": reference(result_path), "summary": result["summary"], "redactions": redactions}, ensure_ascii=False, indent=2))
