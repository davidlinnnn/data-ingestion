import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest
import score


def test_auc_excludes_minor_and_uses_correct_positive():
    assert score.auc(["correct", "meaning_changed", "minor"], [0.8, 0.2, 0]) == 1
    assert score.auc(["correct", "meaning_changed"], [0.2, 0.8]) == 0


def test_auc_ties_empty_and_single_class():
    assert score.auc(["correct", "meaning_changed"], [0.5, 0.5]) == 0.5
    assert score.auc([], []) is None
    assert score.auc(["correct", "minor"], [0.2, 0.8]) is None
    assert score.auc(["meaning_changed"], [0.8]) is None


@pytest.mark.parametrize(
    ("q1", "q2", "expected"),
    [
        (0.8, 0.8, "Q2"),
        (None, None, "Q2"),
        (0.1, None, "Q1"),
        (None, 0.1, "Q2"),
        (math.nextafter(0.75, 1), 0.75, "Q1"),
    ],
)
def test_question_ties_undefined_and_strict_near_tie(q1, q2, expected):
    assert score.select_question(q1, q2) == expected


def test_platt_symmetric_reference():
    fitted = score.fit_platt(
        [1 / (1 + math.e), 1 / (1 + math.exp(-1))], ["meaning_changed", "correct"]
    )
    # Symmetry gives b=0 and the scalar equation a=2/(1+exp(a)).
    assert fitted["a"] == pytest.approx(0.6748316143423994, abs=1e-7)
    assert fitted["b"] == pytest.approx(0, abs=1e-7)


def test_platt_constant_score_unpenalized_intercept_and_minor_is_positive():
    fitted = score.fit_platt([0.5] * 4, ["correct", "minor", "minor", "meaning_changed"])
    assert fitted["a"] == pytest.approx(0, abs=1e-7)
    assert fitted["b"] == pytest.approx(math.log(3), abs=1e-7)
    assert score.calibrate(fitted, 0.5) == pytest.approx(0.75, abs=1e-7)


def test_platt_nonnegative_slope_and_clamped_endpoints():
    reversed_fit = score.fit_platt([0.1, 0.9], ["correct", "meaning_changed"])
    assert reversed_fit["a"] == 0
    fitted = score.fit_platt([0, 1], ["meaning_changed", "correct"])
    assert fitted["a"] >= 0
    assert 0 < score.calibrate(fitted, 0) < score.calibrate(fitted, 1) < 1
    assert score.calibrate(fitted, 0) == score.calibrate(fitted, 1e-6)
    assert score.calibrate(fitted, 1) == score.calibrate(fitted, 1 - 1e-6)


@pytest.mark.parametrize(
    "labels", [[], ["correct"], ["correct", "minor"], ["meaning_changed", "meaning_changed"]]
)
def test_platt_single_y_class_and_empty_are_null(labels):
    assert score.fit_platt([0.5] * len(labels), labels) is None
    assert score.calibrate(None, 0.8) is None


def test_verified_inclusive_boundary_and_maximum_coverage():
    assert score.verified_threshold([0.1, 0.8, 0.9], ["meaning_changed", "correct", "minor"]) == 0.8


def test_verified_exact_two_percent_is_admissible():
    assert (
        score.verified_threshold([0.8] + [0.9] * 49, ["meaning_changed"] + ["correct"] * 49) == 0.8
    )


@pytest.mark.parametrize(
    ("values", "labels"),
    [
        ([], []),
        ([0.8, 0.8], ["correct", "meaning_changed"]),
        ([0.9, 0.8], ["meaning_changed", "correct"]),
    ],
)
def test_verified_duplicate_scores_and_no_admissible_are_null(values, labels):
    assert score.verified_threshold(values, labels) is None


def test_disputed_maximizes_changed_not_precision_and_exact_eighty_percent():
    assert (
        score.disputed_threshold(
            [0.1, 0.2, 0.3, 0.3, 0.3],
            ["meaning_changed", "correct", "meaning_changed", "meaning_changed", "meaning_changed"],
        )
        == 0.3
    )


def test_disputed_equal_changed_prefers_smaller_u():
    assert score.disputed_threshold([0.1] * 4 + [0.2], ["meaning_changed"] * 4 + ["correct"]) == 0.1


@pytest.mark.parametrize(
    ("values", "labels"),
    [([], []), ([0.8, 0.8], ["correct", "meaning_changed"]), ([0.1, 0.2], ["correct", "minor"])],
)
def test_disputed_empty_no_admissible_and_tied_values(values, labels):
    assert score.disputed_threshold(values, labels) is None


@pytest.mark.parametrize(
    ("dev", "test", "expected"),
    [
        (5, 5, "thresholds"),
        (4, 5, "auroc_only"),
        (5, 4, "auroc_only"),
        (0, 5, "auroc_only"),
        (4, 1, "auroc_only"),
        (2, 2, "not_evaluable"),
        (0, 0, "not_evaluable"),
    ],
)
def test_floor_boundary_branches(dev, test, expected):
    assert score.sample_floor(dev, test) == expected


def row(label="correct", value=0.9, **changes):
    return {
        "id": "item",
        "model": "model",
        "category": "formula",
        "split": "test",
        "group": "page",
        "label": label,
        "q1": None,
        "q2": None,
        "score": value,
        "failed": False,
        "rule_flag": None,
        **changes,
    }


def test_wilson_known_values_and_zero_denominator():
    assert score.wilson(0, 10) == pytest.approx([0, 0.2775327998628892])
    assert score.wilson(1, 1) == pytest.approx([0.20654931437723745, 1])
    assert score.wilson(5, 10) == pytest.approx([0.236593090512564, 0.763406909487436])
    assert score.wilson(0, 0) is None


def test_ece_hand_computed_bins_and_minor():
    assert score.ece([0.1, 0.19], ["correct", "meaning_changed"]) == pytest.approx(0.355)
    assert score.ece([0.05, 0.15, 0.95], ["correct", "meaning_changed", "minor"]) == pytest.approx(
        1.15 / 3
    )
    assert score.ece([0, 1], ["meaning_changed", "minor"]) == 0
    assert score.ece([0.099, 0.1], ["correct", "meaning_changed"]) == pytest.approx(0.5005)
    assert score.ece([], []) is None


def test_bootstrap_source_groups_seed153_skip_count():
    rows = [row("correct", 0.9, id=f"safe-{i}", group="a") for i in range(2)]
    rows += [row("meaning_changed", 0.1, id=f"bad-{i}", group="b") for i in range(2)]
    expected = {"interval": [1, 1], "attempted": 2000, "valid": 1006, "skipped": 994, "seed": 153}
    assert score.bootstrap_auc(rows) == expected
    assert score.bootstrap_auc(list(reversed(rows))) == expected
    rows += [
        row("minor", 0.1, id="minor", group="minor-only"),
        row("correct", None, id="failed", failed=True, group="failed-only"),
    ]
    assert score.bootstrap_auc(rows) == expected


def test_bootstrap_percentile_and_all_skipped():
    rows = [
        row("correct", 0.9, id="a1", group="a"),
        row("meaning_changed", 0.1, id="a2", group="a"),
        row("correct", 0.1, id="b1", group="b"),
        row("meaning_changed", 0.9, id="b2", group="b"),
    ]
    result = score.bootstrap_auc(rows)
    assert result["interval"] == [0, 1]
    assert result["skipped"] == 0
    for rows in ([], [row()]):
        assert score.bootstrap_auc(rows) == {
            "interval": None,
            "attempted": 2000,
            "valid": 0,
            "skipped": 2000,
            "seed": 153,
        }


@pytest.mark.parametrize(
    ("value", "interval", "expected"),
    [
        (0.75, [0.50001, 0.9], True),
        (0.75, [0.5, 0.9], False),
        (0.74999, [0.6, 0.9], False),
        (None, [0.6, 0.9], None),
        (0.8, None, None),
    ],
)
def test_weak_signal_exact_boundaries(value, interval, expected):
    assert score.weak_signal(value, interval) is expected


@pytest.mark.parametrize(
    ("failed", "p", "tv", "td", "status", "conflict"),
    [
        (True, 0.9, 0.8, 0.2, "failed", False),
        (False, 0.8, 0.8, 0.2, "verified", False),
        (False, 0.2, 0.8, 0.2, "disputed", False),
        (False, 0.5, 0.8, 0.2, "unverified", False),
        (False, None, 0.8, 0.2, "unverified", False),
        (False, 0.9, None, None, "unverified", False),
        (False, 0.5, 0.5, 0.5, "verified", True),
        (False, 0.5, 0.4, 0.6, "verified", True),
    ],
)
def test_status_precedence_inclusive_bounds_nulls_and_conflicts(
    failed, p, tv, td, status, conflict
):
    assert score.classify(failed, p, tv, td) == {"status": status, "conflict": conflict}


def assess(rows, tv=0.8, td=0.2, fitted=None):
    if fitted is None:
        fitted = {"a": 1, "b": 0}
    results = []
    for item in rows:
        probability = None if item["failed"] else score.calibrate(fitted, item["score"])
        results.append(
            {
                "id": item["id"],
                "calibrated": probability,
                **score.classify(item["failed"], probability, tv, td),
            }
        )
    return results


def test_metrics_failures_stay_in_denominators_and_minor_is_safe():
    rows = [
        row("correct", 0.9, id="a"),
        row("meaning_changed", 0.9, id="b"),
        row("minor", 0.1, id="c"),
        row("meaning_changed", 0.1, id="d"),
        row("meaning_changed", None, id="e", failed=True),
        row("correct", None, id="f", failed=True),
        row("correct", 0.5, id="g"),
    ]
    result = score.summarize(rows, assess(rows))
    assert result["counts"]["labels"] == {"correct": 3, "minor": 1, "meaning_changed": 3}
    assert result["counts"]["failed"] == 2
    assert result["verified"]["coverage"] == score.rate(2, 7)
    assert result["verified"]["risk"] == score.rate(1, 2)
    assert result["verified"]["risk_upper95"] == score.wilson(1, 2)[1]
    assert result["disputed"]["count"] == 2
    assert result["disputed"]["flag_rate"] == score.rate(2, 7)
    assert result["disputed"]["precision"] == score.rate(1, 2)
    assert result["disputed"]["recall"] == score.rate(1, 3)
    assert result["disputed"]["false_flag_rate"] == score.rate(1, 4)
    assert result["status_counts"] == {"verified": 2, "disputed": 2, "unverified": 1, "failed": 2}


def test_metrics_all_zero_denominators_and_null_calibration():
    result = score.summarize([], [])
    assert result["AUROC_raw"] is None
    assert result["ECE_raw"] is None and result["ECE_calibrated"] is None
    for metric in (
        result["verified"]["coverage"],
        result["verified"]["risk"],
        *[v for k, v in result["disputed"].items() if k != "count"],
    ):
        assert metric == {"k": 0, "n": 0, "value": None, "wilson95": None}
    rows = [row()]
    results = [{"id": "item", "calibrated": None, "status": "unverified", "conflict": False}]
    result = score.summarize(rows, results)
    assert result["ECE_raw"] == pytest.approx(0.1)
    assert result["ECE_calibrated"] is None


def test_ordered_thresholds_no_conflict_and_negative_control_counts_overlap():
    rows = [row(value=0.5)]
    assert score.summarize(rows, assess(rows))["conflicts"] == 0
    assert score.summarize(rows, assess(rows, tv=0.5, td=0.5))["conflicts"] == 1


def test_formula_rule_combination_correct_only_null_flags_failures_and_misses():
    rows = [
        row(value=0.5, rule_flag=False),
        row(value=0.9, rule_flag=True),
        row(value=0.1, rule_flag=False),
        row(value=0.1, rule_flag=True),
        row(value=None, rule_flag=True, failed=True),
        row("minor", 0.1, rule_flag=True),
        row(value=0.1, rule_flag=None),
        row("meaning_changed", 0.1, rule_flag=False),
        row("meaning_changed", 0.9, rule_flag=False),
        row("meaning_changed", 0.1, rule_flag=True),
        row("meaning_changed", None, rule_flag=False, failed=True),
    ]
    result = score.combined_with_rule(rows, assess(rows), 0.2)
    assert result["excluded_null_rule_flag"] == 1
    assert result["changed_missed_by_rule_caught_by_d3"] == score.rate(1, 3)
    assert result["correct_false_flag_or"] == score.rate(4, 5)
    assert result["correct_false_flag_and"] == score.rate(1, 5)


def test_combination_formula_only_null_denominators_and_inclusive_boundary():
    rows = [row(value=0.2, rule_flag=False)]
    results = [{"calibrated": 0.2, "status": "verified", "conflict": True}]
    assert score.combined_with_rule(rows, results, 0.2)["correct_false_flag_or"] == score.rate(1, 1)
    assert score.combined_with_rule(rows, results, None)["correct_false_flag_or"] == score.rate(
        0, 1
    )
    rows[0]["category"] = "description"
    assert score.combined_with_rule(rows, results, 0.2) is None
    assert score.combined_with_rule([], [], None) is None


def dev_rows(changed=5, safe=5, **changes):
    return [
        row(
            "meaning_changed" if i < changed else "correct",
            None,
            id=f"dev-{i}",
            split="dev",
            q1=0.1 if i < changed else 0.9,
            q2=0.2 if i < changed else 0.8,
            **changes,
        )
        for i in range(changed + safe)
    ]


def test_select_rows_records_both_aucs_fit_thresholds_and_frozen_test_count():
    rows = dev_rows()
    original = copy.deepcopy(rows)
    spec = score.select_rows(rows, {"model": {"formula": 5}})["model"]["formula"]
    assert rows == original
    assert spec["question"] == "Q2" and spec["dev_AUROC"] == {"Q1": 1, "Q2": 1}
    assert spec["calibration_state"] == "FIT" and spec["calibrator"]["a"] > 0
    assert spec["test_changed_count"] == 5 and spec["sample_floor"] == "thresholds"
    assert spec["t_d"] < spec["t_v"]
    assert spec["dev_counts"]["labels"]["meaning_changed"] == 5


@pytest.mark.parametrize(
    ("changed", "test_changed", "floor"), [(4, 5, "auroc_only"), (2, 2, "not_evaluable")]
)
def test_floor_blocks_thresholds_and_non_auc_reports(changed, test_changed, floor):
    spec = score.select_rows(dev_rows(changed), {"model": {"formula": test_changed}})["model"][
        "formula"
    ]
    assert spec["sample_floor"] == floor and spec["calibrator"] is not None
    assert spec["t_v"] is None and spec["t_d"] is None
    rows = [row("meaning_changed", 0.1, id=f"bad-{i}") for i in range(test_changed)] + [row()]
    result = score.evaluate_rows(rows, spec)
    if floor == "auroc_only":
        assert set(result) == {"sample_floor", "counts", "AUROC_raw", "AUROC_CI"}
    else:
        assert set(result) == {"sample_floor", "counts", "reason"}


def test_floor_counts_gold_independently_of_failures_and_unfittable_dev():
    rows = dev_rows()
    for item in rows[:5]:
        item.update(failed=True, q1=None, q2=None)
    spec = score.select_rows(rows, {"model": {"formula": 5}})["model"]["formula"]
    assert spec["sample_floor"] == "thresholds"
    assert spec["dev_counts"]["failed"] == 5
    assert spec["calibrator"] is None and spec["t_v"] is None and spec["t_d"] is None
    assert spec["question"] == "Q2"


def test_evaluation_uses_frozen_fit_and_thresholds_without_mutation():
    spec = score.select_rows(dev_rows(), {"model": {"formula": 5}})["model"]["formula"]
    original = copy.deepcopy(spec)
    rows = [row("meaning_changed", 0.1, id=f"bad-{i}") for i in range(5)]
    rows += [row("correct", 0.9, id="safe"), row("minor", None, id="failed", failed=True)]
    result = score.evaluate_rows(rows, spec)
    assert spec == original
    assert result["verified"]["count"] == 1 and result["disputed"]["count"] == 5
    assert result["verified"]["coverage"]["n"] == 7
    assert result["items"][-1]["status"] == "failed"
    assert "combined_with_rule" in result


def test_evaluation_rejects_inconsistent_frozen_test_count():
    spec = score.select_rows(dev_rows(), {"model": {"formula": 5}})["model"]["formula"]
    with pytest.raises(ValueError, match="input inconsistency"):
        score.evaluate_rows([row()], spec)


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"model": {}},
        {"model": {"formula": True}},
        {"model": {"formula": -1}},
        {"model": {"formula": 5.0}},
    ],
)
def test_frozen_counts_missing_or_invalid_are_input_errors(metadata):
    with pytest.raises(ValueError):
        score.select_rows(dev_rows(), metadata)


@pytest.mark.parametrize(
    "changes",
    [
        {"id": ""},
        {"model": None},
        {"category": " "},
        {"group": 2},
        {"label": "unknown"},
        {"split": "dev"},
        {"failed": 0},
        {"rule_flag": 1},
        {"score": True},
        {"score": -0.01},
        {"score": 1.01},
        {"score": math.nan},
        {"score": math.inf},
        {"score": None},
    ],
)
def test_row_validation_rejects_malformed_inputs(changes):
    with pytest.raises(ValueError):
        score.validate_rows([row(**changes)], "test")


def test_row_validation_required_fields_duplicate_ids_and_failed_null_scores():
    item = row()
    del item["q1"]
    with pytest.raises(ValueError):
        score.validate_rows([item], "test")
    with pytest.raises(ValueError, match="duplicate"):
        score.validate_rows([row(), row()], "test")
    with pytest.raises(ValueError):
        score.validate_rows([row(split="dev", q1=0.1, q2=None)], "dev")
    score.validate_rows([row(failed=True, value=None), row(model="another")], "test")


def test_cli_select_evaluate_hashes_partitions_and_selection_immutability(tmp_path):
    dev = tmp_path / "dev.jsonl"
    test = tmp_path / "test.jsonl"
    metadata = tmp_path / "counts.json"
    selection = tmp_path / "selection.json"
    output = tmp_path / "metrics.json"
    rows = dev_rows() + dev_rows(model="other", category="description")
    dev.write_text("\n".join(json.dumps(item) for item in rows) + "\n\n")
    metadata.write_text(json.dumps({"model": {"formula": 5}, "other": {"description": 5}}))
    test_rows = [
        row("meaning_changed", 0.1, id=f"test-{i}", model=model, category=category)
        for model, category in (("model", "formula"), ("other", "description"))
        for i in range(5)
    ]
    test.write_text("\n".join(json.dumps(item) for item in test_rows))
    script = str(Path(score.__file__))
    result = subprocess.run(
        [
            sys.executable,
            script,
            "select",
            str(dev),
            str(selection),
            "--test-counts",
            str(metadata),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    saved_bytes = selection.read_bytes()
    saved = json.loads(saved_bytes)
    assert saved["input_sha256"] == hashlib.sha256(dev.read_bytes()).hexdigest()
    assert saved["test_counts_sha256"] == hashlib.sha256(metadata.read_bytes()).hexdigest()
    assert set(saved["models"]) == {"model", "other"}
    result = subprocess.run(
        [sys.executable, script, "evaluate", str(test), str(selection), str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert selection.read_bytes() == saved_bytes
    metrics = json.loads(output.read_bytes())
    assert metrics["selection_sha256"] == hashlib.sha256(saved_bytes).hexdigest()
    assert metrics["input_sha256"] == hashlib.sha256(test.read_bytes()).hexdigest()
    assert set(metrics["models"]) == {"model", "other"}
    assert str(tmp_path) not in output.read_text()


def saved_record(item_id="a", **changes):
    return {
        "id": item_id,
        "category": "formula",
        "split": "dev",
        "state": "OK",
        "questions": ["Q1", "Q2"],
        "safe_scores": {"Q1": 0.2, "Q2": 0.7},
        "result": {
            "answers": {
                "Q1": {
                    "confidence": 0.99,
                    "probabilities": {
                        "faithful": 0.2,
                        "minor_difference": 0.6,
                        "meaning_changed": 0.1,
                        "cannot_determine": 0.1,
                    },
                },
                "Q2": {"noul": 0.7},
            }
        },
        **changes,
    }


def test_raw_extraction_uses_faithful_and_noul_and_checks_cache():
    import reproduce_w4b

    record = saved_record()
    assert reproduce_w4b.raw_score(record, "Q1") == 0.2
    assert reproduce_w4b.raw_score(record, "Q2") == 0.7
    record["safe_scores"]["Q1"] = 0.8
    with pytest.raises(ValueError, match="cache"):
        reproduce_w4b.raw_score(record, "Q1")


@pytest.mark.parametrize(
    "records", [[], [saved_record("unknown")], [saved_record(), saved_record()]]
)
def test_w4b_join_missing_unknown_duplicate_stops(records):
    import reproduce_w4b

    gold = [
        {
            "id": "a",
            "category": "formula",
            "split": "dev",
            "label": "minor",
            "split_group": "page",
            "adjudication_evidence": "must never be copied",
        }
    ]
    with pytest.raises(ValueError, match="join"):
        reproduce_w4b.convert_rows(gold, records, "model", "dev")


def test_w4b_converter_schema_group_and_no_gold_text_copy():
    import reproduce_w4b

    gold = [
        {
            "id": "a",
            "category": "formula",
            "split": "dev",
            "label": "minor",
            "split_group": "page",
            "adjudication_evidence": "must never be copied",
        }
    ]
    rows = reproduce_w4b.convert_rows(gold, [saved_record()], "model", "dev")
    assert rows == [row("minor", None, id="a", split="dev", q1=0.2, q2=0.7)]
    with pytest.raises(ValueError):
        reproduce_w4b.convert_rows(gold, [saved_record(category="code")], "model", "dev")


def test_w4b_legacy_disputed_without_fit_and_verified_precedence():
    import reproduce_w4b

    rows = [row(value=0.1)]
    assert (
        reproduce_w4b.historical_metrics(rows, {"calibrator": None, "threshold": None})[
            "status_counts"
        ]["disputed"]
        == 1
    )
    receipt = {"calibrator": {"a": 0, "b": 8}, "threshold": 0.9}
    assert reproduce_w4b.historical_metrics(rows, receipt)["status_counts"]["verified"] == 1


def test_reproduction_rounding_is_explained_but_not_called_numeric_match():
    import reproduce_w4b

    result = reproduce_w4b.comparison("report.AUROC", 0.778, 0.777511961722488, decimals=3)
    assert result["match"] is False and result["display_match"] is True
    assert result["cause"] == "display rounding to 3 decimal places"
    result = reproduce_w4b.comparison("report.coverage", 0.436, 24 / 55, decimals=1, percent=True)
    assert result["match"] is False and result["display_match"] is True
    assert result["cause"] == "display rounding to 1 decimal places in percent"
    assert reproduce_w4b.comparison("null", None, None)["match"] is True
    assert reproduce_w4b.comparison("not_zero", None, 0)["match"] is False
    assert reproduce_w4b.comparison("unknown", 0.778, 0.7)["cause"] == "UNKNOWN"


def test_reproduction_cli_reads_raw_outputs_and_published_tables(tmp_path):
    import reproduce_w4b

    w = tmp_path / "w4b"
    w.mkdir()

    def write(name, data):
        path = w / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return path

    gold = [
        {
            "id": split,
            "category": "formula",
            "split": split,
            "label": "correct",
            "split_group": split + "-page",
        }
        for split in ("dev", "test")
    ]
    write("gold.json", {"items": gold})
    write("protocol.json", {})
    dev_file = write("runs/model/dev/dev.result.json", saved_record("dev"))
    write("runs/model/test/test.result.json", saved_record("test", split="test", questions=["Q2"]))
    receipt = {
        "question": "Q2",
        "dev_AUROC": {"Q1": None, "Q2": None},
        "dev_n": 1,
        "dev_label_counts": {"correct": 1},
        "calibrator": {"state": "UNFITTABLE_SINGLE_CLASS", "a": None, "b": None},
        "threshold": None,
        "dev_verified": 0,
        "dev_changed": 0,
        "dev_error_rate": None,
    }
    selected = write(
        "selection/model/selection.json",
        {
            "model": "model",
            "categories": {"formula": receipt},
            "producer_files": {},
            "dev_receipt_hashes": {
                dev_file.name: hashlib.sha256(dev_file.read_bytes()).hexdigest()
            },
        },
    )
    write(
        "selection/model/test-launch.json",
        {"selection_SHA256": hashlib.sha256(selected.read_bytes()).hexdigest()},
    )
    metrics = {
        "test_n": 1,
        "valid": 1,
        "failed_or_NOT_RUN": 0,
        "label_counts": {"correct": 1},
        "source_page_groups": 1,
        "AUROC_raw": None,
        "ECE_before": 0.3,
        "ECE_after": None,
        "verified": 0,
        "verified_changed": 0,
        "verified_error_rate": None,
        "verified_error_Wilson95": None,
        "coverage": 0.0,
        "status_counts": {"unverified": 1},
    }
    write("evaluation/model/metrics.json", {"categories": {"formula": metrics}})
    write(
        "comparison.json",
        [
            {
                "model": "model",
                "category": "formula",
                "question": "Q2",
                "test_n": 1,
                "AUROC": None,
                "ECE_before": 0.3,
                "ECE_after": None,
                "threshold": None,
                "verified": 0,
                "changed_in_verified": 0,
                "verified_error_rate": None,
                "coverage": 0.0,
            }
        ],
    )
    (w / "report.md").write_text(
        "## 3. Test\n\n"
        "|model|formula|1|Q2|—|0.300 → —|N/A（0/0）|0.0%|\n\n"
        "|model|formula|— / —|Q2|—|0/1|N/A|\n\n## 4. Other\n"
    )
    output = tmp_path / "reproduction.json"
    result = subprocess.run(
        [sys.executable, str(Path(reproduce_w4b.__file__)), str(w), str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_bytes())
    assert data["summary"]["full_precision_match"] is True
    assert data["summary"]["unexplained_mismatches"] == 0
    assert data["summary"]["published_display_match"] is True
    assert str(tmp_path) not in output.read_text()


def test_bootstrap_preserves_repeated_group_copies_in_percentiles():
    groups = [
        [("correct", 0.1), ("meaning_changed", 0.4)],
        [("correct", 0.7), ("meaning_changed", 0.8)],
        [("correct", 0.9), ("meaning_changed", 0.2)],
        [("correct", 0.6), ("meaning_changed", 0.3)],
        [("correct", 0.5), ("correct", 0.8), ("meaning_changed", 0.55)],
    ]
    rows = [
        row(label, value, id=f"{i}-{j}", group=str(i))
        for i, group in enumerate(groups)
        for j, (label, value) in enumerate(group)
    ]
    # Independent pairwise AUROC calculation gives these percentile endpoints.
    assert score.bootstrap_auc(rows)["interval"] == pytest.approx([0.35, 29 / 30])


def test_unfittable_full_floor_never_uses_raw_disputed_fallback():
    spec = score.select_rows(dev_rows(changed=5, safe=0), {"model": {"formula": 5}})["model"][
        "formula"
    ]
    rows = [row("meaning_changed", 0.1, id=str(i)) for i in range(5)]
    result = score.evaluate_rows(rows, spec)
    assert result["sample_floor"] == "thresholds"
    assert result["status_counts"]["unverified"] == 5
    assert result["status_counts"]["disputed"] == 0
    assert result["ECE_calibrated"] is None
    assert result["AUROC_CI"]["skipped"] == 2000
    assert result["weak_signal"] is None


def test_evaluation_auroc_uses_raw_even_when_calibrator_slope_collapses():
    dev = dev_rows()
    for item in dev:
        item.update(q1=0.5, q2=0.5)
    spec = score.select_rows(dev, {"model": {"formula": 5}})["model"]["formula"]
    assert spec["calibrator"]["a"] == 0
    rows = [
        row("meaning_changed" if i < 5 else "correct", 0.1 if i < 5 else 0.9, id=str(i))
        for i in range(10)
    ]
    result = score.evaluate_rows(rows, spec)
    assert result["AUROC_raw"] == 1 and result["AUROC_CI"]["interval"] == [1, 1]
    assert result["weak_signal"] is True
    assert result["ECE_raw"] == pytest.approx(0.1)
    assert result["ECE_calibrated"] == pytest.approx(0)


@pytest.mark.parametrize(
    "mutation",
    [
        {"t_d": 0.2, "sample_floor": "auroc_only"},
        {"calibrator": {"a": -1, "b": 0}},
        {"t_v": math.nan},
        {"test_changed_count": True},
        {"question": "Q3"},
    ],
)
def test_evaluation_rejects_inconsistent_selection(mutation):
    spec = score.select_rows(dev_rows(), {"model": {"formula": 5}})["model"]["formula"]
    spec.update(mutation)
    with pytest.raises(ValueError):
        score.evaluate_rows([], spec)


def test_cli_count_mismatch_and_input_overwrite_stop_without_output(tmp_path):
    dev = tmp_path / "dev.jsonl"
    metadata = tmp_path / "counts.json"
    selection = tmp_path / "selection.json"
    test = tmp_path / "test.jsonl"
    output = tmp_path / "metrics.json"
    dev.write_text("\n".join(json.dumps(item) for item in dev_rows()))
    metadata.write_text('{"model": {"formula": 5}}')
    script = str(Path(score.__file__))
    selected = subprocess.run(
        [
            sys.executable,
            script,
            "select",
            str(dev),
            str(selection),
            "--test-counts",
            str(metadata),
        ],
        capture_output=True,
        text=True,
    )
    assert selected.returncode == 0
    frozen = selection.read_bytes()
    test.write_text(json.dumps(row()))
    result = subprocess.run(
        [sys.executable, script, "evaluate", str(test), str(selection), str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and "input inconsistency" in result.stderr
    assert not output.exists() and selection.read_bytes() == frozen
    original = dev.read_bytes()
    result = subprocess.run(
        [sys.executable, script, "select", str(dev), str(dev), "--test-counts", str(metadata)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and "overwrite" in result.stderr
    assert dev.read_bytes() == original


def test_selected_equal_thresholds_report_conflicts_and_rule_uses_d3_predicate():
    spec = score.select_rows(dev_rows(changed=5, safe=245), {"model": {"formula": 5}})["model"][
        "formula"
    ]
    assert spec["t_v"] == spec["t_d"]
    rows = [row("meaning_changed", 0.2, id=str(i), rule_flag=False) for i in range(5)]
    rows.append(row("correct", 0.8, id="safe", rule_flag=False))
    result = score.evaluate_rows(rows, spec)
    assert result["conflicts"] == 5 and result["verified"]["count"] == 6
    assert result["disputed"]["count"] == 0
    assert result["combined_with_rule"]["changed_missed_by_rule_caught_by_d3"] == score.rate(5, 5)
