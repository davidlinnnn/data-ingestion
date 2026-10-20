"""Offline evidence checks for three frozen-scope Granite-Docling CPU probes."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
REPO = HERE.parents[3]
VLM = ROUND / "vlm"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(text):
    # G1 allows line joining, this printed line-end split, and range-dash normalization.
    return re.sub(r"\s+", "", text.replace("re-\nsources", "resources").replace("–", "-"))


def paragraphs_preserved_and_adjacent(texts, expected):
    normalized = [normalize(t) for t in texts]
    return any(normalized[i:i + 2] == expected for i in range(len(normalized) - 1))


def formula_observations(text):
    # shortcut: this checks the frozen two-branch Eq2 only; use a LaTeX parser for other formulas.
    first = re.search(r"1\s*&(?P<condition>.*?)\\\\\s*0\s*&", text, re.S)
    return {
        "two_branches_with_otherwise": bool(first and "Otherwise" in text),
        "footnote_2_present_in_first_condition": bool(first and re.search(r"\b2\b", first["condition"])),
        "unbalanced_inline_dollar_delimiters": text.count("$") % 2 == 1,
        "literal_partial_closing_formula_tag": "</formula" in text and "</formula>" not in text,
    }


def main():
    registry_path = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
    registry = read(registry_path)
    observations = read(VLM / "observations.json")
    assert sha(registry_path) == observations["registry_sha256"] == "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
    assert sha(VLM / "probe.py") == observations["runner_sha256"]
    assert [o["case"] for o in observations["observations"]] == ["seal-eq2", "english-scan-p1", "skillopt-p8"]
    cases = {c["id"]: c for c in registry["cases"]}
    generation_checks = []
    for observation in observations["observations"]:
        name = observation["case"]
        out = VLM / name
        locator, method, generation = [read(out / f"{n}.json") for n in ["input", "method", "generation"]]
        assert observation["exit_code"] == 0 and observation["stopped"] is None
        assert observation["sampled_tree_peak_rss_bytes"] < observation["limit_bytes"]
        assert method["devices"] == ["cpu"] and method["dtypes"] == ["torch.float32"]
        assert method["torch_threads"] == 4 and method["interop_threads"] == 1
        assert method["revision"] == "982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe"
        assert sha(out / "input.png") == locator["input_sha256"]
        source = Path(locator["source_png"]) if "source_png" in locator else REPO / locator["source_pdf"]
        assert sha(source) == locator["sha256"]
        assert generation["generated_tokens"] == len(generation["generated_ids"])
        assert generation["last_token_is_eos"] and not generation["at_token_limit"]
        assert generation["generated_ids"][-1] == generation["eos_token_ids"] == 100257
        generation_checks.append({"case": name, "generated_tokens": generation["generated_tokens"],
                                  "eos": True, "token_limit_reached": False})
    assert read(VLM / "seal-eq2/input.json")["input_sha256"] == read(ROUND.parent / "pdf-core-g2-round2-2026-10-14/models/seal-eq2/input.json")["input_sha256"]

    expected = cases["G1-O03"]["details"]["expected"]
    lines = {x["id"]: x["text"] for x in expected["items"]}
    paragraphs = [normalize("\n".join(lines[key] for key in group)) for group in expected["paragraph_groups"]]
    document = read(VLM / "english-scan-p1/document.json")
    texts = [item["text"] for item in document["texts"]]
    assert paragraphs_preserved_and_adjacent(texts, paragraphs)
    assert not paragraphs_preserved_and_adjacent([texts[0], "In-context learning. Wrong-column insertion", *texts[1:]], paragraphs)
    assert not paragraphs_preserved_and_adjacent([texts[0], texts[1].replace("Section 3", "Section 9"), *texts[2:]], paragraphs)
    assert [normalize(t) for t in texts[:2]] == paragraphs
    assert texts[2] == "2 OVERVIEW" and texts[8].startswith("· In-context learning.")
    markdown = (VLM / "english-scan-p1/document.md").read_text()
    assert markdown.index(texts[0]) < markdown.index(texts[1]) < markdown.index("2 OVERVIEW") < markdown.index("In-context learning.")
    parser = read(VLM / "english-scan-p1/parser.json")
    assert parser["page_keys"] == [1] and not parser["parser_remap_applied"]
    formula = formula_observations((VLM / "seal-eq2/cleaned.txt").read_text())
    assert formula == {"two_branches_with_otherwise": True, "footnote_2_present_in_first_condition": False,
                       "unbalanced_inline_dollar_delimiters": True, "literal_partial_closing_formula_tag": True}
    assert not formula_observations(r"\begin{cases}1 & improves\end{cases}")["two_branches_with_otherwise"]
    assert formula_observations(r"\begin{cases}1 & performance^{2} \\ 0 & Otherwise\end{cases}")["footnote_2_present_in_first_condition"]
    assert not formula_observations(r"\begin{cases}1 & performance^{2} \\ 0 & Otherwise\end{cases}")["literal_partial_closing_formula_tag"]
    decode = read(HERE / "token-decode.json")
    for observation in decode["observations"]:
        path = HERE / observation["decoded_file"]
        assert sha(path) == observation["sha256"]
        assert observation["full_closing_tag_before_eos"]
        assert path.read_text().rstrip(decode["pad_token"]) == (VLM / observation["case"] / "output.txt").read_text()
    tables = read(VLM / "skillopt-p8/document.json")["tables"]
    assert len(tables) == 9
    assert [table["data"]["num_cols"] for table in tables[:6]] == [3] * 6
    assert all(not table["captions"] for table in tables[:6])
    assert cases["G1-T02"]["details"]["denominator"]["numeric_error_denominator"] == 84
    critical = read(HERE / "table-critical-review.json")
    assert len(critical["comparisons"]) == len(cases["G1-T02"]["details"]["critical_comparisons"]) == 8
    for actual, oracle in zip(critical["comparisons"], cases["G1-T02"]["details"]["critical_comparisons"]):
        assert actual["left"] == oracle["left"] and actual["right"] == oracle["right"]
        assert actual["operator"] == oracle["operator"] and actual["accepted"] is False
    crop = VLM / "table-crop/run"
    crop_input, crop_generation = read(crop / "input.json"), read(crop / "generation.json")
    assert sha(crop / "input.png") == crop_input["input_sha256"] == "e15d7737e1fd4dc28dde61fd7845dc00a59cda731a521a6a8bebc39b3a9dfc9a"
    assert crop_generation["generated_tokens"] == 435 and crop_generation["last_token_is_eos"]
    assert not crop_generation["at_token_limit"] and crop_generation["generated_ids"][-1] == 100257
    crop_tables = read(crop / "document.json")["tables"]
    assert len(crop_tables) == 1 and crop_tables[0]["data"]["num_cols"] == 9
    crop_critical = read(HERE / "table-crop-critical-review.json")
    assert len(crop_critical["comparisons"]) == 8
    for actual, oracle in zip(crop_critical["comparisons"], cases["G1-T02"]["details"]["critical_comparisons"]):
        assert actual["left"] == oracle["left"] and actual["right"] == oracle["right"]
        assert actual["operator"] == oracle["operator"] and actual["accepted"] is False
    result = {"execution": "offline_only_no_model_inference", "registry_and_runner_unchanged": True,
              "source_and_input_hash_checks": True, "generation": generation_checks,
              "english_selected_scope": {"paragraphs": 2, "source_lines": 16, "normalized_exact": True,
                                         "adjacent_before_right_column": True, "negative_checks": 2},
              "formula": formula, "complete_closing_tags_before_official_engine_rstrip": True,
              "table_critical_reviewed": 8, "table_critical_accepted": 0,
              "table_fixed_numeric_denominator": 84, "table_full_numeric_error_rate": None,
              "table_crop": {"unchanged_input_hash": True, "eos": True, "token_limit_reached": False,
                             "generated_tokens": 435, "critical_reviewed": 8, "critical_accepted": 0}}
    (HERE / "checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
