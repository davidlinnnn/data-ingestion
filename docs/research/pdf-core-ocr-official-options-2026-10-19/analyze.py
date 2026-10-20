"""Reuse frozen source diagnostics; never turn flags into an automatic pass."""
import importlib.util
import json
import statistics
from pathlib import Path
from run import BASE, HERE, PROFILES, read, sha, verify, write

spec = importlib.util.spec_from_file_location("frozen_evaluator", BASE / "evaluate.py")
evaluator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluator)


def analyze():
    registration = verify()
    refs = {page["id"]: page for page in read(BASE / "corpus/reference.json")["pages"]}
    refs["known"] = read(BASE / "known-reference.json")
    summary = {}
    for profile in PROFILES:
        root = HERE / profile
        if not (root / "execution.json").exists():
            continue
        execution = read(root / "execution.json")
        rows = []
        for job in registration["jobs"]:
            path = root / job["id"]
            if not (path / "execution.json").exists():
                continue
            metric = read(path / "execution.json")
            row = {"id": job["id"], "status": metric["status"], "seconds": metric["seconds"]}
            if metric["status"] == "success":
                cells, document = read(path / "cells.json"), read(path / "document.json")
                score = evaluator.evaluate(cells, document, refs[job["id"]])
                if (path / "score.json").exists():
                    assert read(path / "score.json") == score
                else:
                    write(path / "score.json", score)
                row.update({"raw_mix_flags": len(score["raw_cells"]["cross_column_mixed_elements"]),
                    "document_mix_flags": len(score["document"]["cross_column_mixed_elements"]),
                    "omission_flags": score["document"]["whole_unit_omission_candidates"],
                    "critical_difference_flags": score["document"]["critical_text_difference_candidates"],
                    "incomplete_lines": len(score["document"]["incomplete_source_line_candidates"]),
                    "cells_sha256": sha(path / "cells.json"), "document_sha256": sha(path / "document.json")})
            rows.append(row)
        summary[profile] = {"execution_status": execution["status"], "pages": rows,
            "page_seconds_total": sum(r["seconds"] for r in rows),
            "page_seconds_median": statistics.median(r["seconds"] for r in rows) if rows else None,
            "peak_sampled_tree_rss_bytes": execution["peak_sampled_tree_rss_bytes"],
            "qualification": "REVIEW_REQUIRED"}
    write(HERE / "diagnostics.json", summary)
    print(json.dumps({p: {"status": r["execution_status"], "known": r["pages"][0] if r["pages"] else None} for p,r in summary.items()},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    analyze()
