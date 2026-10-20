"""Offline G1 quality checks for temporary API JSON responses; never calls an API."""
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"


def normalized(text):
    assert isinstance(text, str)
    return re.sub(r"\s+", "", text)


def english_normalized(text):
    return normalized(text.replace("re-\nsources", "resources").replace("–", "-"))


def ocr_normalized(text):
    return normalized(text.translate(str.maketrans({"“": '"', "”": '"', "＂": '"'})))


def label(text):
    return normalized(text).casefold()


def ordered_substrings(text, expected):
    cursor, found = 0, []
    for item in expected:
        index = text.find(item, cursor)
        found.append(index)
        if index < 0:
            return False, found
        cursor = index + len(item)
    return True, found


def evaluate_ocr(output, oracle):
    text = ocr_normalized("\n".join(b["text"] for b in output["blocks"]))
    expected = [ocr_normalized(b["text"]) for b in oracle["expected"]["items"]]
    ordered, offsets = ordered_substrings(text, expected)
    return {"all_five_items_in_order": ordered, "offsets": offsets,
            "individual_exact_item_matches": [any(ocr_normalized(b["text"]) == item for b in output["blocks"]) for item in expected],
            "exact_selected_transcript_after_allowed_normalization": text == "".join(expected),
            "position_review": "manual; bbox presence alone does not establish source attribution",
            "simplified_traditional_conversion_applied": False}


def evaluate_english(output, oracle):
    expected = oracle["expected"]
    lines = {item["id"]: item["text"] for item in expected["items"]}
    paragraphs = [english_normalized("\n".join(lines[key] for key in group))
                  for group in expected["paragraph_groups"]]
    texts = [block["text"] for block in output["blocks"]]
    stream = english_normalized("\n".join(texts))
    adjacent = "".join(paragraphs) in stream
    return {"source_lines": 16, "each_complete_paragraph_present": [p in stream for p in paragraphs],
            "selected_paragraphs_contiguous_in_output_order": adjacent,
            "scope": "selected two paragraphs only; paragraph boundaries and source positions reviewed manually"}


def evaluate_formula(output, oracle):
    latex = output["latex"]
    first = re.search(r"1\s*&(?P<condition>.*?)\\\\\s*0\s*&", latex, re.S)
    markers = output["footnote_markers"]
    visible_marker = oracle["expected"]["footnote"]["marker"]
    braces = re.findall(r"(?<!\\)[{}]", latex)
    depth, balanced = 0, True
    for brace in braces:
        depth += 1 if brace == "{" else -1
        balanced &= depth >= 0
    return {"has_two_case_branches_in_expected_syntax": bool(first and re.search("otherwise", latex, re.I)),
            "equation_label_matches": str(output["equation_label"]).strip("() ") == oracle["expected"]["equation_number"],
            "visible_footnote_marker_listed": any(str(m["marker"]).strip("[]() ") == visible_marker for m in markers),
            "footnote_anchor_texts": [m["anchor_text"] for m in markers],
            "footnote_bodies_reported": output["footnote_bodies"],
            "balanced_unescaped_braces": balanced and depth == 0,
            "balanced_inline_dollars": len(re.findall(r"(?<!\\)\$", latex)) % 2 == 0,
            "partial_or_complete_xml_like_tags": re.findall(r"</?(?:formula|doctag)[^\n]*", latex),
            "semantic_status": "manual review required; syntax heuristics are not a formula equivalence proof",
            "footnote_body_delivery": "outside supplied crop; not tested; invented body would be unsupported"}


def panel_id(value):
    match = re.fullmatch(r"\(?([a-f])\)?", value.strip(), re.I)
    return match.group(1).casefold() if match else value


def decimal(value):
    try:
        result = Decimal(value)
        return result if result.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def evaluate_table(output, oracle):
    rows = {r["row_id"]: r["context"] for r in oracle["rows"]}
    expected = {}
    for point in oracle["expected_datapoints"]:
        context = rows[point["row_id"]]
        key = (context["panel"], label(context["setting"]), label(point["column_key"]))
        assert key not in expected
        expected[key] = point
    assert len(expected) == oracle["denominator"]["numeric_error_denominator"] == 84
    actual, header_issues, panel_counts = defaultdict(list), [], defaultdict(int)
    expected_panels = {p["panel_id"]: p for p in oracle["panels"]}
    expected_metrics = {label(h["key"]) for h in oracle["headers"] if h["key"] != "Setting"}
    for panel in output["panels"]:
        name = panel_id(panel["panel_label"])
        panel_counts[name] += 1
        columns = [label(c) for c in panel["columns"]]
        if len(columns) != len(set(columns)):
            header_issues.append({"panel": name, "issue": "duplicate column labels"})
        if set(columns) - {"setting"} != expected_metrics:
            header_issues.append({"panel": name, "issue": "metric header labels differ", "actual": panel["columns"]})
        if name not in expected_panels:
            header_issues.append({"panel": name, "issue": "unknown panel"})
        else:
            source_title = re.sub(r"^\([a-f]\)\s*", "", expected_panels[name]["title"])
            actual_title = re.sub(r"^\([a-f]\)\s*", "", panel["title"], flags=re.I)
            if label(source_title) != label(actual_title):
                header_issues.append({"panel": name, "issue": "panel title differs", "actual": panel["title"]})
        for row in panel["rows"]:
            for item in row["values"]:
                key = name, label(row["setting"]), label(item["column"])
                actual[key].append({"value": item["value"], "declared_column": label(item["column"]) in columns})
    duplicates = {p: n for p, n in panel_counts.items() if n != 1}
    points, accepted = [], {}
    for key, source in expected.items():
        observed = actual.get(key, [])
        valid = (len(observed) == 1 and observed[0]["declared_column"]
                 and decimal(observed[0]["value"]) == Decimal(source["decimal_value"])
                 and panel_counts[key[0]] == 1)
        accepted[source["id"]] = valid
        points.append({"id": source["id"], "binding": list(key), "expected": source["raw_value"],
                       "observed": observed, "correct_numeric_binding": valid,
                       "printed_value_exact": len(observed) == 1 and observed[0]["value"] == source["raw_value"]})
    extras = [{"binding": list(key), "observed": observed} for key, observed in actual.items() if key not in expected]
    critical = []
    points_by_id = {point["id"]: point for point in points}
    for comparison in oracle["critical_comparisons"]:
        left = points_by_id[comparison["left"]]["observed"]
        right = points_by_id[comparison["right"]]["observed"]
        relation = None
        if len(left) == len(right) == 1:
            a, b = decimal(left[0]["value"]), decimal(right[0]["value"])
            if a is not None and b is not None:
                relation = a > b if comparison["operator"] == ">" else a == b
        critical.append({**comparison, "source_values_and_bindings_preserved":
                         accepted[comparison["left"]] and accepted[comparison["right"]],
                         "observed_relation_holds": relation})
    errors = sum(not p["correct_numeric_binding"] for p in points)
    extra_count = sum(len(x["observed"]) for x in extras)
    return {"fixed_numeric_denominator": 84, "source_numeric_bindings_correct": 84 - errors,
            "printed_numeric_strings_exact": sum(p["printed_value_exact"] for p in points),
            "source_numeric_binding_errors": errors, "extra_numeric_observations": extra_count,
            "error_rate_including_unmatched_extras": (errors + extra_count) / 84,
            "panel_header_issues": header_issues, "duplicate_panels": duplicates,
            "caption": output["caption"], "conditions": output["conditions"],
            "caption_condition_semantics": "manual review required",
            "all_critical_numeric_bindings_preserved": all(c["source_values_and_bindings_preserved"] and c["observed_relation_holds"] for c in critical),
            "critical_comparisons": critical, "datapoints": points, "extra_bindings": extras,
            "counting_note": "Each expected key is scored once; unmatched output values add errors without increasing84. Caption/title/condition gate is separate."}


def self_check(cases):
    oracle = cases["G1-T02"]["details"]
    rows = {r["row_id"]: r for r in oracle["rows"]}
    candidate = {"caption": oracle["caption"]["text"], "conditions": oracle["conditions"], "panels": []}
    for source_panel in oracle["panels"]:
        name = source_panel["panel_id"]
        panel = {"panel_label": name, "title": source_panel["title"],
                 "columns": [h["key"] for h in oracle["headers"]], "rows": []}
        for source_row in rows.values():
            if source_row["context"]["panel"] == name:
                values = [{"column": p["column_key"], "value": p["raw_value"]} for p in oracle["expected_datapoints"]
                          if p["row_id"] == source_row["row_id"]]
                panel["rows"].append({"setting": source_row["context"]["setting"], "values": values})
        candidate["panels"].append(panel)
    assert evaluate_table(candidate, oracle)["source_numeric_bindings_correct"] == 84
    bad = deepcopy(candidate)
    bad["panels"][1]["rows"][3]["setting"] = "5"
    assert evaluate_table(bad, oracle)["source_numeric_bindings_correct"] < 84
    assert not evaluate_table(bad, oracle)["all_critical_numeric_bindings_preserved"]
    bad = deepcopy(candidate)
    bad["panels"][5]["rows"].append(deepcopy(bad["panels"][5]["rows"][1]))
    assert evaluate_table(bad, oracle)["source_numeric_binding_errors"] == 3
    bad = deepcopy(candidate)
    bad["panels"][0]["rows"][0]["values"].append({"column": "invented", "value": "9"})
    assert evaluate_table(bad, oracle)["extra_numeric_observations"] == 1
    bad = deepcopy(candidate)
    values = bad["panels"][0]["rows"][0]["values"]
    values[0]["column"], values[1]["column"] = values[1]["column"], values[0]["column"]
    assert evaluate_table(bad, oracle)["source_numeric_binding_errors"] == 2
    bad = deepcopy(candidate)
    bad["panels"][1]["rows"][3]["values"][0]["value"] = "87.0"
    assert evaluate_table(bad, oracle)["source_numeric_binding_errors"] == 1
    assert not evaluate_table(bad, oracle)["all_critical_numeric_bindings_preserved"]
    english = cases["G1-O03"]["details"]
    items = {i["id"]: i["text"] for i in english["expected"]["items"]}
    paragraphs = ["\n".join(items[k] for k in group) for group in english["expected"]["paragraph_groups"]]
    blocks = [{"text": text} for text in paragraphs]
    assert evaluate_english({"blocks": blocks}, english)["selected_paragraphs_contiguous_in_output_order"]
    blocks.insert(1, {"text": "In-context learning: inserted from the wrong column."})
    assert not evaluate_english({"blocks": blocks}, english)["selected_paragraphs_contiguous_in_output_order"]
    return {"table_negative_checks": 5, "english_negative_checks": 1,
            "synthetic_perfect_table_stays_in_memory_and_is_never_an_api_input": True}


if __name__ == "__main__":
    registry_sha256 = hashlib.sha256(REGISTRY.read_bytes()).hexdigest()
    assert registry_sha256 == "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
    cases = {c["id"]: c for c in json.loads(REGISTRY.read_text())["cases"]}
    checks = self_check(cases)
    if sys.argv[1:] == ["--self-check"]:
        print(json.dumps(checks, indent=2))
    else:
        assert not sys.argv[1:], "Use no arguments to score saved responses, or --self-check"
        tasks = [("nccu-panel", "G1-O01", evaluate_ocr), ("seal-eq2", "G1-E07", evaluate_formula),
                 ("english-scan-p1", "G1-O03", evaluate_english), ("skillopt-p8", "G1-T02", evaluate_table)]
        results = {}
        for name, case, evaluator in tasks:
            source = HERE.parent / name / "output.json"
            output = json.loads(source.read_text())
            results[name] = {"case": case, "output": str(source.relative_to(REPO)),
                             "output_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                             "evaluation": evaluator(output, cases[case]["details"])}
        result = {"execution": "offline_only", "candidate_scope": "Temporary GPT-6 Luna API; not company Qwen3 or full Docling integration",
                  "registry_sha256": registry_sha256,
                  "self_checks": checks, "cases": results}
        (HERE / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"self_checks": checks, "saved": str(HERE / "results.json")}, ensure_ascii=False, indent=2))
