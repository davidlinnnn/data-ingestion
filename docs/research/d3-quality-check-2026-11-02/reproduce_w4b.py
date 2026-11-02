"""Independently reproduce W4b from saved raw answers, with historical policy."""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
import scipy
import score


def raw_score(record, question):
    answer = record["result"]["answers"][question]
    value = answer["probabilities"]["faithful"] if question == "Q1" else answer["noul"]
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("invalid saved raw probability")
    if value != record["safe_scores"][question]:
        raise ValueError("raw answer differs from safe-score cache")
    return value


def convert_rows(gold, records, model, split, questions=None):
    expected = [item for item in gold if item["split"] == split]
    items = {item["id"]: item for item in expected}
    saved = {record["id"]: record for record in records}
    if len(items) != len(expected) or len(saved) != len(records) or set(items) != set(saved):
        raise ValueError("W4b output/gold join has missing, unknown or duplicate IDs")
    rows = []
    for item in expected:
        record = saved[item["id"]]
        if record["split"] != split or record["category"] != item["category"]:
            raise ValueError("saved output split/category differs from gold")
        required = ["Q1", "Q2"] if split == "dev" else [questions[item["category"]]]
        if record["questions"] != required:
            raise ValueError("saved questions differ from recomputed dev selection")
        failed = record["state"] != "OK"
        rows.append(
            {
                "id": item["id"],
                "model": model,
                "category": item["category"],
                "split": split,
                "group": item["split_group"],
                "label": item["label"],
                "failed": failed,
                "q1": raw_score(record, "Q1") if not failed and split == "dev" else None,
                "q2": raw_score(record, "Q2") if not failed and split == "dev" else None,
                "score": raw_score(record, required[0]) if not failed and split == "test" else None,
                "rule_flag": None,
            }
        )
    score.validate_rows(rows, split)
    return rows


def historical_metrics(rows, receipt):
    classified = []
    fitted = receipt["calibrator"]
    for row in rows:
        probability = None if row["failed"] else score.calibrate(fitted, row["score"])
        if row["failed"]:
            status = "failed"
        elif (
            probability is not None
            and receipt["threshold"] is not None
            and probability >= receipt["threshold"]
        ):
            status = "verified"
        elif row["score"] < 0.5:
            status = "disputed"
        else:
            status = "unverified"
        classified.append({"calibrated": probability, "status": status, "conflict": False})
    metrics = score.summarize(rows, classified)
    return {
        "test_n": metrics["counts"]["eligible"],
        "valid": metrics["counts"]["valid"],
        "failed_or_NOT_RUN": metrics["counts"]["failed"],
        "label_counts": metrics["counts"]["labels"],
        "source_page_groups": len({row["group"] for row in rows}),
        "AUROC_raw": metrics["AUROC_raw"],
        "ECE_before": metrics["ECE_raw"],
        "ECE_after": metrics["ECE_calibrated"],
        "verified": metrics["verified"]["count"],
        "verified_changed": metrics["verified"]["changed"],
        "verified_error_rate": metrics["verified"]["risk"]["value"],
        "verified_error_Wilson95": metrics["verified"]["risk"]["wilson95"],
        "coverage": metrics["verified"]["coverage"]["value"],
        "status_counts": metrics["status_counts"],
    }


def comparison(name, expected, actual, decimals=None, percent=False):
    numeric = type(expected) in (int, float) and type(actual) in (int, float)
    error = abs(expected - actual) if numeric else None
    match = (
        error <= 1e-4
        if numeric and (type(expected) is float or type(actual) is float)
        else expected == actual
    )
    display_match = None
    cause = None if match else "UNKNOWN"
    if decimals is not None and numeric:
        multiplier = 100 if percent else 1
        display_match = (
            f"{expected * multiplier:.{decimals}f}" == f"{actual * multiplier:.{decimals}f}"
        )
        if not match and display_match:
            cause = f"display rounding to {decimals} decimal places" + (
                " in percent" if percent else ""
            )
    return {
        "number": name,
        "w4b": expected,
        "ours": actual,
        "absolute_error": error,
        "match": bool(match),
        "display_match": display_match,
        "cause": cause,
    }


def dev_receipt(rows):
    valid = [row for row in rows if not row["failed"]]
    labels = [row["label"] for row in valid]
    aucs = {q.upper(): score.auc(labels, [row[q] for row in valid]) for q in ("q1", "q2")}
    question = score.select_question(aucs["Q1"], aucs["Q2"])
    fitted = score.fit_platt([row[question.lower()] for row in valid], labels)
    probabilities = (
        [score.calibrate(fitted, row[question.lower()]) for row in valid] if fitted else []
    )
    threshold = score.verified_threshold(probabilities, labels) if fitted else None
    selected = (
        [
            label
            for p, label in zip(probabilities, labels, strict=True)
            if threshold is not None and p >= threshold
        ]
        if fitted
        else []
    )
    changed = selected.count("meaning_changed")
    return {
        "question": question,
        "dev_AUROC": aucs,
        "dev_n": len(valid),
        "dev_label_counts": {label: labels.count(label) for label in sorted(set(labels))},
        "calibrator": fitted,
        "threshold": threshold,
        "dev_verified": len(selected),
        "dev_changed": changed,
        "dev_error_rate": changed / len(selected) if selected else None,
    }


def published_checks(report, models):
    section = report.split("## 3.", 1)[1].split("## 4.", 1)[0]
    checks = []
    seen = {"test": set(), "dev": set()}

    def number(text):
        return None if text in ("—", "N/A") else float(text)

    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0] not in models:
            continue
        model, category = cells[:2]
        data = models[model][category]
        kind = "test" if len(cells) == 8 else "dev" if len(cells) == 7 else None
        if kind is None or (model, category) in seen[kind]:
            raise ValueError("invalid or duplicate published table row")
        seen[kind].add((model, category))
        prefix = f"report.{kind}.{model}.{category}"

        def add(field, expected, actual, decimals=None, percent=False, prefix=prefix):
            checks.append(comparison(f"{prefix}.{field}", expected, actual, decimals, percent))

        if kind == "test":
            metrics = data["test"]
            add("n", int(cells[2]), metrics["test_n"])
            add("question", cells[3], data["dev"]["question"])
            add("AUROC", number(cells[4]), metrics["AUROC_raw"], 3)
            before, after = (value.strip() for value in cells[5].split("→"))
            add("ECE_before", number(before), metrics["ECE_before"], 3)
            add("ECE_after", number(after), metrics["ECE_after"], 3)
            fraction = re.search(r"(\d+)/(\d+)", cells[6])
            if fraction is None:
                raise ValueError("published verified fraction missing")
            changed, verified = map(int, fraction.groups())
            add("verified_changed", changed, metrics["verified_changed"])
            add("verified", verified, metrics["verified"])
            percentage = re.search(r"([\d.]+)%", cells[6])
            risk = float(percentage[1]) / 100 if percentage else None
            add("risk", risk, metrics["verified_error_rate"], 1, True)
            add("coverage", float(cells[7].removesuffix("%")) / 100, metrics["coverage"], 1, True)
        else:
            dev = data["dev"]
            q1, q2 = (value.strip() for value in cells[2].split("/"))
            add("AUROC_Q1", number(q1), dev["dev_AUROC"]["Q1"], 4)
            add("AUROC_Q2", number(q2), dev["dev_AUROC"]["Q2"], 4)
            add("question", cells[3], dev["question"])
            add("threshold", number(cells[4]), dev["threshold"], 4)
            verified, n = map(int, cells[5].split("/"))
            add("verified", verified, dev["dev_verified"])
            add("n", n, dev["dev_n"])
            add("risk", number(cells[6]), dev["dev_error_rate"], 1)
    expected = {
        (model, category) for model, categories in models.items() for category in categories
    }
    if seen["test"] != expected or seen["dev"] != expected:
        raise ValueError("published tables have missing or extra model/category rows")
    return checks


def reproduce(w):
    sources = {}
    raw_digest = hashlib.sha256()
    raw_file_count = 0

    def read(name, text=False):
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("source name escapes W4b directory")
        raw = (w / path).read_bytes()
        sources[path.as_posix()] = score.sha256(raw)
        return raw.decode() if text else json.loads(raw)

    def run_records(model, split):
        nonlocal raw_file_count
        records = []
        hashes = {}
        for path in sorted((w / "runs" / model / split).glob("*.result.json")):
            raw = path.read_bytes()
            records.append(json.loads(raw))
            hashes[path.name] = score.sha256(raw)
            raw_digest.update(path.relative_to(w).as_posix().encode() + b"\0")
            raw_digest.update(hashlib.sha256(raw).digest())
            raw_file_count += 1
        return records, hashes

    gold = read("gold.json")["items"]
    if len({item["id"] for item in gold}) != len(gold) or any(
        item["split"] not in ("dev", "test") for item in gold
    ):
        raise ValueError("invalid gold IDs or splits")
    if {item["split_group"] for item in gold if item["split"] == "dev"} & {
        item["split_group"] for item in gold if item["split"] == "test"
    }:
        raise ValueError("gold source-page groups overlap dev and test")
    read("protocol.json")
    published = read("comparison.json")
    comparisons = {}
    for item in published:
        key = (item["model"], item["category"])
        if key in comparisons:
            raise ValueError("duplicate comparison model/category")
        comparisons[key] = item
    models = {}
    checks = []
    for path in sorted((w / "selection").glob("*/selection.json")):
        model = path.parent.name
        selection = read(f"selection/{model}/selection.json")
        if selection["model"] != model:
            raise ValueError("selection model differs from directory")
        launch = read(f"selection/{model}/test-launch.json")
        checks.append(
            comparison(
                f"receipt.{model}.launch_selection_sha256",
                launch["selection_SHA256"],
                sources[f"selection/{model}/selection.json"],
            )
        )
        for name, digest in selection["producer_files"].items():
            read(name, text=True)
            checks.append(comparison(f"receipt.{model}.producer.{name}", digest, sources[name]))
        records, hashes = run_records(model, "dev")
        checks.append(
            comparison(
                f"receipt.{model}.dev_file_count", len(selection["dev_receipt_hashes"]), len(hashes)
            )
        )
        checks.append(
            comparison(
                f"receipt.{model}.dev_hashes_equal", True, hashes == selection["dev_receipt_hashes"]
            )
        )
        dev_rows = convert_rows(gold, records, model, "dev")
        dev_groups = score.partitions(dev_rows)
        if set(selection["categories"]) != {category for _, category in dev_groups}:
            raise ValueError("selection categories differ from gold dev categories")
        receipts = {category: dev_receipt(rows) for (_, category), rows in dev_groups.items()}
        records, _ = run_records(model, "test")
        test_rows = convert_rows(
            gold,
            records,
            model,
            "test",
            {category: receipt["question"] for category, receipt in receipts.items()},
        )
        test_groups = score.partitions(test_rows)
        saved_metrics = read(f"evaluation/{model}/metrics.json")["categories"]
        models[model] = {}
        for category, receipt in receipts.items():
            prefix = f"selection.{model}.{category}"
            saved = selection["categories"][category]
            for field in (
                "question",
                "dev_n",
                "threshold",
                "dev_verified",
                "dev_changed",
                "dev_error_rate",
            ):
                checks.append(comparison(f"{prefix}.{field}", saved[field], receipt[field]))
            for question in ("Q1", "Q2"):
                checks.append(
                    comparison(
                        f"{prefix}.dev_AUROC.{question}",
                        saved["dev_AUROC"][question],
                        receipt["dev_AUROC"][question],
                    )
                )
            for label in ("correct", "minor", "meaning_changed"):
                checks.append(
                    comparison(
                        f"{prefix}.dev_label_counts.{label}",
                        saved["dev_label_counts"].get(label, 0),
                        receipt["dev_label_counts"].get(label, 0),
                    )
                )
            fitted = receipt["calibrator"]
            state = "FIT" if fitted else "UNFITTABLE_SINGLE_CLASS"
            checks.append(
                comparison(f"{prefix}.calibrator.state", saved["calibrator"]["state"], state)
            )
            for field in ("a", "b", "objective", "n", "positives", "negatives"):
                checks.append(
                    comparison(
                        f"{prefix}.calibrator.{field}",
                        saved["calibrator"].get(field),
                        fitted.get(field) if fitted else None,
                    )
                )
            metrics = historical_metrics(test_groups.get((model, category), []), receipt)
            models[model][category] = {"dev": receipt, "test": metrics}
            target = saved_metrics[category]
            prefix = f"evaluation.{model}.{category}"
            for field in (
                "test_n",
                "valid",
                "failed_or_NOT_RUN",
                "source_page_groups",
                "AUROC_raw",
                "ECE_before",
                "ECE_after",
                "verified",
                "verified_changed",
                "verified_error_rate",
                "coverage",
            ):
                checks.append(comparison(f"{prefix}.{field}", target[field], metrics[field]))
            for field, keys in (
                ("label_counts", ("correct", "minor", "meaning_changed")),
                ("status_counts", ("verified", "disputed", "unverified", "failed")),
            ):
                for key in keys:
                    checks.append(
                        comparison(
                            f"{prefix}.{field}.{key}",
                            target[field].get(key, 0),
                            metrics[field][key],
                        )
                    )
            interval = metrics["verified_error_Wilson95"]
            saved_interval = target["verified_error_Wilson95"]
            if interval is None or saved_interval is None:
                checks.append(comparison(f"{prefix}.risk_Wilson95", saved_interval, interval))
            else:
                for index, end in enumerate(("lower", "upper")):
                    checks.append(
                        comparison(
                            f"{prefix}.risk_Wilson95.{end}", saved_interval[index], interval[index]
                        )
                    )
            target = comparisons[model, category]
            for old, new in (
                ("test_n", "test_n"),
                ("AUROC", "AUROC_raw"),
                ("ECE_before", "ECE_before"),
                ("ECE_after", "ECE_after"),
                ("verified", "verified"),
                ("changed_in_verified", "verified_changed"),
                ("verified_error_rate", "verified_error_rate"),
                ("coverage", "coverage"),
            ):
                checks.append(
                    comparison(f"comparison.{model}.{category}.{old}", target[old], metrics[new])
                )
            for field in ("question", "threshold"):
                checks.append(
                    comparison(
                        f"comparison.{model}.{category}.{field}", target[field], receipt[field]
                    )
                )
    expected = {
        (model, category) for model, categories in models.items() for category in categories
    }
    if not expected or set(comparisons) != expected:
        raise ValueError("comparison partitions differ from selections")
    checks.extend(published_checks(read("report.md", text=True), models))
    full = [check for check in checks if not check["number"].startswith("report.")]
    display = [check for check in checks if check["display_match"] is not None]
    unknown = [check for check in checks if check["cause"] == "UNKNOWN"]
    summary = {
        "checks": len(checks),
        "matched": sum(check["match"] for check in checks),
        "full_precision_checks": len(full),
        "full_precision_match": all(check["match"] for check in full),
        "max_full_precision_error": max(
            (check["absolute_error"] or 0 for check in full), default=0
        ),
        "display_rounding_differences": sum(
            check["cause"] not in (None, "UNKNOWN") for check in checks
        ),
        "unexplained_mismatches": len(unknown),
        "published_display_match": all(check["display_match"] for check in display),
        "raw_result_files": raw_file_count,
    }
    return {
        "summary": summary,
        "checks": checks,
        "models": models,
        "policy": {
            "C1": "bypassed for historical comparison",
            "disputed": "raw < 0.5 after verified",
            "bootstrap": "not part of historical comparison",
        },
        "source_files_sha256": sources,
        "raw_results_sha256": raw_digest.hexdigest(),
        "versions": {"numpy": np.__version__, "scipy": scipy.__version__},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("w_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output.resolve().is_relative_to(args.w_dir.resolve()):
            raise ValueError("output must be outside read-only W4b inputs")
        result = reproduce(args.w_dir)
        score.write_json(args.output, result, [])
    except (ValueError, KeyError, TypeError, AttributeError, IndexError, OSError) as error:
        parser.exit(2, f"reproduction input error: {error}\n")
    print(json.dumps(result["summary"], sort_keys=True))
    summary = result["summary"]
    if (
        not summary["full_precision_match"]
        or summary["unexplained_mismatches"]
        or not summary["published_display_match"]
    ):
        parser.exit(1, "reproduction contains unresolved mismatches\n")


if __name__ == "__main__":
    main()
