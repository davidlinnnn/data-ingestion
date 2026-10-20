"""Verify the actual resource-stop outcome without rerunning inference."""
import sys

from run import HERE, read, sha, verify, write


def main():
    registration = verify()
    folder = HERE / "V5"
    execution = read(folder / "execution.json")
    assert execution["status"] == "time_or_memory_budget_stop" and execution["exit_code"] == -9
    budgets = registration["budgets"]
    samples = execution["samples"]
    assert samples and samples[-1]["available"] < budgets["available_floor_bytes"]
    assert execution["seconds"] < budgets["profile_seconds"]
    assert execution["seconds"] < budgets["page_and_init_seconds"]
    assert execution["peak_sampled_tree_rss_bytes"] < budgets["max_tree_rss_bytes"]
    assert execution["API_calls"] == execution["automatic_retries"] == 0
    attempts = list(folder.rglob("attempt.json"))
    assert attempts == [folder / "known/attempt.json"]
    assert read(attempts[0])["attempt"] == 1
    assert not list(folder.rglob("result.json")) and not list(folder.rglob("document.json"))
    assert not list((HERE / "initialization-only-failure").rglob("attempt.json"))
    actual = read(folder / "actual-models.json")
    for task in ("Det", "Rec"):
        model = registration["model_receipt"]["models"][task.lower()]
        assert actual["models"][task]["sha256"] == model["expected_sha256"] == sha(model["path"])
        assert actual["resolved_config"][task]["ocr_version"] == "PP-OCRv5"
        assert actual["resolved_config"][task]["model_type"] == "server"
    assert all(p == ["CPUExecutionProvider"] for p in actual["providers"].values())
    assert actual["models"]["Cls"]["sha256"] == sha(actual["models"]["Cls"]["path"])
    assert sha(folder / "recognizer-dictionary.txt") == actual["recognizer_dictionary"]["sha256"]
    assert not (HERE / "validation-run").exists()
    review = read(HERE / "resource-review.json")
    assert review["quality_decision"] == "INCONCLUSIVE_RESOURCE_STOP"
    assert review["completed_pages"] == 0 and review["attempted_pages"] == 1
    assert review["additional_page_inferences"] == 0
    previous = []
    for name in ("pdf-core-ocr-regression-2026-10-19", "pdf-core-ocr-official-options-2026-10-19",
                 "pdf-core-ocr-crop-ablation-2026-10-19", "pdf-core-ocr-region-policy-2026-10-20",
                 "pdf-core-official-multicol-2026-10-20", "pdf-core-order-tessbest-2026-10-20"):
        path = HERE.parent / name
        seal = read(path / "artifact-seal.json")
        files = seal["files"] if "files" in seal else seal["artifacts"]
        assert all(sha(path / p) == digest for p, digest in files.items()), name
        previous.append({"folder": name, "unchanged_files": len(files)})
    summary = {"state": "stopped_at_frozen_resource_boundary", "quality_decision": "INCONCLUSIVE_RESOURCE_STOP",
        "attempted_pages": 1, "completed_pages": 0, "additional_page_inferences": 0,
        "initializations": 2, "first_initialization_stopped_before_any_page": True,
        "page_inference_retries": 0, "API_calls": 0, "actual_model_and_provider_verified": True,
        "stop_reason": "host_available_memory_below_8_GiB", "historical_seals_unchanged": previous}
    if sys.argv[1:] == ["--seal"]:
        assert not (HERE / "artifact-seal.json").exists()
        write(HERE / "final-verification.json", summary)
        files = {str(p.relative_to(HERE)): sha(p) for p in sorted(HERE.rglob("*"))
                 if p.is_file() and "__pycache__" not in p.parts}
        write(HERE / "artifact-seal.json", {"state": "resource_stop", "files": files})
    elif not sys.argv[1:]:
        assert read(HERE / "final-verification.json") == summary
        assert all(sha(HERE / p) == digest for p, digest in read(HERE / "artifact-seal.json")["files"].items())
    else:
        raise SystemExit("use --seal once, then no arguments")
    print("Verified: host-available-memory guard stopped the first page; zero complete pages, no quality verdict, no retries; six historical seals unchanged.")


if __name__ == "__main__":
    main()
