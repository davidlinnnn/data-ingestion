"""Reuse the R3 sequential resource supervisor; only the official backend changes."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
R3 = ROOT.parent / "pdf-core-w2-native-coverage-round3-2026-10-20"
R2 = ROOT.parent / "pdf-core-w2-native-coverage-round2-2026-10-20"
DEADLINE = "2026-10-20T08:37:37+00:00"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def child(job_id):
    from docling.document_converter import PdfFormatOption
    from docling.backend.docling_parse_backend import ThreadedDoclingParseDocumentBackend
    from docling.datamodel.pipeline_options import HeadingHierarchyOptions
    assert PdfFormatOption.model_fields["backend"].default is ThreadedDoclingParseDocumentBackend
    module = load_module("round4_worker", ROOT / "worker.py")
    job = next(j for j in module.JOBS if j["id"] == job_id)
    assert sha(Path(job["pdf"])) == job["pdf_sha256"]
    original_options = module.options

    def options():
        opts = original_options()
        opts.generate_page_images = False
        opts.generate_picture_images = False
        opts.heading_hierarchy_options = HeadingHierarchyOptions(
            enabled=True, use_bookmarks=True, use_numbering=False, use_style=False)
        expected = json.loads((R2 / "effective-options.json").read_text())
        actual = opts.model_dump(mode="json", serialize_as_any=True)
        canonical = load_module("round3_option_comparison", R3 / "run_round3.py").canonical_options
        delta = sorted(k for k in actual if canonical(actual[k]) != canonical(expected[k]))
        assert delta == ["generate_page_images", "generate_picture_images", "heading_hierarchy_options"], delta
        assert opts.use_reading_order_separators
        save(ROOT / "runs/V4/option-diff.json", {
            "versus_original_S0": delta,
            "versus_selected_R3_profile": "Only backend; image-off and B-only already selected",
            "backend": "ThreadedDoclingParseDocumentBackend"})
        return opts

    module.HERE = ROOT / "runs/V4"
    module.JOBS = [job]
    module.options = options
    module.verify_registration = lambda: json.loads((ROOT / "registration.json").read_text())
    module.worker(0)
    identity = json.loads((module.HERE / "runtime-identity.json").read_text())
    identity.update(round4_runner_sha256=sha(Path(__file__)), original_worker_sha256=sha(R2 / "run_full.py"),
                    official_default_backend=True, conversion_retries=0, heading="bookmark-only")
    save(module.HERE / "jobs" / job_id / "runtime-identity.json", identity)


def parent():
    supervisor = load_module("readonly_round3_supervisor", R3 / "run_round3.py")
    supervisor.HERE = ROOT
    supervisor.__file__ = str(Path(__file__).resolve())
    supervisor.DEADLINE = datetime.datetime.fromisoformat(DEADLINE).timestamp()
    supervisor.run("V4")


if __name__ == "__main__":
    if sys.argv[1:3] == ["--child", "V4"]:
        child(sys.argv[3])
    elif sys.argv[1:] == ["--run", "V4"]:
        parent()
    else:
        raise SystemExit("--run V4 or --child V4 <id>")
