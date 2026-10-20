"""Generic public-native picture inventory and bounded component requests; no oracle."""
import copy
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Literal

from docling_core.types.doc import DoclingDocument, ImageRef
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
METHOD = "native-picture-components-v1"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seam = load("native_image_seam", REPO / "docs/research/pdf-core-stage1-followup-2026-10-17/C/controls.py")
saved = load("saved_image_schema", REPO / "docs/research/pdf-core-stage1-2026-10-17/C/controls.py")


class Entity(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    id: str
    label: str
    role: str


class Relation(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    from_: str = Field(alias="from")
    to: str
    meaning: str
    condition: str | None


class Description(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    image_kind: str
    description: str = Field(min_length=1)
    visible_text: list[str]
    components: list[Entity]
    relations: list[Relation]
    ordered_steps: list[str]
    uncertainties: list[str]


class Point(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    series: str | None
    category: str | None
    x: int | float | str | None
    value: int | float | str | None
    value_status: Literal["printed", "estimated", "unreadable"]

    @model_validator(mode="after")
    def missing_is_explicit(self):
        if (self.value is None) != (self.value_status == "unreadable"):
            raise ValueError("null value must explicitly be unreadable")
        return self


class Chart(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    chart_type: Literal["bar chart", "line chart", "pie chart", "mixed bar/line chart", "not_chart", "unsupported_chart", "unknown"]
    unit: str | None
    data: list[Point]
    uncertainties: list[str]

    @model_validator(mode="after")
    def type_and_data(self):
        if self.chart_type in {"not_chart", "unsupported_chart", "unknown"}:
            if self.data:
                raise ValueError("non-numeric assessment cannot invent values")
        elif not self.data:
            raise ValueError("supported chart cannot silently deliver no observations")
        return self


def materialize(job):
    if sha(job["input"]) != job["binding"]["crop_sha256"]:
        raise ValueError("actual image bytes changed")
    if digest([job["binding"], job["body_without_image"]]) != job["template_sha256"]:
        raise ValueError("request template changed")
    body = copy.deepcopy(job["body_without_image"])
    body["messages"][1]["content"][1]["image_url"]["url"] = "data:image/png;base64," + base64.b64encode(Path(job["input"]).read_bytes()).decode()
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()


def validate_response(job, envelope):
    """Bind any actual provider result to this exact request before parsing content."""
    actual_request_sha = hashlib.sha256(materialize(job)).hexdigest()
    if actual_request_sha != job["request_sha256"]:
        raise ValueError("materialized request hash mismatch")
    if envelope["input"] != job["binding"] or envelope["request_sha256"] != actual_request_sha:
        raise ValueError("foreign/stale/crop/request binding")
    if envelope.get("model") != job["body_without_image"]["model"]:
        raise ValueError("provider model differs from candidate label")
    usage = envelope.get("usage", {})
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ["prompt_tokens", "completion_tokens", "total_tokens"]):
        raise ValueError("invalid usage")
    if usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
        raise ValueError("incoherent usage")
    if usage["prompt_tokens"] > job["input_tokens_reserve"] or usage["completion_tokens"] > job["output_tokens_cap"]:
        raise ValueError("per-job token budget overrun; stop later jobs")
    if len(json.dumps(envelope).encode()) > job["transport_bytes_max"]:
        raise ValueError("transport budget")
    if envelope.get("finish_reason") != "stop" or envelope.get("refusal"):
        raise ValueError("truncated or refused result")
    payload = envelope["payload"]
    if len(json.dumps(payload).encode()) > job["content_bytes_max"]:
        raise ValueError("content byte budget")
    if job["task"] == "description":
        parsed = Description.model_validate(payload)
        if not parsed.description.strip():
            raise ValueError("empty description is not delivered")
    elif job["task"] == "chart_assessment":
        Chart.model_validate(payload)
    else:
        raise ValueError("unsupported remote task")
    return payload


def self_check(jobs):
    if not jobs:
        raise ValueError("no actual native requests to validate")
    job = next(j for j in jobs if j["task"] == "description")
    # Schema/binding control only; this text is never saved as a source result.
    response = {"input": job["binding"], "request_sha256": job["request_sha256"],
                "model": job["body_without_image"]["model"], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "finish_reason": "stop", "payload": {"image_kind": "control", "description": "schema control",
                "visible_text": [], "components": [], "relations": [], "ordered_steps": [], "uncertainties": []}}
    validate_response(job, response)
    rejected = []
    for name, mutate in [
        ("foreign_crop", lambda r: r["input"].update(crop_sha256="foreign")),
        ("foreign_revision", lambda r: r["input"].update(document_revision="stale")),
        ("wrong_request", lambda r: r.update(request_sha256="other")),
        ("truncated", lambda r: r.update(finish_reason="length")),
        ("empty", lambda r: r["payload"].update(description="")),
        ("null_component", lambda r: r["payload"].update(components=[None])),
        ("bool_relation", lambda r: r["payload"].update(relations=[False])),
        ("numeric_visible_text", lambda r: r["payload"].update(visible_text=[123])),
        ("wrong_model", lambda r: r.update(model="another")),
        ("boolean_usage", lambda r: r["usage"].update(prompt_tokens=True)),
        ("token_overrun", lambda r: r.update(usage={"prompt_tokens": 1, "completion_tokens": 6145, "total_tokens": 6146})),
    ]:
        bad = copy.deepcopy(response)
        mutate(bad)
        try:
            validate_response(job, bad)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(name)
    try:
        saved.Work.model_validate({"state": "failed", "texts": ["delivered"], "diagnostic": "failed"})
    except ValueError:
        rejected.append("failed_with_delivered_OCR")
    else:
        raise AssertionError("failed OCR accepted as delivered")
    chart_job = next(j for j in jobs if j["task"] == "chart_assessment")
    chart = {"chart_type": "line chart", "unit": None, "data": [{"series": None, "category": None, "x": 1, "value": None, "value_status": "unreadable"}], "uncertainties": ["source unreadable"]}
    Chart.model_validate(chart)
    for name, payload in [("unknown_chart_kind", {**chart, "chart_type": "unsupported_made_up_kind", "data": []}),
                          ("empty_supported_chart", {**chart, "data": []}),
                          ("null_estimated_value", {**chart, "data": [{**chart["data"][0], "value_status": "estimated"}]})]:
        try:
            Chart.model_validate(payload)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(name)
    return {"positive_schema_control": True, "negative_controls_rejected": rejected,
            "model_accuracy_evidence": False}


def prepare():
    start = time.monotonic()
    (HERE / "crops").mkdir(exist_ok=False)
    ranges, records, errors = [], [], []
    for source in read(HERE / "scope.json")["ranges"]:
        path = Path(source["baseline"])
        if not path.exists():
            errors.append({"range_id": source["range_id"], "reason": "native baseline unavailable"})
            continue
        if sha(source["source"]["path"]) != source["source"]["sha256"]:
            raise ValueError("source changed")
        if source.get("baseline_sha256") and sha(path) != source["baseline_sha256"]:
            raise ValueError("cached baseline changed")
        doc = DoclingDocument.load_from_json(path)
        baseline = doc.export_to_dict()
        revision = digest(baseline)
        page_ids = sorted(doc.pages)
        assert page_ids == list(range(source["first"], source["last"]+1))
        ranges.append({**source, "baseline_sha256": sha(path), "document_revision": revision,
                       "pages": page_ids, "native_picture_count": len(doc.pictures)})
        for picture in doc.pictures:
            row = {"range_id": source["range_id"], "source_id": source["source_id"],
                   "source": source["source"], "document_revision": revision,
                   "baseline": str(path), "baseline_sha256": sha(path), "owner_ref": picture.self_ref,
                   "provenance": [p.model_dump(mode="json") for p in picture.prov],
                   "caption_refs": [c.cref for c in picture.captions],
                   "native_children": [c.cref for c in picture.children],
                   "classification": "unknown", "required_work": saved.required_work("unknown"),
                   "states": {"ocr": "unattempted", "description": "unattempted", "chart_assessment": "unattempted"}}
            try:
                if len(picture.prov) != 1:
                    raise ValueError("multi-provenance picture not supported by retained seam")
                mapping = seam.native_mapping(doc, picture)
                image = picture.get_image(doc)
                temp = HERE / "crops" / "native.png"
                image.save(temp)
                crop_hash = sha(temp)
                key = digest([revision, picture.self_ref, crop_hash])
                dest = HERE / "crops" / (key + ".png")
                temp.rename(dest)
                row.update({"image_key": key, "crop": str(dest), "crop_sha256": crop_hash,
                            "pixels": list(image.size), "mapping": mapping, "status": "input_ready"})
            except (ValueError, AttributeError, IndexError) as error:
                row.update(status="input_unresolved", diagnostic=str(error))
            records.append(row)
    # Freeze native discovery before a separate evaluator process reads source locators.
    inventory = {"method": METHOD, "oracle_reads": 0, "ranges": ranges, "pictures": records,
                 "range_errors": errors, "producer_seconds": time.monotonic()-start}
    write(HERE / "producer-inventory.json", inventory)
    requests, ocr = [], []
    history = REPO / "docs/research/pdf-core-g2-images-2026-10-14/api"
    for row in records:
        if row["status"] != "input_ready":
            continue
        binding = {k: row[k] for k in ["document_revision", "owner_ref", "image_key", "crop_sha256"]}
        ocr.append({"task": "ocr", "binding": binding, "input": row["crop"],
                    "component": "RapidOCR existing pinned det/rec/cls options", "max_seconds": 30,
                    "output_state": "unattempted", "failure_is_not_acceptance": True})
        for task, example in [("description", "g1-s05"), ("chart_assessment", "g1-c03")]:
            body = copy.deepcopy(read(history / example / "request-description.json")["body_without_inline_image"])
            if task == "chart_assessment":
                body["messages"][1]["content"][0]["text"] = (
                    "Use chart_type exactly one of bar chart, line chart, pie chart, mixed bar/line chart, not_chart, unsupported_chart, unknown. "
                    "For a non-chart use not_chart; for other chart families use unsupported_chart; for uncertainty use unknown; these three have data=[]. "
                    "Unreadable source observations remain data points with value=null and value_status=unreadable; never omit them. "
                    "Always supply uncertainties as a list of strings. Never infer a chart from labels alone. "
                    + body["messages"][1]["content"][0]["text"])
            body["messages"][1]["content"][1]["image_url"]["url"] = "REGISTERED_INPUT_BYTES"
            # Token reserve is deliberately conservative and not provider billing prediction.
            reserve = 8192 + 2*((len(json.dumps(body).encode())+2)//3)
            requests.append({"job_id": row["image_key"]+":"+task, "task": task,
                             "binding": binding, "input": row["crop"], "pixels": row["pixels"],
                             "body_without_image": body, "template_sha256": digest([binding,body]),
                             "input_tokens_reserve": reserve, "output_tokens_cap": 6144,
                             "max_seconds": 180, "content_bytes_max": 500000,
                             "transport_bytes_max": 2000000, "output_state": "unattempted"})
            requests[-1]["request_sha256"] = hashlib.sha256(materialize(requests[-1])).hexdigest()
    write(HERE / "requests.json", {"method": METHOD, "jobs": requests, "local_OCR_jobs": ocr,
          "calls_candidate": len(requests), "retry": 0, "concurrency": 1,
          "input_tokens_reserve_total": sum(r["input_tokens_reserve"] for r in requests),
          "completion_tokens_cap_total": len(requests)*6144,
          "remote_live_seconds_cap": min(10800, len(requests)*180),
          "rss_max_bytes": 12*2**30, "minimum_available_bytes": 8*2**30,
          "transport_bytes_per_request": 2000000,
          "input_policy": "all native pictures; no area/classification/known-source skip",
          "remote_execution_ready": False, "reason": "await independent coverage and source contract gates; no API client run"})
    write(HERE / "interface-selfcheck.json", self_check(requests))
    print(json.dumps({"ranges": len(ranges), "pages": sum(len(r["pages"]) for r in ranges),
                      "native_pictures": len(records), "inputs_ready": len(ocr),
                      "remote_candidate_requests": len(requests), "oracle_reads": 0,
                      "range_errors": errors}))


def finalize_requests():
    manifest = read(HERE / "requests.json")
    chart_base = read(REPO / "docs/research/pdf-core-g2-images-2026-10-14/api/g1-c03/request-description.json")["body_without_inline_image"]["messages"][1]["content"][0]["text"]
    for job in manifest["jobs"]:
        body = job["body_without_image"]
        if job["task"] == "chart_assessment":
            body["messages"][1]["content"][0]["text"] = (
                "Use chart_type exactly one of bar chart, line chart, pie chart, mixed bar/line chart, not_chart, unsupported_chart, unknown. "
                "For non-charts use not_chart; for other chart families use unsupported_chart; for uncertainty use unknown. These three have data=[]. "
                "Unreadable observations remain data points with value=null and value_status=unreadable, with uncertainties; never omit them. "
                + chart_base)
        schema = (Description if job["task"] == "description" else Chart).model_json_schema()
        body["messages"][1]["content"][0]["text"] += "\nRequired known-field schema (unknown provider fields preserved separately):\n"+json.dumps(schema, separators=(",", ":"))
        job["template_sha256"] = digest([job["binding"],body])
        job["input_tokens_reserve"] = 8192 + 2*((len(json.dumps(body).encode())+2)//3)
        job["request_sha256"] = hashlib.sha256(materialize(job)).hexdigest()
    manifest.update({"interface_version": 2, "candidate_calls_upper_bound": len(manifest["jobs"]),
        "input_tokens_reserve_total": sum(j["input_tokens_reserve"] for j in manifest["jobs"]),
        "wire_materialization": "actual UTF-8 JSON HTTP body with registered PNG data URL; no authorization header stored",
        "token_reserve_limit": "heuristic reserve, not provider/tokenizer guarantee; usage overrun stops later jobs; no live runner implemented",
        "remote_execution_ready": False, "live_run_budget_enforcement_ready": False})
    write(HERE / "requests.json", manifest)
    write(HERE / "interface-selfcheck.json", self_check(manifest["jobs"]))
    print(json.dumps({"requests_materialized_and_hashed": len(manifest["jobs"]), "source_crops_changed": False,
                      "negative_controls": len(read(HERE / "interface-selfcheck.json")["negative_controls_rejected"]),
                      "remote_execution_ready": False}))


def bundle_inputs():
    inventory = read(HERE / "producer-inventory.json")
    results = []
    for source in inventory["ranges"]:
        doc = DoclingDocument.load_from_json(source["baseline"])
        baseline = doc.export_to_dict()
        records = [p for p in inventory["pictures"] if p["range_id"] == source["range_id"]]
        dst = HERE / "bundles" / source["range_id"]
        dst.mkdir(parents=True, exist_ok=False)
        for row in records:
            picture = next(p for p in doc.pictures if p.self_ref == row["owner_ref"])
            if row["status"] != "input_ready":
                continue
            picture.image = ImageRef(mimetype="image/png", dpi=picture.image.dpi,
                                     size=picture.image.size, uri=Path("../../crops")/(row["image_key"]+".png"))
        write(dst / "document.json", doc.export_to_dict())
        write(dst / "supplement.json", {"method": METHOD, "document_revision": source["document_revision"],
                                        "images": records, "provider_results": [], "acceptance": "unattempted_not_accepted"})
        (dst / "document.md").write_text(seam.markdown(doc))
        restored = DoclingDocument.load_from_json(dst / "document.json")
        compare = restored.export_to_dict()
        for row in records:
            picture = next(p for p in restored.pictures if p.self_ref == row["owner_ref"])
            assert (dst / Path(str(picture.image.uri))).resolve() == Path(row["crop"]).resolve()
            assert sha(row["crop"]) == row["crop_sha256"]
            index = int(row["owner_ref"].rsplit("/", 1)[1])
            compare["pictures"][index]["image"] = baseline["pictures"][index]["image"]
        assert compare == baseline, "source graph/caption/text changed"
        assert seam.markdown(restored).encode() == (dst / "document.md").read_bytes()
        results.append({"range_id": source["range_id"], "pictures": len(records), "baseline_graph_preserved_except_resource_URI": True,
                        "supplement_model_results": 0, "states": "unattempted", "source_MD_generated_results_inserted": False})
    write(HERE / "bundle-validation.json", {"ranges": results, "pass": True,
          "limit": "actual native input/key/supplement/source-Markdown seam, not inference content or worker recovery"})
    print(json.dumps({"native_bundles": len(results), "pass": True, "model_results": 0}))


if __name__ == "__main__":
    if sys.argv[1:] == ["--finalize-requests"]:
        finalize_requests()
    elif sys.argv[1:] == ["--bundle-inputs"]:
        bundle_inputs()
    else:
        prepare()
