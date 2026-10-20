"""Observed resources only; failed preflight initialization is not a conversion retry."""
import json
import statistics
from pathlib import Path

HERE=Path(__file__).resolve().parent


def stats(values):
    return dict(n=len(values),p50=statistics.median(values) if values else None,max=max(values) if values else None)


def main():
    runs=[]
    for name in ("controls-v1","recovery","V1","V2-official"):
        folder=HERE/"runs"/name
        execution=json.loads((folder/"execution.json").read_text())
        perpaper=[];pages=[]
        for record in execution["records"]:
            job=record["id"];dest=folder/"jobs"/job
            conv=json.loads((dest/"conversion.json").read_text())
            initialization=json.loads((dest/"initialization-00.json").read_text()) if (dest/"initialization-00.json").exists() else {}
            perpaper.append(dict(**record,conversion_wall_seconds=conv.get("wall_seconds"),
                conversion_cpu_seconds=conv.get("cpu_seconds"),initialization=initialization))
            if not (dest/"stage-events.json").exists():continue
            events=json.loads((dest/"stage-events.json").read_text())
            for page in sorted({e["page"] for e in events}):
                local=[e for e in events if e["page"]==page]
                start=[e["start"] for e in local if e["stage"]=="preprocess"]
                end=[e["end"] for e in local if e["stage"]=="assemble"]
                if not start or not end:continue
                start=min(start);end=max(end)
                samples=[s for s in execution["samples"] if s["job"]==job and start<=s["monotonic"]<=end]
                pages.append(dict(job=job,page=page,residence_seconds=end-start,
                    service_seconds=sum(e["wall_seconds"] for e in local),
                    process_tree_peak_rss_bytes=max((s["rss"] for s in samples),default=None)))
        runs.append(dict(run=name,attempts=len(perpaper),successful=sum(r["status"]=="success" for r in perpaper),
            selected_pages=sum(r["pages"] for r in perpaper),wall_seconds=execution["wall_seconds"],
            conversion_wall_seconds=sum(r["conversion_wall_seconds"] or 0 for r in perpaper),
            measured_conversion_cpu_seconds=sum(r["conversion_cpu_seconds"] or 0 for r in perpaper),
            measured_initialization_cpu_seconds=sum(r["initialization"].get("cpu_seconds",0) for r in perpaper),
            peak_tree_rss_bytes=execution["peak_tree_rss_bytes"],
            minimum_host_available_bytes=min(s["available"] for s in execution["samples"]),
            residence_seconds=stats([r["residence_seconds"] for r in pages]),
            stage_service_seconds=stats([r["service_seconds"] for r in pages]),
            perpage_tree_rss_bytes=stats([r["process_tree_peak_rss_bytes"] for r in pages if r["process_tree_peak_rss_bytes"] is not None]),
            papers=perpaper,pages=pages))
    data=dict(definition="All actual conversions used fresh sequential CPU4 workers, 12 GiB sampled RSS guard and host available >=4GiB. Residence overlaps queued pages; cannot be summed as total run wall. Process RSS is not page-exclusive memory.",
              actual_conversion_calls=sum(r["attempts"] for r in runs),converted_page_attempts=sum(r["selected_pages"] for r in runs),
              pipeline_wall_seconds=sum(r["wall_seconds"] for r in runs),
              known_conversion_and_initialization_cpu_seconds=sum(r["measured_conversion_cpu_seconds"]+r["measured_initialization_cpu_seconds"] for r in runs),
              preflight_failures=dict(option_serialization_set_order=2,legacy_egret_model_spec_type=36,conversion_calls=0),runs=runs)
    assert data["actual_conversion_calls"]==80 and data["converted_page_attempts"]==1685
    (HERE/"resources.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in data.items() if k!="runs"},indent=2))


if __name__=="__main__":
    assert stats([1,3,2])==dict(n=3,p50=2,max=3)
    main()
