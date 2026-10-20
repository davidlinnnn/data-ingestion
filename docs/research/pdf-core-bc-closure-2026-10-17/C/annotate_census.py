"""Encode this round's source-only visual review; these are evaluator data."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
pages = json.loads((ROOT / "source-pages.json").read_text())
by_id = {p["page_id"]: p for p in pages}
rows = []


def figure(page, name, kind, region, caption, meaning, refs=(), limits=(), cross=()):
    row = {
        "source_group_id": f"{page}-{name}", "page_id": page,
        "source_id": by_id[page]["source_id"],
        "source_sha256": by_id[page]["source_sha256"],
        "physical_page_1based": by_id[page]["physical_page_1based"],
        "source_image": by_id[page]["image"],
        "source_image_sha256": by_id[page]["image_sha256"],
        "visual_kind": kind, "location_on_page": region,
        "locator_precision": "visual region plus printed label; no producer bbox",
        "original_caption": {"locator": caption, "status": "source_seen" if caption else "no_separate_caption_seen",
                             "delivery": "preserve source text separately; never replace by generated description"},
        "presence_review": "confirmed", "caption_association": "confirmed" if caption else "not_applicable",
        "required_meaning": meaning, "existing_source_oracle_refs": list(refs),
        "uncompleted_semantic_annotation": list(limits),
        "cross_component_responsibility": list(cross),
        "required_work": {"source_image": "required", "image_ocr": "required_outcome_including_no_text_or_failed",
                          "description": "not_applicable_brand_decoration" if kind == "brand_mark" else "required",
                          "chart_assessment": "required_until_generically_resolved",
                          "chart_data": "required" if kind == "chart" else "not_applicable_by_source_review",
                          "classification": "optional_preferred"},
        "producer_owner": None, "same_revision_image_key": None,
        "delivery_status": "not_newly_run", "evaluation_only": True,
    }
    rows.append(row)
    by_id[page]["figures"].append(row["source_group_id"])


figure("SRC01-p01", "brand", "brand_mark", "top-left Google Research mark", None,
       ["Retain source mark and visible Google Research text; no additional semantic description is needed for branding."],
       limits=["The source review justifies description N/A; no production classifier exemption has been qualified."])
figure("SRC01-p01", "figure1", "chart", "lower half, before Figure 1 caption", "Figure 1, immediately below plot",
       ["Accuracy (%) over four named inference models; No skill, EvoSkill, SkillOpt and WikiSkill series remain associated with their lines.",
        "Sixteen plotted series-position observations; values are unprinted estimates, with a 30% to 75% displayed axis.",
        "WikiSkill is above the three alternatives at every shown model; retain the stated cross-model condition."],
       limits=["Sixteen per-point geometry values and tolerance fixtures not frozen this round; no chart inference evidence for this figure."])
figure("SRC01-p04", "figure2", "diagram", "upper third, three layers above four-step workflow", "Figure 2, below workflow",
       ["Preserve Skill/Wiki/Raw layers, their paths and reversible/never-reset/write-once distinctions.",
        "Preserve four numbered steps, directed trace/skill/wiki paths, better-only update and return loop."], ["G1-S05"])
figure("SRC01-p12", "figure3", "diagram", "upper half, persistent wiki left and active skill right", "Figure 3, below diagram",
       ["Persistent Wiki Layer wiki/ and Active Skill Layer skills/; skill-impact.md, logs.md and patterns feed the skill update.",
        "Iteration 0 proposal rejected; iteration 1 break-repetition-loop accepted; iteration 4 update accepted.",
        "Prior rejection explains rationale; accepted proposal updates skill; chronological logs record decisions; documented patterns motivate updates.",
        "Preserve the visible PURPOSE.md/SKILL.md trigger, rule/anti-pattern associations rather than replacing with caption-only prose."],
       limits=["Complete line-level OCR transcript not frozen; source file snippets require A/F14 review if treated as code."],
       cross=["A owns any required code/literal reconstruction; C OCR/description does not qualify F14."])
figure("SRC11-p02", "figure1", "diagram", "top, RL outer-loop graphic including title", "Figure 1: Overview of SEAL, immediately below graphic",
       ["LM generates candidate self-edits; each is optimized, tested and rewarded; RL data drive a policy update.",
        "Retain all three candidate branches, test/answer status, reward association and outer loop iteration t title."],
       limits=["Full mathematical glyph transcription remains A responsibility, including title t outside prior picture envelope."],
       cross=["A/F13 mathematical text in title and graphic; C must preserve image/caption and describe the process."])
figure("SRC06-p08", "figure6", "chart", "upper-left two bar panels", "Figure 6, below panels",
       ["Two panels: Llama-3.1-8B-Instruct and GPT-4o-mini; F1/B1/J and Before RL/PPO/GRPO identities retained.",
        "Score in %; do not interpret cumulative colored display as independent additions without confirming chart convention."],
       limits=["Exact bar/stack representation and all source observation values require focused annotation; chart oracle not frozen."])
figure("SRC06-p08", "figure7", "chart", "upper-right two training curves", "Figure 7, immediately below curves",
       ["PPO and GRPO training reward by training step for Llama-3.1-8B-Instruct and Qwen-2.5-7B-Instruct.",
        "Retain condition, initial convergence distinction and similar final reward; do not invent exact unprinted samples."],
       limits=["Dense continuous curves need predeclared sampling/representation before a finite numeric denominator can be frozen."])
figure("SRC06-p08", "figure8", "chart", "right column, below Figure 7 caption, three scatter panels", "Figure 8, below scatter panels",
       ["Accuracy versus latency (s), panels F1/B1/J; Base, Base+Reranker and Memory-R1 (GRPO) with p50/p95 marker identities.",
        "Preserve accuracy/latency trade-off and method/percentile associations."],
       limits=["Small labels were inspected at 1.5x full-page render; exact percentile marker binding remains uncertain.",
               "Scatter numeric extraction is outside the registered F12 bar/line/pie scope; no new all-points numeric gate is introduced."])
rows[-1]["required_work"]["chart_data"] = "outside_registered_F12_scatter_numeric_scope"
rows[-1]["F12_numeric_scope"] = "not_required_by_current_bar_line_pie_contract"
figure("SRC03-p03", "screenshot", "screenshot", "central application screen, including banner and right menu", None,
       ["Application selection UI; source navigation and B5A personal statement link remain bound to displayed options.",
        "Full screenshot has additional banner, left and right menus and bottom instruction beyond selected S07 panel.",
        "Do not invent identities of photographed people or post-click outcomes."], ["G1-S07", "G1-O01", "G1-O05"],
       limits=["S07/O01 only annotate a selected panel, not full screenshot OCR/meaning; full-image transcript needs completion."])
figure("SRC04-p02", "figure1", "diagram", "top full-width timeline with model names, dates and logos", "Fig. 1, below timeline in raster image",
       ["Timeline of LLMs larger than 10B in recent years; years/month associations, branches and model names.",
        "Yellow marks open-source models; graphic logos are parts of this figure, not new independent canonical jobs."],
       limits=["Complete timeline node/edge/label oracle not frozen; source is raster-only, caption must remain source text."])
figure("SRC12-p02", "figure2", "diagram", "top three-stage branched flow", "Figure 2, immediately below flow",
       ["Success/error traces feed separate analysts; three patch paths merge into one evolved skill.",
        "Preserve addition versus edition, patch conditions and parallel/hierarchical merge; no invented feedback arrow."], ["G1-E10"],
       cross=["A owns required mathematical/literal fidelity; C figure meaning alone cannot satisfy F13/F14."])
figure("SRC13-p09", "figure4", "chart", "upper-right, two panels with bars and lines", "Figure 4, directly below two panels",
       ["All 30 printed (panel, series, k, value) observations, axes, condition and critical comparisons from G1-E11."], ["G1-E11"])
figure("SRC13-p09", "figure5", "chart", "lower-right, mixed grouped bars/line", "Figure 5, directly below plot",
       ["All 12 printed (memory mechanism, series, value) observations, truncated axis, sampling conditions and critical comparisons from G1-E12."], ["G1-E12"])
for name, region, oracle, meaning in [
    ("panelA", "upper-left printed bar chart", "G1-C03", "Two printed observations A=10%, B=20%; preserve axes and B>A."),
    ("panelB", "upper-right two crossing line series", "G1-C04", "Six estimated observations; preserve Blue/Orange, Step, percent axis, midpoint equality and endpoint order."),
    ("panelC", "lower-left log line chart", "G1-C05", "Three estimated observations; preserve log10 axis, 1/10/100 and factor-ten progression."),
    ("panelD", "lower-right pie chart", "G1-C06", "Two estimated sectors, A about25% and B about75%; preserve estimated flags/category identity and larger B."),
]:
    figure("SRC05-p02", name, "chart", region, None, [meaning], [oracle])
for page in ["SRC05-p07", "SRC05-p08"]:
    figure(page, "figure1", "screenshot", "central source-derived application selection panel", "Figure 1, directly below panel",
           ["Retain S07-like breadcrumb, headings, B5A link and selection instruction, with generated meaning separate from source caption.",
            "Preserve source native paragraph before, tail after and final instruction; page8 is rasterized but has the same semantic division."],
           ["G1-C12" if page.endswith("07") else "G1-C13"],
           limits=["Derived source context and image bytes differ from G1-S07 exact input; no exact-input API reuse claim."])

# These are visual responsibility fences, not a B accuracy oracle.
tables = {
    "SRC01-p08": ["Table 1"], "SRC01-p10": ["Table 2"], "SRC01-p11": ["Table 3"],
    "SRC01-p13": ["Table 4"], "SRC01-p20": ["Table 5", "Table 6"], "SRC01-p22": ["Table 7"],
    "SRC06-p08": ["Table 2"], "SRC07-p08": ["Table 2 (six panels)", "Table 3"],
    "SRC09-p17": ["Table 6", "Table 7"], "SRC08-p27": ["Table 12 (two panels)", "Table 13 first fragment"],
    "SRC08-p28": ["Table 13 continued"], "SRC08-p29": ["Table 13 continued"],
    "SRC02-p01": ["Untitled meeting-record table; visible fragment continues beyond selected page"],
}
wrappers = {"SRC02-p01": "full-page scan; text and table, not a semantic figure",
            "SRC04-p01": "full-page raster text", "SRC04-p02": "full-page raster text plus timeline",
            "SRC05-p03": "0-degree raster source text", "SRC05-p04": "90-degree source text",
            "SRC05-p05": "180-degree source text", "SRC05-p06": "270-degree source text",
            "SRC05-p08": "raster mixed page; contains one semantic screenshot plus page text"}
for p in pages:
    p["review_status"] = "visual_presence_and_caption_location_reviewed"
    p["review_evidence"] = [p["contact_sheet"]]
    if p["figures"]:
        p["review_evidence"].append(p["image"])
    p["semantic_figure_groups"] = len(p["figures"])
    p["table_source_locators_B"] = tables.get(p["page_id"], [])
    p["raster_page_wrapper"] = wrappers.get(p["page_id"])
    p["negative_C_presence"] = not p["figures"]
    p["scope_limit"] = "C figure presence/caption responsibility review; not full text/heading/A/B accuracy scoring"
assert len(pages) == 55 and len(rows) == 19
assert sum(r["visual_kind"] == "chart" for r in rows) == 10
assert sum(r["visual_kind"] == "brand_mark" for r in rows) == 1
assert len(wrappers) == 8
assert len({r["source_group_id"] for r in rows}) == len(rows)
result = {"format": "source-only-c-visual-census-v1", "role": "evaluator_only_exposed_DEV",
          "native_inventory_used_as_truth": False, "embedded_images_used_as_truth": False,
          "all_pages_visual_presence_reviewed": True, "page_count": 55,
          "logical_visual_groups_including_brand": len(rows), "informational_groups": 18,
          "chart_groups": 10, "registered_F12_chart_groups": 9,
          "scatter_F11_groups_numeric_scope_unregistered": 1, "raster_page_wrappers": 8,
          "full_semantic_oracles_frozen": False,
          "producer_jobs": None, "N_3": None,
          "pages": pages, "figures": rows}
(ROOT / "source-census.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k:v for k,v in result.items() if k not in {"pages", "figures"}}, ensure_ascii=False))
