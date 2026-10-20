"""Saved observed costs, keeping harness failures and censored attempts explicit."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text())


def main():
    runs = []
    for name in ("E1_pilot", "E1_sampled", "E1_sampled_v2"):
        root = HERE / "runs" / name
        if not root.exists():
            continue
        execution = root / "execution.json"
        progress = root / "progress.json"
        data = load(execution) if execution.exists() else load(progress) if progress.exists() else {"records": []}
        records = data["records"]
        papers = []
        for directory in sorted((root / "jobs").iterdir()):
            jobid = directory.name
            supervised = next((r for r in records if r["id"] == jobid), None)
            conv = load(directory / "conversion.json") if (directory / "conversion.json").exists() else None
            batches = load(directory / "enrichment-batches.json") if (directory / "enrichment-batches.json").exists() else []
            papers.append(dict(job_id=jobid, conversion=conv, supervision=supervised,
                               enrichment_batches=len(batches),
                               enrichment_items=sum(len(b["inputs"]) for b in batches),
                               enrichment_wall_seconds=sum(b["wall_seconds"] for b in batches),
                               enrichment_cpu_seconds=sum(b["cpu_seconds"] for b in batches),
                               resource_censored=supervised is None or conv is None))
        runs.append(dict(run=name, completed_execution_file=execution.exists(),
                         observed_run_wall_seconds=data.get("wall_seconds"),
                         attempts=len(papers), completed_supervision_records=len(records),
                         successful=sum(p["conversion"] is not None and p["conversion"]["status"] == "success" for p in papers),
                         sampled_peak_tree_rss_bytes=max((r["peak_tree_rss_bytes"] for r in records), default=0),
                         known_attempt_wall_seconds=sum(r["attempt_wall_seconds"] for r in records),
                         known_conversion_cpu_seconds=sum((p["conversion"] or {}).get("cpu_seconds", 0) for p in papers),
                         measured_enrichment_wall_seconds=sum(p["enrichment_wall_seconds"] for p in papers),
                         measured_enrichment_cpu_seconds=sum(p["enrichment_cpu_seconds"] for p in papers),
                         censored_attempts=[p["job_id"] for p in papers if p["resource_censored"]], papers=papers))
    result = dict(E0=load(HERE / "E0-resources.json"), E1=dict(
        runs=runs, actual_conversion_attempts=sum(r["attempts"] for r in runs),
        unique_documents=len({p["job_id"] for r in runs for p in r["papers"]}),
        successful_attempts=sum(r["successful"] for r in runs),
        known_attempt_wall_seconds=sum(r["known_attempt_wall_seconds"] for r in runs),
        known_conversion_cpu_seconds=sum(r["known_conversion_cpu_seconds"] for r in runs),
        measured_enrichment_wall_seconds=sum(r["measured_enrichment_wall_seconds"] for r in runs),
        measured_enrichment_cpu_seconds=sum(r["measured_enrichment_cpu_seconds"] for r in runs),
        peak_sampled_tree_rss_bytes=max((r["sampled_peak_tree_rss_bytes"] for r in runs),default=0),
        failures_not_model_quality="Initial gate keyword mismatch: five failed conversions and one interrupted attempt before any enrichment; preserved and charged separately. One explicit repaired harness restart, not hidden retries.",
        limitations="Partial batches in active/timed-out conversions may be observed, but completed-document scores require success marker. Censored attempt costs are lower bounds; summed attempt walls are not the task end-to-end wall; process RSS is not per-element exclusive memory."))
    (HERE / "resources.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:v for k,v in result["E1"].items() if k not in ("runs","failures_not_model_quality","limitations")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
