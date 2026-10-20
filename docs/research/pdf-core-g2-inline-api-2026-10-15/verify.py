"""Offline aggregate evidence checks; never calls a model or accesses credentials."""

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REPORT = HERE.with_suffix(".md")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


assert sha(REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json") == "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
assert sha(HERE / "inputs/input-manifest.json") == "c87899f88b96553f9dc856d020adafdea7281938b00fb121a5f358b6a1a75f0d"
prior = {}
for name in ["pdf-core-g2-local-cpu-2026-10-14", "pdf-core-g2-round2-2026-10-14",
             "pdf-core-g2-round3-2026-10-14", "pdf-core-g2-api-2026-10-14",
             "pdf-core-g2-images-2026-10-14", "pdf-core-g2-heading-2026-10-15",
             "pdf-core-g2-orientation-2026-10-15", "pdf-core-g2-inline-2026-10-15"]:
    records = read(REPO / "docs/research" / name / "artifacts.json")["files"]
    for record in records:
        path = REPO / record["path"]
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
    prior[name] = len(records)
assert sum(prior.values()) == 1517
lanes = {}
for lane in ("inputs", "parsed", "reinsertion"):
    manifest = read(HERE / lane / "artifact-sha256.json")
    for name, expected in manifest.items():
        assert sha(HERE / lane / name) == expected, (lane, name)
    lanes[lane] = len(manifest)
for name, expected in read(HERE / "source-audit.json")["source_sha256"].items():
    assert sha(REPO / name) == expected, name

api = read(HERE / "api/verification.json")
assert api["checks"] == "passed" and api["selected"] == api["observed_responses"] == 22
assert api["all_selected_completed_contract_valid"]
for key, path in [("verifier_sha256", "api/verify.py"), ("runner_sha256", "api/run.py"),
                  ("method_sha256", "api/method.json"), ("observations_sha256", "api/observations.json")]:
    assert api[key] == sha(HERE / path)
observations = read(HERE / "api/observations.json")
assert len(observations) == 22 and len({r["request_id"] for r in observations}) == 22
assert all(r["http_status"] == 200 and r["finish_reason"] == "stop" and r["attempts"] == 1 for r in observations)
assert {r["returned_model"] for r in observations} == {"gpt-6-luna"}
assert read(HERE / "inputs/verification.json")["exact_old_png_bytes_referenced"]
parsed = read(HERE / "parsed/summary.json")
assert parsed["parser_sha256"] == sha(HERE / "parsed/parse.py") and len(parsed["outcomes"]) == 22
for lane in ("parsed", "reinsertion"):
    assert read(HERE / lane / "selfcheck.json")["passed"]
association = read(HERE / "reinsertion/verification.json")
assert association["passed"] and len(association["parsed_inputs"]) == 22
assert association["structurally_applied"] == 11 and association["not_applied"] == 6

review = read(HERE / "review/output-review.json")
assert review["checker_sha256"] == sha(HERE / "review/check.py")
assert review["completed_runs"] == 22 and review["all_outputs_present"]
assert review["selfchecks"]["all_rejected"] and len(review["selfchecks"]["controls"]) >= 11
assert all(review["selfchecks"]["controls"].values())
assert not review["reinsertion"]["errors"]
for case in ("G1-E14", "G1-E13"):
    assert review["frozen_case_semantics"][case]["paragraph"]["bounded_F13_delivery_pass"]
assert not review["frozen_case_semantics"]["G1-E14"]["page"]["bounded_F13_delivery_pass"]
ticket = read(HERE / "ticket-update.json")
assert ticket["comment_exact_readback"] and ticket["issue_body_exact_readback"]
assert ticket["feature_rows_unchanged"] == 44 and ticket["issue_state"] == "OPEN"

links = 0
human_docs = [REPORT, *(p for p in HERE.rglob("*.md") if p.name not in {"document.md", "candidate.md", "baseline.md"}),
    *(HERE.parent / name for name in ("README.md", "docling-pdf-core-capability-validation-plan-2026-10-14.md", "docling-pdf-core-g2-pipeline-start-2026-10-14.md"))]
for path in human_docs:
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        target = re.sub(r":\d+$", "", target.split("#")[0])
        linked = (path.parent / target).resolve()
        assert linked.exists() or linked in {HERE / "artifacts.json", HERE / "validation.json"}, (path, target)
        links += 1

files = []
for path in sorted([REPORT, *HERE.rglob("*")]):
    if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts:
        continue
    if path in {HERE / "artifacts.json", HERE / "validation.json"}:
        continue
    if path.suffix in {".md", ".json", ".jsonl", ".log", ".py", ".yaml", ".yml", ".txt", ".toml"}:
        assert not re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", path.read_text()), "Possible credential; never print matching text"
    files.append({"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size, "sha256": sha(path)})
save(HERE / "artifacts.json", {"scope": "Owned inline API report and payloads, no model cache or Python caches; prior artifacts referenced unchanged", "files": files})
save(HERE / "validation.json", {"g1_registry_and_prior_payloads_unchanged": prior,
    "lane_payloads_unchanged": lanes, "exact_same_png_inputs": 22, "one_attempt_completed_api_calls": 22,
    "all_contracts_valid_is_not_semantic_approval": True, "structural_applications": 11, "explicit_abstentions": 6,
    "independent_tamper_controls": len(review["selfchecks"]["controls"]),
    "ticket_summary_exact_readback_and_44_feature_rows_preserved": True,
    "credential_pattern_scan_clean": True, "local_markdown_links_checked": links,
    "payload_files": len(files), "payload_bytes": sum(r["bytes"] for r in files)})
print(json.dumps(read(HERE / "validation.json")))
