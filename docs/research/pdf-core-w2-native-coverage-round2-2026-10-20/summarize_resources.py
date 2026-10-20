"""Summarize observed residence latency, service time and sampled process RSS."""
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent


def summarize(values):
    return {"n": len(values), "p50": statistics.median(values) if values else None,
            "max": max(values) if values else None}


def main():
    execution = json.loads((HERE / "execution.json").read_text())
    jobs = json.loads((HERE / "jobs.json").read_text())["jobs"]
    samples = execution["samples"]
    rows, papers = [], []
    for job in jobs:
        folder = HERE / "jobs" / job["id"]
        record = json.loads((folder / "conversion.json").read_text())
        selected = [s for s in samples if s.get("job") == job["id"]]
        paper = dict(id=job["id"], selected_pages=job["last"]-job["first"]+1,
                     status=record["status"], conversion_wall_seconds=record.get("wall_seconds"),
                     conversion_cpu_seconds=record.get("cpu_seconds"),
                     observed_job_wall_seconds=(max(s["monotonic"] for s in selected)-min(s["monotonic"] for s in selected)) if selected else None,
                     sampled_peak_tree_rss_bytes=max((s["rss"] for s in selected), default=None))
        papers.append(paper)
        events_path = folder / "stage-events.json"
        if not events_path.exists():
            continue
        events = json.loads(events_path.read_text())
        for page in range(job["first"], job["last"]+1):
            pe = [e for e in events if e["page"] == page]
            starts = [e["start"] for e in pe if e["stage"] == "preprocess"]
            ends = [e["end"] for e in pe if e["stage"] == "assemble"]
            if not starts or not ends:
                continue
            begin, end = min(starts), max(ends)
            ps = [s for s in selected if begin <= s["monotonic"] <= end]
            rows.append(dict(id=job["id"], page=page, residence_wall_seconds=end-begin,
                stage_service_wall_seconds=sum(e["wall_seconds"] for e in pe),
                sampled_peak_tree_rss_bytes=max((s["rss"] for s in ps), default=None),
                rss_samples=len(ps), stages=[e["stage"] for e in pe]))
    result = dict(definition="Residence preprocess start to assemble end; overlapping queue latency, excludes document reading-order. RSS process-tree peak during residence, not page-exclusive memory.",
        selected_pages=715, completed_page_observations=len(rows),
        residence_wall_seconds=summarize([r["residence_wall_seconds"] for r in rows]),
        stage_service_wall_seconds=summarize([r["stage_service_wall_seconds"] for r in rows]),
        page_sampled_peak_tree_rss_bytes=summarize([r["sampled_peak_tree_rss_bytes"] for r in rows if r["sampled_peak_tree_rss_bytes"] is not None]),
        execution_wall_seconds=execution["wall_seconds"],
        successful_conversion_wall_seconds=sum(p["conversion_wall_seconds"] or 0 for p in papers),
        known_conversion_cpu_seconds=sum(p["conversion_cpu_seconds"] or 0 for p in papers),
        cpu_censored_jobs=[p["id"] for p in papers if p["conversion_cpu_seconds"] is None],
        peak_sampled_tree_rss_bytes=execution["peak_sampled_tree_rss_bytes"],
        minimum_host_available_bytes=min(s["available"] for s in samples),
        stops=execution["stops"], papers=papers, pages=rows)
    (HERE / "resources.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in {"papers", "pages"}}, indent=2))


if __name__ == "__main__":
    assert summarize([1, 5, 3]) == {"n": 3, "p50": 3, "max": 5}
    main()
