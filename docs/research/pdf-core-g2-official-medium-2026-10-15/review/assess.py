"""Assert and freeze the independent medium-effort review, without changing outputs."""
import collections
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "docs/research/pdf-core-g2-official-medium-2026-10-15"
OUT = BASE / "review"
LOW = ROOT / "docs/research/pdf-core-g2-official-method-2026-10-15"


def ref(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


contract_path = OUT / "contract.json"
assert ref(contract_path)["sha256"] == "22ee81e79db28cf07d14ddd1f53269aada08d8b6480633ef67046a3e955777f2"
contract = json.loads(contract_path.read_text())
low_path = LOW / "review/results.json"
assert ref(low_path)["sha256"] == "01840c109b117763b5c46ea82729150d4f9a19911bb3d5ee33959deca05068c9"
low = json.loads(low_path.read_text())
docs = {s: json.loads((BASE / "documents" / s / "document.json").read_text()) for s in ("wikiskill", "dgm", "seal", "controls")}
markdown = {s: (BASE / "documents" / s / "document.md").read_text() for s in docs}
raw = {p.parent.name: p.read_text() for p in sorted((BASE / "api").glob("*/raw-doctags.txt"))}
assert len(raw) == 8
mapping = {
    "wikiskill": {357: [5, 6, 9], 361: list(range(11, 16)), 362: list(range(16, 21)), 363: list(range(21, 34)), 366: [36], 367: [37, 38, 39], 368: [40, 41, 42, 45]},
    "dgm": {646: [0], 648: list(range(2, 13)), 649: [13], 650: [14], 651: [15], 652: [16]},
    "seal": {21: [7, 9], 23: [10], 24: [11], 25: [12], 26: [13], 28: [15], 30: list(range(17, 32)) + list(range(33, 44)), 32: list(range(44, 53)), 45: [70], 46: [72, 73, 74], 47: [75, 76, 77], 49: list(range(79, 92)), 52: list(range(94, 111)), 53: [111], 33: [53], 34: list(range(54, 71)) + [71], 48: [78], 50: [92], 51: [93]},
    "controls": {0: [8], 1: [10], 2: [12], 1001: [1], 4: [4, 5, 6], 12: [14], 13: [14], 14: [15, 16], 15: [17]},
}
f13 = {"wikiskill": {361, 362, 363}, "dgm": set(), "seal": {30, 32, 33, 34, 46, 47, 48, 49, 50, 51, 52}, "controls": {0, 1, 2, 4}}
f13_pass = {("seal", 33), ("seal", 48), ("seal", 50), ("controls", 0), ("controls", 1), ("controls", 4)}
f14 = {"wikiskill": set(), "dgm": {646, 648, 650, 652}, "seal": set(), "controls": {12, 13, 14}}
f14_fail = {("dgm", 646), ("controls", 13), ("controls", 14)}
material = {("dgm", 646), ("seal", 30), ("seal", 32)}
minor = {("seal", 25), ("seal", 34)}
notes = {
    ("wikiskill", 357): "Complete words across20/21; lead-in is now a section_header rather than ordinary paragraph, and body remains split acrosspages. Content pass, original paragraph-role delivery fails.",
    ("wikiskill", 361): "All prose, subset/set subscripts and iterationk now present as math in raw; nested text/inline causes parser to detach both math expressions as root display blocks, losing child provenance. F13 remains incomplete.",
    ("wikiskill", 362): "Complete opening sentence and all prose/formula meanings retained. Original opening-omission positive passes, but two math expressions become detached displays with no provenance, a fullF13 regression versus low.",
    ("wikiskill", 363): "All6 required math occurrences now emitted in raw; meanings/quantifiers and full prose preserved. Nested text/inline becomes root displays, p &lt;0.05 stays literalentity; E14 originalinline/fullparagraph delivery still fails.",
    ("wikiskill", 366): "Complete Trace2Skill paragraph and author/year/pipeline retained; redundant nested text did not remove its single text body.",
    ("wikiskill", 367): "Complete EvoSkill prose and SKILL.md literal retained in raw. Official parser turns raw inlinecode SKILL.md into detached root codeblock, splitting source paragraph; content pass with final structure loss.",
    ("wikiskill", 368): "ReflACT identifier corrected versus low, six-stage expansion and complete remaining prose retained. Raw separate text elements and official rootitems split original paragraph, in addition to crosspage split.",
    ("dgm", 646): "Material diff changes remain: test_stats→test_state, removed test_stats line becomes '- )', attempt_num+1→len(attempts)+1, Errors log becomes len(test_state.get('errors',[])), ===→--- and TestSuccess line omitted; source indentation changed. Some tie-breaktext recovers versus low, insufficient source fidelity.",
    ("dgm", 648): "All five inlinecode tokens now typed code and correctly preserved by parser; full prose, node6/node24 bindings,23.3%/40.5% intact. Original E04 passes without requiring typedJSON.",
    ("dgm", 649): "Exact node6 label retained as its separate source block.",
    ("dgm", 650): "Both full instruction paragraphs and exactliteralnames/uniqueness/no-write conditions retained; printerwrap arrows retained. Delivered as separate ordinary text block rather than monospacedcode; formatting difference recorded, native code label not blindly imposed as F14 requirement.",
    ("dgm", 651): "Exact node24 label retained as its separate source block.",
    ("dgm", 652): "Complete editor/atomic/contextpreservation instructions retained, printerwrap arrows retained. Ordinarytext block loses source monospace presentation but coherent source block/content remains; no executablecode is inferred.",
    ("seal", 21): "Complete KnowledgeUpdating prose across2/3 retained; typography variants allowed. Official two root paragraphs remain split at or/otheroutputformats.",
    ("seal", 23): "Full Test-TimeTraining prose retained; straight/curly apostrophes are allowed.",
    ("seal", 24): "Full ReinforcementLearningforLLMs prose retained, including self-edit-generation distinction.",
    ("seal", 25): "Same minor punctuation/orthographic variants as low: comma after Schmidhuber[46] becomes period and parametrize→parameterize. All substantive meaning/references retained.",
    ("seal", 26): "Complete SelfImprovement paragraph/citations retained; apostrophe normalization allowed.",
    ("seal", 28): "Complete two-loopframework prose retained; plainstandaloneSE is not a new productfailure.",
    ("seal", 30): "NEW materialraw error: source LM_theta becomes L_M, losingtheta and changing symbolattachment. Other prose/eleven originalmath roles retained in meaning except this occurrence. P3 is validinlinegroup, but p4 nestedinline becomes detached rootdisplay/text items withoutprovenance; onecrosspageparagraph still absent. E13 content and delivery regress.",
    ("seal", 32): "NEW materialraw error: source LM_theta-prime becomes LM_theta_t. This changes adaptedparameter to indexedcurrentparameter; not typography. Nestedinline also becomes detached rootdisplays and missingchildprovenance.",
    ("seal", 45): "Complete aresampledfrom...currentmodel suffix occurs once as end of paragraph fragment70. It has no own parsedprovenance because nestedinline group was flattened; input/requestpageassociation available only through evaluator/rawpage matching.",
    ("seal", 46): "Complete GRPO/PPO/ReST prose and correct ReST^EM rawmath preserved. Official nestedinline parsing detaches formula into displayblock withmissingprovenance; inlineF13 fails.",
    ("seal", 47): "Complete EMprocedure prose; raw ReST outside formula plus orphan ^EM retains visible meaning but parser turns ^EM into detacheddisplay, not usable original inlineexpression.",
    ("seal", 49): "Complete prose and all6 mathematical expressions correct inraw; officialparser detaches them into displays and omits childprovenance, breaking inline F13 despite sourcecontent improvement.",
    ("seal", 52): "Full prose and all8 required mathematical expressions retained inraw; official nestedinline parsing produces detached display/text blocks withmissingprovenance. F13 fails.",
    ("seal", 53): "Complete teacher-student paragraph retained in one parsedtext item.",
    ("seal", 33): "Formula1 nestedexpectations/distributions/negative/reward and source tag1 now complete inraw andparsed. Recovers low missinglabel; inferredbox invalid separately.",
    ("seal", 34): "Source paragraph/title correctlyseparated, entire substantiveleftcolumnprose plus correcttheta/thetaprime/old/current math present. Same minor omission of 'of this'. Nestedinline yields many rootdisplays; title is separatecaption, source role distinction retained; F13 fails.",
    ("seal", 48): "Formula2 cases1/0,condition,rewardargs andtag2 now complete; literalalignment& preserved correctlyinparsedLaTeX rather than &amp;. Footnote2 association retains surroundingfootnote context. Recoverslowlabel/entityloss.",
    ("seal", 50): "Formula3 negative1/NM,i/jsums,r_ij,gradient/conditionalselfedit andtag3 completeinraw/parsed; recoverslowlabelomission.",
    ("seal", 51): "Rawformula4 includes complete i/j/ssums,historycondition y_<s andtag4. Officialparser treats literal <s asmarkup and TRUNCATES formulaafter '\\mid y_{', losingrest ofcondition, C_i andtag4. Rawsourcepass, parsedcontent/F13failure; no posthocunescape/parserrepair.",
    ("controls", 0): "Matrix M,2x2signs/entries correct inraw andparsed displayLaTeX.",
    ("controls", 1): "Fraction g(x)=1/(x+1) correct inraw andparsed displayLaTeX.",
    ("controls", 2): "RawXMLentityencoded piecewise preservesmeaning aftermarkup interpretation. OfficialparsedLaTeX leaves &amp; and &lt; literally; casesalignment/strictnegativecondition unusableasdelivered, newF13regressionversuslow.",
    ("controls", 1001): "Complete syntheticfixture disclaimer retained.",
    ("controls", 4): "Whole y=x^2+1 expression now inlineLaTeX, fullsentencecorrect; recoverslowpartialexpressiondelivery.",
    ("controls", 12): "Comment retainedonce asfirstline ofcombinedcodeblock; sourcecommentunitcontent/F14 passes. Bodyfailure separatelyassignedto13.",
    ("controls", 13): "RawXML &lt;= conveys correctsourceoperator; officialparser leaves literal &lt;= incode/Markdown. Remaining sixlines/indent0/4/4/8/0/4 correct, but executableoperatorcontent corruptedasdelivered; newF14regressionversuslow.",
    ("controls", 14): "Rawinlinecode items[i] &lt;= limit is decodedasintendedmarkup byreader; officialparser leaves literal &lt;= insidebackticks. Correctinlineposition but deliveredoperatorwrong; newF14regressionversuslow.",
    ("controls", 15): "Complete sourcefaithfulness sentence and[1] reference retained.",
}

units = []
for source_unit in contract["units"]:
    s = source_unit["source"]
    n = int(source_unit["native_target_refs"][0].split("/")[-1])
    if s == "controls" and n == 1 and "paragraph" in source_unit["job_id"]:
        n = 1001
    key = (s, n)
    items = [docs[s]["texts"][i] for i in mapping[s][n]]
    provenance = [p for x in items for p in x.get("prov", [])]
    physical = sorted(p["physical_page_1based"] for p in contract["scope"]["page_manifest"] if p["source"] == s)
    valid = True
    for p in provenance:
        box = p["bbox"]
        size = docs[s]["pages"][str(p["page_no"])]["size"]
        valid &= 0 <= box["l"] <= box["r"] <= size["width"] and 0 <= box["t"] <= box["b"] <= size["height"]
    available_pages = sorted({physical[p["page_no"] - 1] for p in provenance})
    assert set(available_pages) <= set(source_unit["physical_pages_1based"])
    units.append({
        "unit_id": source_unit["unit_id"], "source": s, "job_id": source_unit["job_id"], "prior_prepared": source_unit["prior_prepared"],
        "executed": True, "source_clear": True, "source_ambiguous": False,
        "raw_source_fidelity_status": "material" if key in material else "minor" if key in minor else "pass",
        "raw_target_content_complete_under_allowed_minor_equivalence": key not in material,
        "raw_source_equation_label_present": True if s == "seal" and n in {33, 48, 50, 51} else None,
        "parsed_content_introduced_material_loss": key in {("seal", 51), ("controls", 13), ("controls", 14)},
        "parsed_item_refs": [x["self_ref"] for x in items],
        "parsed_formula_item_count": sum(x["label"] == "formula" for x in items),
        "expected_physical_pages": source_unit["physical_pages_1based"],
        "matched_output_physical_pages_available_in_native_provenance": available_pages,
        "raw_request_page_matching_recovers_coarse_page_association": True,
        "all_matched_items_have_provenance": all(x.get("prov") for x in items),
        "all_available_inferred_boxes_inside_page_bounds": bool(valid) if provenance else None,
        "inferred_boxes_are_ground_truth": False, "page_bounds_pass_proves_correct_localization": False,
        "F13_applicable": n in f13[s],
        "F13_complete_source_expression_and_required_presentation_delivered": key in f13_pass if n in f13[s] else None,
        "F14_applicable": n in f14[s],
        "F14_content_and_block_delivery_pass": key not in f14_fail if n in f14[s] else None,
        "original_single_logical_paragraph_preserved": False if key in {("wikiskill", 357), ("wikiskill", 361), ("wikiskill", 362), ("wikiskill", 363), ("wikiskill", 367), ("wikiskill", 368), ("seal", 21), ("seal", 30), ("seal", 32), ("seal", 34), ("seal", 46), ("seal", 47), ("seal", 49), ("seal", 52)} else None,
        "custom_typed_JSON_contract_applies": False, "findings": [notes[key]],
    })

assert len(units) == 41 and len({x["unit_id"] for x in units}) == 41
counts = dict(collections.Counter(x["raw_source_fidelity_status"] for x in units))
assert counts == {"pass": 36, "material": 3, "minor": 2}, counts
assert sum(x["F13_applicable"] for x in units) == 18
assert sum(x["F13_complete_source_expression_and_required_presentation_delivered"] is True for x in units) == 6
assert sum(x["F14_content_and_block_delivery_pass"] is True for x in units) == 4
assert "ReflACT" in raw["wikiskill-p21"]
assert raw["wikiskill-p21"].split("We determine", 1)[1].split("</inline>", 1)[0].count("<formula>") == 6
assert docs["seal"]["texts"][20]["text"] == "L_M"
assert docs["seal"]["texts"][49]["text"] == r"\mathrm{LM}_{\theta_t}"
assert "attempt_number=len(attempts) + 1" in docs["dgm"]["texts"][0]["text"]
assert docs["seal"]["texts"][93]["text"].endswith(r"\mid y_{")
assert r"\tag{4}" in raw["seal-p4"] and r"\tag{4}" not in docs["seal"]["texts"][93]["text"]
assert "if x &lt;= limit:" in docs["controls"]["texts"][14]["text"]
assert "items[i] &lt;= limit" == docs["controls"]["texts"][16]["text"]
assert "&amp;" in docs["controls"]["texts"][12]["text"]
assert docs["controls"]["texts"][14]["text"].splitlines()[0] == "# keep the boundary and block nesting"
assert [len(line) - len(line.lstrip()) for line in docs["controls"]["texts"][14]["text"].splitlines()[1:]] == [0, 4, 4, 8, 0, 4]

redactions = []
for page, text in raw.items():
    if "[REDACTED]" in text:
        at = text.index("[REDACTED]")
        redactions.append({"page": page, "context": text[max(0, at - 65):at + 90], "selected41_scope_affected": False, "attribution": "Existing credential scrub falsepositive on task-specific; savedrawmutation, not model error; actualoriginal independently available inliveparsed doc. No rawrestoration."})
assert len(redactions) == 1 and redactions[0]["page"] == "seal-p2"
assert "task-specific data augmentation" in markdown["seal"]

paired = []
low_units = {x["unit_id"]: x for x in low["units"]}
for x in units:
    previous = low_units[x["unit_id"]]
    paired.append({"unit_id": x["unit_id"], "raw_low": previous["raw_source_fidelity_status"], "raw_medium": x["raw_source_fidelity_status"], "F13_low": previous["F13_complete_source_expression_and_required_presentation_delivered"], "F13_medium": x["F13_complete_source_expression_and_required_presentation_delivered"], "F14_low": previous["F14_content_and_block_delivery_pass"], "F14_medium": x["F14_content_and_block_delivery_pass"], "notes": x["findings"]})
anchors = [
    {"case": "G1-E14", "unit_id": "wikiskill/ordinary_paragraph--texts-363", "original_content_math_meanings_pass": True, "original_full_delivery_pass": False, "reason": "Raw6/6math recovered, but parsedrootdisplays/entityliteral/provenancefail originalinlineparagraph delivery."},
    {"case": "G1-E13", "unit_id": "seal/ordinary_paragraph--texts-30", "original_content_math_meanings_pass": False, "original_full_delivery_pass": False, "reason": "RawLM_theta→L_M materialerror; crosspageparagraph/someinline/provenance alsofail."},
    {"case": "G1-E04", "unit_id": "dgm/ordinary_paragraph--texts-648", "original_content_math_meanings_pass": True, "original_full_delivery_pass": True, "reason": "All5inlinecode tokens/bindings/nodeperformances retained, parserproperinlinegroup."},
    {"case": "WikiSkill362", "unit_id": "wikiskill/ordinary_paragraph--texts-362", "original_content_math_meanings_pass": True, "original_full_delivery_pass": True, "reason": "Original opening-omission boundedcriterion retained. FulltargetF13 nowfails separately; boundedpositive is notwholeparagraphF13approval."},
]
evidence = [ref(contract_path), ref(low_path)] + [ref(BASE / "api" / p / "raw-doctags.txt") for p in raw] + [ref(BASE / "documents" / s / f) for s in docs for f in ("document.json", "document.md")]
path = OUT / "results.json"
completed_at = json.loads(path.read_text())["completed_at_utc"] if path.exists() else datetime.datetime.now(datetime.timezone.utc).isoformat()
result = {
    "format": "g2-official-medium-independent-source-review-v1", "completed_at_utc": completed_at,
    "frozen_source_contract_unchanged": True, "same41unit_contract_as_low": True,
    "holdout_reads": 0, "reviewer_model_calls": 0, "response_repairs": 0, "candidate_reruns": 0,
    "method": "Manualwhole-source review ofall41fixedunits, samepreoutputoracle/equivalences. RawXMLentities interpretedasmarkup forcontentassessment, butactualsavedparsedcode/LaTeX judgedwithoutunescapingrepair. Priorlowrunispairedconfigurationreference,notholdout.",
    "summary": {
        "selected_source_units": 41, "source_clear_units": 41, "attempted_units": 41, "technical_missing_outputs": 0,
        "raw_source_fidelity_counts": counts,
        "raw_counts_scope": "36pass/2minor/3material is rawsourcecontent,nottotaldeliveryaccuracy. Newmaterialerrors areSEAL30/32andpersistentDGM646; parserintroducesadditionaldeliveredlosses.",
        "by_source": {s: {"units": sum(x["source"] == s for x in units), "raw_source_fidelity_counts": dict(collections.Counter(x["raw_source_fidelity_status"] for x in units if x["source"] == s))} for s in docs},
        "F13_required_expression_delivery": {"applicable_units": 18, "fully_delivered_units": 6, "low_fully_delivered_units": 4, "new_regression_units": [x["unit_id"] for x in paired if x["F13_low"] is True and x["F13_medium"] is False], "recovered_units": [x["unit_id"] for x in paired if x["F13_low"] is False and x["F13_medium"] is True], "note": "Taskslice/integrationdelivery,notOCRaccuracy. Materialregressionscannotbeoffsetbypooledcountgain."},
        "F14_content_and_block_delivery": {"applicable_units": 7, "passed_units": 4, "low_passed_units": 6, "new_regression_units": [x["unit_id"] for x in paired if x["F14_low"] is True and x["F14_medium"] is False], "note": "Geometrynotincluded; sourcequoted-instructionproseordinaryblockformatlossnamedseparately,nativecodelabelnotnewgate."},
        "protected_original_positives": {"original_content_math_meanings_preserved": 3, "original_full_delivery_preserved": 2, "required_total": 4, "note": "Wiki362originalpositiveisopening-omissionboundedcheck; itsfullF13nowfails. E13newrawmathematicalerrorisrealregression."},
        "previously_unprepared_units": {"units": 5, "all_attempted": True, "raw_source_fidelity_counts": dict(collections.Counter(x["raw_source_fidelity_status"] for x in units if not x["prior_prepared"])), "F13_fully_delivered_units": 3, "note": "All4displaylabelsrecoveredinraw,butformula4truncatedbyofficialparser; paragraph/titlecorrectlyseparatedwithsame2wordomission/inlinefailure. No5/5fullsuccessclaim."},
        "units_with_any_available_inferred_box_outside_page_bounds": sum(x["all_available_inferred_boxes_inside_page_bounds"] is False for x in units),
        "units_with_missing_item_provenance": sum(not x["all_matched_items_have_provenance"] for x in units),
        "units_with_no_available_native_item_page_provenance": sum(not x["matched_output_physical_pages_available_in_native_provenance"] for x in units),
        "source_bbox_fidelity_proven": False, "whole_candidate_adoptable": False, "CanonicalAcceptance": False, "G2_passed": False,
        "development_budget_consumed": "third/lastregisteredconfiguration; thisreviewdoesnotauthorizefurthersearch/holdout",
    },
    "protected_positives": anchors, "saved_evidence_redaction_falsepositives": redactions,
    "paired_low_medium_units": paired, "evidence_refs": evidence, "units": units,
    "supplemental_collateral_findings": ["WikiSkillp22formula/tablecontentoutside41scopewasnotfullyscored; nopagewidequalityclaim.", "SEALAlgorithm1bodyoutside41scopeisrenderedaslistitemswithliteralbrmarkup/subscriptvariants; noalgorithmfidelityapproval.", "WikiSkill357lead-inpromotedtoheadingand367SKILL.mdbecomesdetachedcodeblock; sourceblockpresentationlosskeptvisible."],
    "limits": ["Same8exposedpages/41selectedunits,notindependentvalidationorallpageinventory.", "TemporaryOpenAImodelnotQwen3identity/performanceevidence; companyinformationnotrequiredtocompletethiscomparison.", "Nobboxrepair,HTMLunescape,paragraphjoinoranswerpatchapplied.", "NoGPU/highfrequencyload/holdoutvalidation; nosingleaggregateaccuracyratecanjustifyadoptionwithnewmaterialregressions."]
}
if path.exists():
    assert json.loads(path.read_text()) == result, "Frozenreviewdiffers; do notoverwrite."
else:
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
assert all(ref(ROOT / x["path"]) == x for x in evidence)
print(json.dumps({"result": ref(path), "summary": result["summary"]}, ensure_ascii=False, indent=2))
