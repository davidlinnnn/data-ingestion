"""Check saved association spans, immutable provider inputs and outside-scope serialization."""

import importlib.util
from pathlib import Path

from docling_core.types.doc import DoclingDocument

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("inline_reinsertion", HERE / "apply.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def main():
    manifest = adapter.check_inputs()
    plan = adapter.read(HERE / "plan.json")
    checks = []
    for variant in ("component", "token-aware"):
        total, applied = 0, 0
        for source in manifest["sources"]:
            folder = HERE / variant / source["name"]
            structure = adapter.read(folder / "inline-structure.json")
            candidate_markdown = (folder / "candidate.md").read_text()
            raw = adapter.read(adapter.REPO / source["document_path"])
            document = DoclingDocument.model_validate(raw)
            assert (folder / "baseline.md").read_text() == document.export_to_markdown()
            rows = [r for r in plan["rows"] if r["source"] == source["name"]]
            assert {r["candidate_id"] for r in rows} == {r["candidate_id"] for r in structure["candidates"]}
            accepted = [r for r in structure["candidates"] if r["status"] != "not_applied"]
            adapter.validate_batch(raw, rows, accepted)
            expected_markdown, ranges = adapter.render(document, accepted)
            assert candidate_markdown == expected_markdown
            for row in structure["candidates"]:
                total += 1
                assert adapter.sha(adapter.REPO / row["raw_output_path"]) == row["raw_output_sha256"]
                assert adapter.sha(adapter.REPO / row["parsed_document_path"]) == row["parsed_document_sha256"]
                if row["status"] == "not_applied":
                    assert row["main_markdown_charspan"] is None and row["reason"]
                    continue
                applied += 1
                start, end = row["main_markdown_charspan"]
                assert ranges[row["candidate_id"]] == [start, end]
                assert candidate_markdown[start:end] == row["markdown"]
                for span in row["inline_spans"]:
                    left, right = span["markdown_charspan"]
                    assert row["markdown"][left:right] == span["raw_markup"]
                assert all(n["before_sha256"] == n["after_sha256"] and n["unchanged"] for n in row["neighbor_checks"])
            checks.append({"variant": variant, "source": source["name"],
                "outside_scope_serialization_unchanged": True, "output_spans_exact": True,
                "raw_provider_and_model_payloads_unchanged": True})
        assert total == 17
        summary = adapter.read(HERE / variant / "summary.json")
        assert summary["status_counts"].get("structurally_applied_semantic_quality_unverified", 0) == applied
    adapter.check_inputs()
    adapter.save(HERE / "verification.json", {"passed": True,
        "scope": "Saved-output association and immutable-source integrity; no semantic-quality verdict", "checks": checks})
    print("Both saved reinsertion variants verified; original source/provider/model payload hashes intact.")


if __name__ == "__main__":
    main()
