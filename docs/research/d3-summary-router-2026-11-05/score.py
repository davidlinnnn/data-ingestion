"""Frozen dev selection and one-pass test evaluation for #153."""

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit
from scipy.stats import rankdata


def auc(labels, scores):
    """Return correct-positive AUROC, excluding minor; undefined is None."""
    binary = [
        (label, value) for label, value in zip(labels, scores, strict=True) if label != "minor"
    ]
    positives = sum(label == "correct" for label, _ in binary)
    negatives = len(binary) - positives
    if not positives or not negatives:
        return None
    ranks = rankdata([value for _, value in binary], method="average")
    rank_sum = sum(
        rank for rank, (label, _) in zip(ranks, binary, strict=True) if label == "correct"
    )
    return float((rank_sum - positives * (positives + 1) / 2) / (positives * negatives))


def select_question(q1_auc, q2_auc):
    return "Q1" if q1_auc is not None and (q2_auc is None or q1_auc > q2_auc) else "Q2"


def fit_platt(scores, labels):
    """Fit the fixed monotone regularized Platt model; one Y class is unfittable."""
    y = np.array([label != "meaning_changed" for label in labels], dtype=float)
    if len(set(y)) < 2:
        return None
    x = logit(np.clip(np.array(scores, dtype=float), 1e-6, 1 - 1e-6))

    def objective(parameters):
        a, b = parameters
        z = a * x + b
        error = expit(z) - y
        return (
            float(np.sum(np.logaddexp(0, z) - y * z) + 0.5 * a * a),
            np.array([np.dot(error, x) + a, np.sum(error)]),
        )

    result = minimize(
        objective,
        [1, float(logit(y.mean()))],
        jac=True,
        method="L-BFGS-B",
        bounds=[(0, None), (None, None)],
        options={"maxiter": 1000, "ftol": 1e-12, "gtol": 1e-8},
    )
    if not result.success:
        raise ValueError("Platt optimization failed; no selection produced")
    return {
        "a": float(result.x[0]),
        "b": float(result.x[1]),
        "objective": float(result.fun),
        "n": len(y),
        "positives": int(y.sum()),
        "negatives": int(len(y) - y.sum()),
    }


def calibrate(fitted, raw):
    if fitted is None:
        return None
    return float(expit(fitted["a"] * logit(np.clip(raw, 1e-6, 1 - 1e-6)) + fitted["b"]))


def verified_threshold(probabilities, labels):
    candidates = []
    for threshold in sorted(set(probabilities)):
        chosen = [label for p, label in zip(probabilities, labels, strict=True) if p >= threshold]
        changed = chosen.count("meaning_changed")
        if chosen and changed / len(chosen) <= 0.02:
            candidates.append((len(chosen), threshold))
    return max(candidates)[1] if candidates else None


def disputed_threshold(probabilities, labels):
    candidates = []
    for threshold in sorted(set(probabilities)):
        flagged = [label for p, label in zip(probabilities, labels, strict=True) if p <= threshold]
        changed = flagged.count("meaning_changed")
        if flagged and changed / len(flagged) >= 0.80:
            candidates.append((changed, -threshold))
    return -max(candidates)[1] if candidates else None


def sample_floor(dev_changed, test_changed):
    if dev_changed >= 5 and test_changed >= 5:
        return "thresholds"
    return "auroc_only" if dev_changed + test_changed >= 5 else "not_evaluable"


def wilson(k, n):
    if n == 0:
        return None
    z = 1.959963984540054
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [max(0, center - half), min(1, center + half)]


def rate(k, n):
    return {"k": k, "n": n, "value": k / n if n else None, "wilson95": wilson(k, n)}


def ece(probabilities, labels):
    bins = [[] for _ in range(10)]
    for probability, label in zip(probabilities, labels, strict=True):
        bins[min(9, int(probability * 10))].append((probability, label != "meaning_changed"))
    error = sum(abs(sum(p for p, _ in values) - sum(y for _, y in values)) for values in bins)
    return error / len(probabilities) if len(probabilities) else None


def bootstrap_auc(rows):
    """Use exactly 2,000 source-page group draws, including failed bootstrap attempts."""
    groups = {}
    for row in rows:
        if not row["failed"] and row["label"] != "minor":
            groups.setdefault(row["group"], []).append(row)
    population = [groups[key] for key in sorted(groups)]
    rng = np.random.default_rng(153)
    values = []
    for _ in range(2000):
        sampled = (
            [
                row
                for index in rng.integers(0, len(population), size=len(population))
                for row in population[index]
            ]
            if population
            else []
        )
        value = auc([row["label"] for row in sampled], [row["score"] for row in sampled])
        if value is not None:
            values.append(value)
    return {
        "interval": np.percentile(values, [2.5, 97.5], method="linear").tolist()
        if values
        else None,
        "attempted": 2000,
        "valid": len(values),
        "skipped": 2000 - len(values),
        "seed": 153,
    }


def weak_signal(raw_auc, interval):
    if raw_auc is None or interval is None:
        return None
    return raw_auc >= 0.75 and interval[0] > 0.5


def classify(failed, probability, t_v, t_d):
    if failed:
        return {"status": "failed", "conflict": False}
    verified = probability is not None and t_v is not None and probability >= t_v
    disputed = probability is not None and t_d is not None and probability <= t_d
    return {
        "status": "verified" if verified else "disputed" if disputed else "unverified",
        "conflict": verified and disputed,
    }


def counts(rows):
    valid = [row for row in rows if not row["failed"]]
    return {
        "eligible": len(rows),
        "valid": len(valid),
        "failed": len(rows) - len(valid),
        "labels": {
            label: sum(row["label"] == label for row in rows)
            for label in ("correct", "minor", "meaning_changed")
        },
        "valid_labels": {
            label: sum(row["label"] == label for row in valid)
            for label in ("correct", "minor", "meaning_changed")
        },
    }


def summarize(rows, classified):
    """Summarize assigned statuses; eligible failed rows remain in denominators."""
    pairs = list(zip(rows, classified, strict=True))
    valid = [(row, result) for row, result in pairs if not row["failed"]]
    calibrated = [(row, result) for row, result in valid if result["calibrated"] is not None]
    verified = [row for row, result in pairs if result["status"] == "verified"]
    disputed = [row for row, result in pairs if result["status"] == "disputed"]
    verified_changed = sum(row["label"] == "meaning_changed" for row in verified)
    disputed_changed = sum(row["label"] == "meaning_changed" for row in disputed)
    changed = sum(row["label"] == "meaning_changed" for row in rows)
    risk = rate(verified_changed, len(verified))
    statuses = Counter(result["status"] for result in classified)
    return {
        "counts": counts(rows),
        "AUROC_raw": auc([row["label"] for row, _ in valid], [row["score"] for row, _ in valid]),
        "ECE_raw": ece([row["score"] for row, _ in valid], [row["label"] for row, _ in valid]),
        "ECE_calibrated": ece(
            [result["calibrated"] for _, result in calibrated],
            [row["label"] for row, _ in calibrated],
        ),
        "verified": {
            "count": len(verified),
            "changed": verified_changed,
            "coverage": rate(len(verified), len(rows)),
            "risk": risk,
            "risk_upper95": risk["wilson95"][1] if risk["wilson95"] is not None else None,
        },
        "disputed": {
            "count": len(disputed),
            "flag_rate": rate(len(disputed), len(rows)),
            "precision": rate(disputed_changed, len(disputed)),
            "recall": rate(disputed_changed, changed),
            "false_flag_rate": rate(len(disputed) - disputed_changed, len(rows) - changed),
        },
        "status_counts": {
            status: statuses[status] for status in ("verified", "disputed", "unverified", "failed")
        },
        "conflicts": sum(result["conflict"] for result in classified),
    }


def combined_with_rule(rows, classified, t_d):
    formula = [
        (row, result)
        for row, result in zip(rows, classified, strict=True)
        if row["category"] == "formula"
    ]
    if not formula:
        return None
    known = [
        (
            row,
            not row["failed"]
            and result["calibrated"] is not None
            and t_d is not None
            and result["calibrated"] <= t_d,
        )
        for row, result in formula
        if row["rule_flag"] is not None
    ]
    missed = [
        (row, flag)
        for row, flag in known
        if row["label"] == "meaning_changed" and not row["rule_flag"]
    ]
    correct = [(row, flag) for row, flag in known if row["label"] == "correct"]
    return {
        "excluded_null_rule_flag": len(formula) - len(known),
        "changed_missed_by_rule_caught_by_d3": rate(sum(flag for _, flag in missed), len(missed)),
        "correct_false_flag_or": rate(
            sum(row["rule_flag"] or flag for row, flag in correct), len(correct)
        ),
        "correct_false_flag_and": rate(
            sum(row["rule_flag"] and flag for row, flag in correct), len(correct)
        ),
    }


def validate_rows(rows, split):
    required = {
        "id",
        "model",
        "category",
        "split",
        "group",
        "label",
        "q1",
        "q2",
        "score",
        "failed",
        "rule_flag",
    }
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not required <= row.keys():
            raise ValueError("row missing required fields")
        for field in ("id", "model", "category", "group"):
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError(f"invalid row {field}")
        if row["split"] != split or row["label"] not in ("correct", "minor", "meaning_changed"):
            raise ValueError("invalid row split or label")
        if type(row["failed"]) is not bool or (
            row["rule_flag"] is not None and type(row["rule_flag"]) is not bool
        ):
            raise ValueError("failed and non-null rule_flag must be boolean")
        for field in ("q1", "q2", "score"):
            value = row[field]
            if value is not None and (
                type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1
            ):
                raise ValueError(f"invalid probability in {field}")
        fields = ("q1", "q2") if split == "dev" else ("score",)
        if not row["failed"] and any(row[field] is None for field in fields):
            raise ValueError("nonfailed row has a null required score")
        identity = (row["model"], row["id"])
        if identity in seen:
            raise ValueError("duplicate model/item identity")
        seen.add(identity)


def partitions(rows):
    groups = {}
    for row in rows:
        groups.setdefault((row["model"], row["category"]), []).append(row)
    return groups


def validate_test_counts(test_counts):
    if not isinstance(test_counts, dict):
        raise ValueError("test counts must be a model/category object")
    for model, categories in test_counts.items():
        if not isinstance(model, str) or not model.strip() or not isinstance(categories, dict):
            raise ValueError("invalid model in test counts")
        for category, count in categories.items():
            if (
                not isinstance(category, str)
                or not category.strip()
                or type(count) is not int
                or count < 0
            ):
                raise ValueError("test changed counts must be nonnegative integers")


def select_rows(rows, test_counts):
    validate_rows(rows, "dev")
    validate_test_counts(test_counts)
    if not rows:
        raise ValueError("dev rows are empty")
    models = {}
    for (model, category), group in sorted(partitions(rows).items()):
        if model not in test_counts or category not in test_counts[model]:
            raise ValueError("missing frozen test count for dev model/category")
        valid = [row for row in group if not row["failed"]]
        labels = [row["label"] for row in valid]
        aucs = {q.upper(): auc(labels, [row[q] for row in valid]) for q in ("q1", "q2")}
        question = select_question(aucs["Q1"], aucs["Q2"])
        raw = [row[question.lower()] for row in valid]
        fitted = fit_platt(raw, labels)
        dev_counts = counts(group)
        test_changed = test_counts[model][category]
        floor = sample_floor(dev_counts["labels"]["meaning_changed"], test_changed)
        probabilities = [calibrate(fitted, value) for value in raw] if fitted is not None else []
        thresholds_allowed = fitted is not None and floor == "thresholds"
        models.setdefault(model, {})[category] = {
            "question": question,
            "dev_AUROC": aucs,
            "calibrator": fitted,
            "calibration_state": "FIT" if fitted is not None else "UNFITTABLE_SINGLE_CLASS",
            "t_v": verified_threshold(probabilities, labels) if thresholds_allowed else None,
            "t_d": disputed_threshold(probabilities, labels) if thresholds_allowed else None,
            "sample_floor": floor,
            "dev_counts": dev_counts,
            "test_changed_count": test_changed,
        }
    return models


def validate_spec(spec):
    if spec["question"] not in ("Q1", "Q2"):
        raise ValueError("invalid selected question")
    test_changed = spec["test_changed_count"]
    dev_changed = spec["dev_counts"]["labels"]["meaning_changed"]
    if any(type(value) is not int or value < 0 for value in (dev_changed, test_changed)):
        raise ValueError("invalid frozen label counts")
    if spec["sample_floor"] != sample_floor(dev_changed, test_changed):
        raise ValueError("inconsistent selection sample floor")
    fitted = spec["calibrator"]
    if fitted is not None:
        for field in ("a", "b"):
            value = fitted[field]
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("invalid frozen calibrator")
        if fitted["a"] < 0:
            raise ValueError("frozen calibrator slope must be nonnegative")
    for field in ("t_v", "t_d"):
        value = spec[field]
        if value is not None:
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("invalid frozen threshold")
            if fitted is None or spec["sample_floor"] != "thresholds":
                raise ValueError("threshold without fit or C1 eligibility")


def evaluate_rows(rows, spec):
    validate_rows(rows, "test")
    validate_spec(spec)
    if len(partitions(rows)) > 1:
        raise ValueError("evaluate_rows requires one model/category")
    observed = counts(rows)
    if observed["labels"]["meaning_changed"] != spec["test_changed_count"]:
        raise ValueError("input inconsistency: test changed count differs from frozen count")
    floor = spec["sample_floor"]
    if floor == "not_evaluable":
        return {
            "sample_floor": floor,
            "counts": observed,
            "reason": "FEWER_THAN_FIVE_CHANGED_ACROSS_DEV_AND_TEST",
        }
    valid = [row for row in rows if not row["failed"]]
    raw_auc = auc([row["label"] for row in valid], [row["score"] for row in valid])
    interval = bootstrap_auc(rows)
    if floor == "auroc_only":
        return {
            "sample_floor": floor,
            "counts": observed,
            "AUROC_raw": raw_auc,
            "AUROC_CI": interval,
        }
    classified = []
    for row in rows:
        probability = None if row["failed"] else calibrate(spec["calibrator"], row["score"])
        classified.append(
            {
                "id": row["id"],
                "calibrated": probability,
                **classify(row["failed"], probability, spec["t_v"], spec["t_d"]),
            }
        )
    result = {
        **summarize(rows, classified),
        "sample_floor": floor,
        "AUROC_CI": interval,
        "weak_signal": weak_signal(raw_auc, interval["interval"]),
        "items": classified,
    }
    combined = combined_with_rule(rows, classified, spec["t_d"])
    if combined is not None:
        result["combined_with_rule"] = combined
    return result


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, data, inputs):
    if path.resolve() in {item.resolve() for item in inputs}:
        raise ValueError("output would overwrite an input")
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    select = commands.add_parser("select")
    select.add_argument("rows", type=Path)
    select.add_argument("output", type=Path)
    select.add_argument("--test-counts", type=Path, required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("rows", type=Path)
    evaluate.add_argument("selection", type=Path)
    evaluate.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        raw = args.rows.read_bytes()
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if args.command == "select":
            raw_counts = args.test_counts.read_bytes()
            models = select_rows(rows, json.loads(raw_counts))
            result = {
                "input_sha256": sha256(raw),
                "test_counts_sha256": sha256(raw_counts),
                "models": models,
            }
            inputs = [args.rows, args.test_counts]
        else:
            validate_rows(rows, "test")
            raw_selection = args.selection.read_bytes()
            selection = json.loads(raw_selection)
            for field in ("input_sha256", "test_counts_sha256"):
                digest = selection[field]
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(char not in "0123456789abcdef" for char in digest)
                ):
                    raise ValueError("invalid selection provenance hash")
            groups = partitions(rows)
            known = {
                (model, category)
                for model, categories in selection["models"].items()
                for category in categories
            }
            if set(groups) - known:
                raise ValueError("test model/category has no frozen selection")
            models = {}
            for model, category in sorted(known):
                models.setdefault(model, {})[category] = evaluate_rows(
                    groups.get((model, category), []), selection["models"][model][category]
                )
            result = {
                "input_sha256": sha256(raw),
                "selection_sha256": sha256(raw_selection),
                "models": models,
            }
            inputs = [args.rows, args.selection]
        write_json(args.output, result, inputs)
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        parser.exit(2, f"input error: {error}\n")


if __name__ == "__main__":
    main()
