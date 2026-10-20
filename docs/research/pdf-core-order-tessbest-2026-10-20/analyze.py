"""Compare the one new candidate to cached controls; source review decides acceptance."""
from run import BASE, HERE, read, sha, verify, write
from trace_order import audit

CONTROLS = {"T-fast": BASE / "T1", "Rapid-full": HERE.parent / "pdf-core-ocr-official-options-2026-10-19/full"}


def main():
    registration = verify()
    refs = {p["id"]: p for p in read(BASE / "corpus/reference.json")["pages"]}
    refs["known"] = read(BASE / "known-reference.json")
    results = {}
    for name, folder in {**CONTROLS, "TB": HERE / "TB"}.items():
        execution = read(folder / "execution.json")
        rows = []
        for job in registration["jobs"]:
            page = folder / job["id"]
            run = read(page / "execution.json")
            row = {"id": job["id"], "status": run["status"], "seconds": run["seconds"]}
            if run["status"] == "success":
                cells, doc, ref = read(page / "cells.json"), read(page / "document.json"), refs[job["id"]]
                score = audit.evaluator.evaluate(cells, doc, ref)
                order = audit.order_diagnostic(doc, ref)
                row.update(raw_mix_flags=len(score["raw_cells"]["cross_column_mixed_elements"]),
                    document_mix_flags=len(score["document"]["cross_column_mixed_elements"]),
                    omission_flags=score["document"]["whole_unit_omission_candidates"],
                    critical_difference_flags=score["document"]["critical_text_difference_candidates"],
                    order=order, document_sha256=sha(page / "document.json"), cells_sha256=sha(page / "cells.json"))
                if name == "TB":
                    write(page / "score.json", score)
                    write(page / "order.json", order)
                    row["markdown_equal_to_fast"] = (page / "document.md").read_bytes() == (CONTROLS["T-fast"] / job["id"] / "document.md").read_bytes()
            rows.append(row)
        results[name] = {"execution_status": execution["status"], "pages": rows,
            "page_seconds_total": sum(r["seconds"] for r in rows),
            "initialization_seconds": read(folder / "initialization.json")["seconds"],
            "peak_sampled_tree_rss_bytes": execution["peak_sampled_tree_rss_bytes"], "qualification": "REVIEW_REQUIRED"}
    write(HERE / "diagnostics.json", results)
    for name, value in results.items():
        print(name, "seconds", value["page_seconds_total"], "RSS GiB", value["peak_sampled_tree_rss_bytes"] / 2**30)
        for row in value["pages"]:
            print(row["id"], "mix", row.get("document_mix_flags"), "missing", row.get("omission_flags"),
                  "order", len(row.get("order", {}).get("inversion_candidates", [])))


if __name__ == "__main__":
    main()
