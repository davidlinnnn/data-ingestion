"""Source-only inventory; no evaluator files, network, credentials or inference."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESEARCH = ROOT / "docs/research"
READS = set()


def guard(event, args):
    if event in {"socket.connect", "socket.getaddrinfo"}:
        raise RuntimeError("network forbidden")
    if event == "open" and isinstance(args[0], (str, bytes)):
        name = os.fsdecode(args[0])
        if any(token in name for token in ("/A-review/", "/A-evaluator/", "/evaluator/", "source-contract", "source-coverage", "coverage.json", "holdout", "/.ssh/", "/.aws/")):
            raise RuntimeError("producer cannot read evaluator/holdout/credential files: " + name)
        mode = args[1] or ""
        if any(flag in mode for flag in "wax+") and not Path(name).resolve().is_relative_to(HERE):
            raise RuntimeError("producer write outside R1 directory")
        if Path(name).is_file() and Path(name).resolve().is_relative_to(ROOT):
            READS.add(str(Path(name).resolve().relative_to(ROOT)))


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    with Path(path).open("x") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2); stream.write("\n")


def deadline():
    end = datetime.fromisoformat(read(HERE / "registration.json")["deadline"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) >= end:
        raise RuntimeError("BUDGET_STOP: R1 deadline")


def inputs():
    A = RESEARCH / "pdf-core-stage1-followup-2026-10-17/A/inventory.json"
    C = RESEARCH / "pdf-core-eval-interfaces-2026-10-18/C/producer-inventory.json"
    pages = RESEARCH / "pdf-core-page-discovery-2026-10-17/registration.json"
    a, c, frames = read(A), read(C), read(pages)
    paths = {A, C, pages}
    for item in a["sources"]:
        paths |= {ROOT / item["document_path"], ROOT / item["pdf"]["path"]}
    for item in frames["jobs"]:
        paths.add(ROOT / item["image"])
    for item in c["ranges"]:
        paths |= {ROOT / item["baseline"], ROOT / item["source"]["path"]}
    for item in c["pictures"]:
        if item["status"] != "input_ready":
            raise ValueError("unprepared native picture remains required")
        paths.add(Path(item["crop"]))
    methods = [HERE / n for n in ("method.py", "producer.py", "test_method.py", "contract.md")]
    paths.update(methods)
    return a, c, frames, {str(p.resolve().relative_to(ROOT)): sha(p) for p in sorted(paths)}


def verify():
    frozen = read(HERE / "producer-inputs.json")
    for name, expected in frozen["files"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("changed producer input/method: " + name)


def produce():
    import method as m
    from docling_core.types.doc import DoclingDocument
    a, c, old_pages, _ = inputs()
    verify(); deadline()
    out = HERE / "production"
    out.mkdir()
    (out / "contexts").mkdir(); (out / "crops").mkdir()
    frame_index = {(str((ROOT / j["baseline"]).resolve()), j["physical_page"]): j for j in old_pages["jobs"]}
    all_groups, ranges = [], []
    sources = [("A", s["source"], ROOT / s["document_path"], s["pdf"], []) for s in a["sources"]]
    sources += [("C", r["range_id"], ROOT / r["baseline"], r["source"],
        [p for p in c["pictures"] if p["range_id"] == r["range_id"]]) for r in c["ranges"]]
    for component, name, path, source, pictures in sources:
        deadline(); baseline = read(path); doc = DoclingDocument.model_validate(baseline)
        revision = m.digest(baseline)
        groups = m.groups(baseline, component)
        ranges.append({"component": component, "source_name": name, "baseline": str(path.relative_to(ROOT)),
            "source": source, "pages": sorted(doc.pages), "groups": len(groups)})
        for pages in groups:
            views = []
            for page in pages:
                asset = f"contexts/{revision}-p{page}.png"
                destination = out / asset
                if not destination.exists():
                    old = frame_index.get((str(path.resolve()), page))
                    if old:
                        shutil.copyfile(ROOT / old["image"], destination)
                    else:
                        image = doc.pages[page].image
                        if image is None:
                            raise ValueError("missing retained full-page pixels")
                        image.pil_image.save(destination)
                from PIL import Image
                with Image.open(destination) as raster:
                    if raster.convert("RGB").getextrema() == ((0, 0), (0, 0), (0, 0)):
                        raise ValueError("black source view")
                    pixels = list(raster.size)
                size = doc.pages[page].size
                views.append({"page_no": page, "asset": asset, "sha256": sha(destination),
                    "pixels": pixels, "page_points": [size.width, size.height],
                    "pixel_scale_xy": [pixels[0]/size.width, pixels[1]/size.height],
                    "transform": "retained unrotated page view; page-envelope precision"})
            images = []
            for record in pictures:
                if set(p["page_no"] for p in record["provenance"]) <= set(pages):
                    item = {k: record[k] for k in ("owner_ref", "document_revision", "crop_sha256", "image_key", "mapping")}
                    item["asset"] = f"crops/{record['image_key']}.png"
                    if not (out / item["asset"]).exists():
                        shutil.copyfile(record["crop"], out / item["asset"])
                    if sha(out / item["asset"]) != item["crop_sha256"]:
                        raise ValueError("crop changed")
                    images.append(item)
            binding = m.bind(baseline, pages, views, images, component)
            identifier = m.digest([component, revision, pages])
            all_groups.append({"id": identifier, "source_name": name, "component": component,
                "baseline": str(path.relative_to(ROOT)), "binding": binding,
                "candidate_tasks": ["source_reconstruction"] if component == "A" else
                    ["description_with_context_OCR", "chart_assessment"],
                "remote_candidate_calls": 1 if component == "A" else 2,
                "local_crop_OCR_jobs": len(images) if component == "C" else 0,
                "context_pixels": sum(v["pixels"][0]*v["pixels"][1] for v in views)})
    result = {"method": "source-group-v1", "ranges": ranges, "groups": all_groups,
        "A_pages": sum(len(r["pages"]) for r in ranges if r["component"] == "A"),
        "C_pages": sum(len(r["pages"]) for r in ranges if r["component"] == "C"),
        "remote_candidate_calls": sum(g["remote_candidate_calls"] for g in all_groups),
        "local_crop_OCR_jobs": sum(g["local_crop_OCR_jobs"] for g in all_groups),
        "producer_oracle_reads": 0, "network_attempts": 0, "model_calls": 0,
        "input_and_task_inventory_only": True, "model_quality_verified": False}
    write(out / "inventory.json", result)
    write(out / "producer-read-log.json", {"repo_files_read": sorted(READS), "oracle_reads": 0})
    verify(); deadline()
    print(json.dumps({k:v for k,v in result.items() if k not in {"groups", "ranges"}}))


if __name__ == "__main__":
    os.environ.pop("OPENAI_API_KEY", None)
    sys.addaudithook(guard)
    deadline()
    if sys.argv[1:] == ["--freeze"]:
        _, _, _, files = inputs()
        write(HERE / "producer-inputs.json", {"files": files, "scope": "source-only producer", "model_calls": 0})
        print("Producer source/method inputs frozen; no evaluator data.")
    elif sys.argv[1:] == ["--produce"]:
        produce()
    elif sys.argv[1:] == ["--verify"]:
        verify(); print("Producer inputs/methods unchanged")
    else:
        raise SystemExit("Use --freeze, --produce or --verify; no inference mode")
