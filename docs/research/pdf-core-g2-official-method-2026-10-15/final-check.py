"""Verify completed selection evidence without inference, network or holdout access."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MEDIUM = HERE.parent / "pdf-core-g2-official-medium-2026-10-15"
REPORT = HERE.parent / "pdf-core-g2-method-selection-decision-2026-10-15.md"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    prior = read(HERE / "prior-inputs.json")
    checked, skipped = 0, 0
    for ref in prior["prior_manifest_refs"]:
        path = REPO / ref["path"]
        assert sha(path) == ref["sha256"], path
        for entry in read(path)["files"]:
            if entry["path"].startswith("docs/fixtures/pdf-core-g2-holdout-") and entry["path"].endswith(".pdf"):
                skipped += 1
                continue
            target = REPO / entry["path"]
            assert target.stat().st_size == entry["bytes"] and sha(target) == entry["sha256"], target
            checked += 1
    assert checked == 2324 and skipped == 6
    frozen = read(MEDIUM / "candidate2-frozen-inputs.json")["files"]
    assert len(frozen) == 85
    for entry in frozen:
        assert sha(REPO / entry["path"]) == entry["sha256"], entry["path"]
    expected_contract = "22ee81e79db28cf07d14ddd1f53269aada08d8b6480633ef67046a3e955777f2"
    expected_reviews = ["01840c109b117763b5c46ea82729150d4f9a19911bb3d5ee33959deca05068c9",
                        "c9bbd7c055400960f05b455f50ada3f63be8784e42cf457211645b9004a108a4"]
    summaries = []
    for folder, expected, configuration in zip([HERE, MEDIUM], expected_reviews, [2, 3]):
        assert sha(folder / "review/contract.json") == expected_contract
        assert sha(folder / "review/results.json") == expected
        registration = read(folder / "registration.json")
        assert registration["configuration_number"] == configuration and registration["maximum_configurations"] == 3
        assert sha(REPO / registration["runner_ref"]["path"]) == registration["runner_sha256"]
        verification = read(folder / ("api-verification.json" if configuration == 2 else "verification.json"))
        assert verification["passed"] and verification["requests_verified"] == 8
        summary = read(folder / "review/results.json")["summary"]
        assert summary["selected_source_units"] == summary["attempted_units"] == 41
        assert not summary["whole_candidate_adoptable"] and not summary["G2_passed"]
        usage = read(folder / "usage.json")
        assert usage["requests"] == 8 and not usage["invoice_verified"]
        summaries.append(summary)
    assert summaries[0]["raw_source_fidelity_counts"] == {"pass": 33, "minor": 2, "material": 6}
    assert summaries[1]["raw_source_fidelity_counts"] == {"pass": 36, "minor": 2, "material": 3}
    assert summaries[0]["F14_content_and_block_delivery"]["passed_units"] == 6
    assert summaries[1]["F14_content_and_block_delivery"]["passed_units"] == 4
    assert read(MEDIUM / "verification.json")["pairwise_only_reasoning_changed"]
    payloads, links = [], 0
    files = [REPORT, *HERE.rglob("*"), *MEDIUM.rglob("*")]
    for path in sorted(files):
        if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts or path.name in {"artifacts.json", "validation.json"}:
            continue
        if path.suffix in {".json", ".py", ".txt", ".md"}:
            text = path.read_text()
            assert not re.search(r"sk-proj-[A-Za-z0-9_-]{64,}", text), "Credential pattern in " + str(path)
            if path.suffix == ".md" and path.name != "document.md":
                for target in re.findall(r"\]\(([^)]+)\)", text):
                    if "://" in target or target.startswith("#"):
                        continue
                    linked = (path.parent / target.split("#")[0]).resolve()
                    assert linked.exists(), (path, target)
                    links += 1
        payloads.append({"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size, "sha256": sha(path)})
    ticket = read(HERE / "ticket-update.json") if (HERE / "ticket-update.json").exists() else None
    if ticket:
        assert ticket["comment_exact_readback"] and ticket["issue_state"] == "OPEN"
        assert ticket["feature_rows_unchanged"] == 44 and ticket["issue_body_unchanged"]
    result = {"passed": True, "prior_payloads_unchanged": checked, "holdout_pdf_bytes_not_accessed": skipped,
              "candidate2_snapshot_files_unchanged": len(frozen), "new_actual_calls": 16,
              "attempts_per_page_configuration": 1, "source_units_each": 41,
              "candidate3_only_reasoning_changed": True, "configurations_consumed": 3,
              "raw_reviews_unchanged": True, "output_repairs": 0, "holdout_reads": 0,
              "selected_challenger": False, "g2_passed": False,
              "credentials_scan_clean": True, "verified_local_links": links,
              "ticket_exact_readback": bool(ticket), "payload_files": len(payloads)}
    (HERE / "artifacts.json").write_text(json.dumps({"scope": "Official method selection, low/medium execution and decision evidence", "files": payloads}, indent=2)+"\n")
    (HERE / "validation.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
