"""CPU4 offline E1; reuse pinned W2 conversion worker and resource supervisor."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
R2 = ROOT.parent / "pdf-core-w2-native-coverage-round2-2026-10-20"
R3 = ROOT.parent / "pdf-core-w2-native-coverage-round3-2026-10-20"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n")
    temp.replace(path)


def verify_oracle_freeze():
    seal = json.loads((ROOT / "oracle-freeze.json").read_text())
    for name, digest in seal["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    return seal


def child(name, jobid):
    verify_oracle_freeze()
    from docling.datamodel.pipeline_options import HeadingHierarchyOptions
    from docling.models.stages.code_formula.code_formula_vlm_model import CodeFormulaVlmModel
    worker = module("w3_saved_worker", ROOT / "worker.py")
    job = next(j for j in worker.JOBS if j["id"] == jobid)
    assert worker.sha(job["pdf"]) == job["pdf_sha256"]
    get_options = worker.options
    destination = ROOT / "runs" / name / "jobs" / jobid
    observer_events = []
    original_call = CodeFormulaVlmModel.__call__

    def observe(self, doc, element_batch):
        batch = list(element_batch)
        info = dict(index=len(observer_events), started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    inputs=[dict(ref=e.item.self_ref, label=str(e.item.label), text=e.item.text, orig=e.item.orig,
                                 prov=[p.model_dump(mode="json") for p in e.item.prov]) for e in batch])
        start, used = time.monotonic(), worker.cpu()
        save(destination / "enrichment-active-batch.json", info)
        results = list(original_call(self, doc, batch))
        info.update(wall_seconds=time.monotonic()-start, cpu_seconds=worker.cpu()-used,
                    outputs=[dict(ref=e.self_ref, label=str(e.label), text=e.text, orig=e.orig) for e in results])
        observer_events.append(info)
        save(destination / "enrichment-batches.json", observer_events)
        for result in results:
            yield result

    CodeFormulaVlmModel.__call__ = observe

    def options():
        opts = get_options()
        opts.generate_page_images = False
        opts.generate_picture_images = False
        opts.heading_hierarchy_options = HeadingHierarchyOptions(enabled=True, use_bookmarks=True, use_numbering=False, use_style=False)
        opts.do_formula_enrichment = True
        opts.do_code_enrichment = True
        assert opts.accelerator_options.num_threads == 4 and opts.use_reading_order_separators
        assert opts.code_formula_options.model_spec.default_repo_id == "docling-project/CodeFormulaV2"
        assert not any((opts.do_picture_description, opts.do_picture_classification, opts.do_chart_extraction, opts.enable_remote_services))
        save(ROOT / "runs" / name / "option-diff.json", dict(versus_selected_E0=["do_formula_enrichment", "do_code_enrichment"], images="off as registered", inference="local CodeFormulaV2 only", sample_gate="none"))
        return opts

    worker.HERE = ROOT / "runs" / name
    worker.JOBS = [job]
    worker.options = options
    worker.verify_registration = verify_oracle_freeze
    worker.worker(0)


def parent(name):
    verify_oracle_freeze()
    supervisor = module("w3_readonly_supervisor", R3 / "run_round3.py")
    supervisor.HERE = ROOT
    supervisor.__file__ = str(Path(__file__).resolve())
    supervisor.DEADLINE = datetime.datetime.fromisoformat("2026-10-20T11:00:05+00:00").timestamp()
    supervisor.run(name)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--child"]:
        child(sys.argv[2], sys.argv[3])
    elif sys.argv[1:2] == ["--run"]:
        parent(sys.argv[2])
    else:
        raise SystemExit("--run <plan> or --child <plan> <jobid>")
