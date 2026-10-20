"""Two offline CPU TableFormerV2 stage probes on unchanged first-round clusters."""

import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FIRST = ROOT / "docs/research/pdf-core-g2-local-cpu-2026-10-14/runs"
REGISTRY = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
CANDIDATE = Path("/private/tmp/issue72-table-upstream-20261011/candidate")
ARTIFACTS = Path("/private/tmp/issue72-table-v2-20261011/artifacts")
PYTHON = ROOT / "docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python"
JOBS = [("skillopt-p8", "G1-T02", 6), ("memory-r1-p8", "G1-T01", 9)]
REVISION = "51559fad3946873e26a6f9b8e912f948e8745bef"
LIMIT, TIMEOUT = 6 * 1024**3, 180


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def prepare():
    registry = json.loads(REGISTRY.read_text())
    originals = {str(REGISTRY): sha(REGISTRY)}
    for name, case_id, cluster_id in JOBS:
        folder = HERE / name
        folder.mkdir(exist_ok=False)
        case = next(c for c in registry["cases"] if c["id"] == case_id)
        provider = FIRST / name / "conversion-result.json"
        raw = json.loads(provider.read_text())
        page, = raw["pages"]
        table, = [t for t in page["assembled"]["elements"]
                  if t["label"] == "table" and t["cluster"]["id"] == cluster_id]
        source = next(s for s in registry["sources"] if s["id"] == case["source_ids"][0])
        pdf = ROOT / source["path"]
        assert sha(pdf) == raw["input"]["document_hash"] == source["sha256"]
        assert page["page_no"] == table["page_no"] == 8
        assert table["cluster"]["label"] == "table" and table["cluster"]["cells"]
        points = case["details"]["expected_datapoints"]
        assert len(points) == (84 if case_id == "G1-T02" else 6)
        box = table["cluster"]["bbox"]
        assert all(box["l"] <= p["source"]["bbox_top_left_points"][0] <
                   p["source"]["bbox_top_left_points"][2] <= box["r"] and
                   box["t"] <= p["source"]["bbox_top_left_points"][1] <
                   p["source"]["bbox_top_left_points"][3] <= box["b"] for p in points)
        save(folder / "capture-table.json", table)
        save(folder / "source.json", {"pdf": str(pdf), "sha256": source["sha256"],
             "page_no": 8, "size": page["size"], "case_id": case_id,
             "provider_result": str(provider), "provider_sha256": sha(provider),
             "full_original_table_cluster": True, "numeric_oracle_count": len(points)})
        for path in (pdf, provider, FIRST / name / "method.json"):
            originals[str(path)] = sha(path)
    assets = [p for p in ARTIFACTS.iterdir() if p.is_file()]
    assert {p.name for p in assets} == {"model.safetensors", "tokenizer_config.json",
          "special_tokens_map.json", "config.json", "tokenizer.json", "generation_config.json"}
    save(HERE / "method.json", {"scope": "New G1-T02 p8 six-panel table plus G1-T01 ordinary control",
         "entry": "TableStructureModelV2.predict_tables", "model": "docling-project/TableFormerV2",
         "revision_from_retained_download_record": REVISION,
         "identity_evidence": "docs/research/paper-pdf-table-v2-2026-10-11/download.json",
         "candidate": str(CANDIDATE), "runtime_difference": "Docling/IBM/parse stack also differs from first round; no single-model causal claim",
         "artifacts": {p.name: {"bytes": p.stat().st_size, "sha256": sha(p)} for p in assets},
         "threads": 1, "interop_threads": 1, "batch_size": 1, "device": "cpu", "offline": True,
         "max_new_structure_tokens": 512, "do_cell_matching": True,
         "timeout_seconds_per_child": TIMEOUT, "sampled_tree_rss_guard_bytes": LIMIT,
         "sample_seconds": .25, "originals": originals, "runner_sha256": sha(Path(__file__))})


def child(name):
    import torch
    from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat, LayoutPrediction, Page, Table
    from docling.datamodel.document import ConversionResult, InputDocument
    from docling.datamodel.pipeline_options import TableStructureV2Options
    from docling.models.stages.table_structure.table_structure_model_v2 import TableStructureModelV2

    folder = HERE / name
    started = time.monotonic()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    source = json.loads((folder / "source.json").read_text())
    assert sha(Path(source["pdf"])) == source["sha256"]
    capture = Table.model_validate(json.loads((folder / "capture-table.json").read_text()))
    in_doc = InputDocument(path_or_stream=Path(source["pdf"]), format=InputFormat.PDF,
                           backend=DoclingParseDocumentBackend)
    assert in_doc.valid
    page = Page(page_no=source["page_no"], size=source["size"])
    try:
        page._backend = in_doc._backend.load_page(page.page_no - 1)
        assert page._backend.is_valid() and page._backend.page_no == page.page_no
        size = page._backend.get_size()
        assert abs(size.width - page.size.width) < .01 and abs(size.height - page.size.height) < .01
        page.predictions.layout = LayoutPrediction(clusters=[capture.cluster])
        image = page.get_image(scale=2.0)
        image.save(folder / "page-144dpi.png")
        box = [round(v) * 2 for v in capture.cluster.bbox.as_tuple()]
        image.crop(box).save(folder / "table-crop-144dpi.png")
        model = TableStructureModelV2(enabled=True, artifacts_path=ARTIFACTS,
            options=TableStructureV2Options(do_cell_matching=True),
            accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=1))
        assert model.device == "cpu" and torch.get_num_threads() == 1
        save(folder / "settings.json", {"packages": {p: metadata.version(p) for p in
             ("docling", "docling-slim", "docling-core", "docling-ibm-models", "docling-parse", "torch")},
             "runtime_module": __import__("docling").__path__[0], "device": model.device,
             "dtype": str(next(model.model.parameters()).dtype), "threads": torch.get_num_threads(),
             "interop_threads": torch.get_num_interop_threads(), "stage_scale": model.scale,
             "crop_size": [box[2] - box[0], box[3] - box[1]],
             "captured_native_cells": len(capture.cluster.cells), "max_new_tokens": 512})
        original_generate, calls = model.model.generate, []

        def observed_generate(images, tokenizer, max_length=512, **kwargs):
            assert max_length == 512 and list(images.shape) == [1, 3, 448, 448]
            tick = time.monotonic()
            result = original_generate(images, tokenizer, max_length=max_length, **kwargs)
            ids = result["generated_ids"][0].tolist()
            eos = bool(ids) and ids[-1] == tokenizer.eos_token_id
            sequence = model._decode_otsl_sequence(result["generated_ids"][0])
            calls.append(time.monotonic() - tick)
            save(folder / "generation.json", {"ids": ids, "new_tokens": len(ids)-1,
                 "eos_reached": eos, "length_limit_reached_without_eos": len(ids)-1 >= 512 and not eos,
                 "last_structure_token": sequence[-1] if sequence else None, "otsl": sequence,
                 "seconds": calls[-1], "input_shape": list(images.shape),
                 "predicted_bboxes": result["predicted_bboxes"].tolist() if result["predicted_bboxes"] is not None else None})
            return result

        model.model.generate = observed_generate
        predictions = model.predict_tables(ConversionResult(input=in_doc, pages=[page]), [page])
        assert len(calls) == len(predictions) == 1
        table = predictions[0].table_map[capture.cluster.id]
        save(folder / "table.json", table.model_dump(mode="json"))
        save(folder / "result.json", {"status": "complete", "seconds": time.monotonic()-started,
             "generation_seconds": calls[0], "rows": table.num_rows, "cols": table.num_cols,
             "cells": len(table.table_cells), "nonempty_cells": sum(bool(c.text.strip()) for c in table.table_cells)})
    finally:
        if page._backend is not None:
            page._backend.unload()
        in_doc._backend.unload()


def run():
    import psutil
    assert not (HERE / "observations.json").exists()
    env = {**os.environ, "PYTHONPATH": str(CANDIDATE), "HF_HUB_OFFLINE": "1",
           "TRANSFORMERS_OFFLINE": "1", "HF_HOME": "/private/tmp/issue72-table-v2-20261011/hf",
           "PYTHONDONTWRITEBYTECODE": "1", "TOKENIZERS_PARALLELISM": "false",
           "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    observations = []
    try:
        for name, *_ in JOBS:
            folder = HERE / name
            assert psutil.virtual_memory().available >= 8 * 1024**3
            started, peak, samples, stopped = time.monotonic(), 0, 0, None
            with (folder / "child.log").open("wb") as log:
                process = subprocess.Popen(["rtk", "proxy", str(PYTHON), "-B", str(Path(__file__)), "child", name],
                    env=env, cwd=ROOT, stdout=log, stderr=log, start_new_session=True)
                try:
                    while process.poll() is None:
                        try:
                            p = psutil.Process(process.pid)
                            peak = max(peak, sum(c.memory_info().rss for c in [p, *p.children(recursive=True)]))
                            samples += 1
                        except psutil.NoSuchProcess:
                            pass
                        except (psutil.AccessDenied, OSError):
                            stopped = "process_monitor_unavailable"
                            break
                        if peak > LIMIT or time.monotonic()-started > TIMEOUT:
                            stopped = "sampled_memory_guard" if peak > LIMIT else "timeout"
                            break
                        time.sleep(.25)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            row = {"case": name, "pid": process.pid, "seconds": time.monotonic()-started,
                   "sampled_tree_peak_rss_bytes": peak, "samples": samples,
                   "exit_code": process.returncode, "stopped": stopped, "reaped": True}
            observations.append(row)
            save(HERE / "observations.json", observations)
            print(json.dumps(row), flush=True)
            if stopped or process.returncode:
                break
    finally:
        originals = json.loads((HERE / "method.json").read_text())["originals"]
        checks = {p: sha(Path(p)) == digest for p, digest in originals.items()}
        save(HERE / "originals-check.json", checks)
        assert all(checks.values())


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare()
    elif sys.argv[1] == "run":
        run()
    else:
        assert sys.argv[1] == "child"
        child(sys.argv[2])
