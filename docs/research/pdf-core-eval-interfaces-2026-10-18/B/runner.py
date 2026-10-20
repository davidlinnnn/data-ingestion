"""Seven-crop semantic comparison: thin bridge over the pinned bounded HTTP runner."""
import argparse
import base64
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import httpx
from PIL import Image
import psutil
from docling_core.types.doc import DoclingDocument
import protocol as p

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RESEARCH = HERE.parents[1]
OLD = RESEARCH / "pdf-core-stage1-followup-2026-10-17/B"
INVENTORY = RESEARCH / "pdf-core-bc-closure-2026-10-17/B/proposed-input-inventory.json"
RUNTIME = HERE.parent / "runtime-lock.json"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def body(job):
    if sha(job["image"]) != job["image_sha256"]:
        raise ValueError("source image changed")
    value = deepcopy(job["body_without_image"])
    value["messages"][0]["content"][1]["image_url"]["url"] = (
        "data:image/png;base64," + base64.b64encode(Path(job["image"]).read_bytes()).decode())
    raw = encoded(value)
    if len(raw) > 8 * 2**20 or job.get("http_body_sha256", sha256(raw).hexdigest()) != sha256(raw).hexdigest():
        raise ValueError("request bytes/hash outside frozen envelope")
    return raw


def legacy(reg=None):
    # Isolate old module names; reuse its tested transport/watchdog/usage and atomic assembly.
    saved = {name: sys.modules.get(name) for name in ("protocol", "controls")}
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module
    try:
        sys.modules["protocol"] = load("semantic_transport_old_protocol", OLD / "protocol.py")
        sys.modules["controls"] = load("semantic_transport_old_controls", OLD / "controls.py")
        transport = load("semantic_transport_old_runner", OLD / "runner.py")
    finally:
        for name, module in saved.items():
            if module is None: sys.modules.pop(name, None)
            else: sys.modules[name] = module
    transport.p = p; transport.body = body
    if reg is not None:
        assert (transport.ENDPOINT, transport.REQUEST_SECONDS, transport.LIVE_SECONDS) == (
            reg["endpoint"], reg["request_seconds"], reg["live_seconds"]), "transport constants differ"
    transport.json = SimpleNamespace(loads=p.loads, dumps=json.dumps)
    def own_guard(started):
        sample = dict(seconds=time.monotonic()-started, rss=psutil.Process().memory_info().rss,
            available=psutil.virtual_memory().available, scope="current process; runner spawns no children")
        if sample["seconds"] >= 1800 or sample["rss"] >= 12*2**30 or sample["available"] < 8*2**30:
            raise transport.BudgetStop("time_or_memory_guard")
        return sample
    transport.resource_guard = own_guard
    original_assemble = transport.assemble
    def source_bound_assemble(registration, records, directory):
        if any(sha(page["baseline"]) != page["baseline_sha256"] for page in registration["pages"]):
            raise transport.BudgetStop("baseline_changed_before_assembly")
        return original_assemble(registration, records, directory)
    transport.assemble = source_bound_assemble
    original_write = transport.write
    def count_write(path, value):
        if Path(path).name == "attempt.json" and "calls_max" in value:
            value = {**value, "calls_max": 7}
        if Path(path).name == "execution.json":
            value = {k: v for k, v in value.items() if k != "all_six_attempted"}
            value["all_registered_jobs_attempted"] = value["ledger"]["calls"] == 7
        original_write(path, value)
    transport.write = count_write
    return transport


def plan():
    prompt = (HERE / "prompt.txt").read_text()
    schema = p.Response.model_json_schema()
    lock = json.loads(RUNTIME.read_text())
    assert sys.version.split()[0] == lock["python"]
    assert all(version(item["name"]) == item["version"] for item in lock["packages"])
    assert all(sha(path) == item["sha256"] for path, item in lock["selected_runtime_source_files"].items())
    old = json.loads((OLD / "live-registration.json").read_text())
    jobs = deepcopy(json.loads(INVENTORY.read_text())["jobs"])
    pages = {}
    for job in jobs:
        for key in ("image", "baseline", "source_path"):
            path = Path(job[key]); job[key] = str(path if path.is_absolute() else ROOT / path)
            assert sha(job[key]) == job[key+"_sha256" if key != "source_path" else "source_sha256"]
        with Image.open(job["image"]) as image: assert list(image.size) == job["image_size"]
        text = prompt + "\nSchema:\n" + encoded(schema).decode() + "\nTarget:\n" + encoded(
            {"target_key": job["target_key"], "bbox": [0, 0, *job["image_size"]]}).decode()
        job.update(input_token_reservation=len(text.encode()) + 8192 + 1024, completion_cap=32768,
            body_without_image={"model": old["model"], "store": False, "reasoning_effort": "low",
                "max_completion_tokens": 32768, "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": [{"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": "REGISTERED_IMAGE", "detail": "high"}}]}]})
        job["http_body_sha256"] = sha256(body(job)).hexdigest()
        page = pages.setdefault(job["page_name"], {"name": job["page_name"], "page_no": job["physical_page"],
            "baseline": job["baseline"], "baseline_sha256": job["baseline_sha256"], "target_keys": []})
        assert page["baseline"] == job["baseline"]
        page["target_keys"].append(job["target_key"])
    assert len(jobs) == 7 and len({j["name"] for j in jobs}) == 7
    for page in pages.values():
        baseline = DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
        assert set(p.adapter.inventory(baseline, page["page_no"])) == set(page["target_keys"])
    files = [HERE / "runner.py", HERE / "protocol.py", HERE / "prompt.txt", HERE / "test_interface.py",
        INVENTORY, RUNTIME, OLD / "runner.py", OLD / "protocol.py", OLD / "controls.py",
        RESEARCH / "pdf-core-bc-closure-2026-10-17/B/method.py",
        RESEARCH / "pdf-core-direct-cell-2026-10-17/adapter.py",
        RESEARCH / "pdf-core-caption-ownership-2026-10-17/policy.py",
        RESEARCH / "pdf-core-table-delivery-2026-10-17/mapper.py"]
    return dict(jobs=jobs, pages=list(pages.values()), endpoint=old["endpoint"], model=old["model"],
        calls_max=7, concurrency=1, retries=0, max_completion_tokens=32768,
        total_completion_budget=7*32768, total_input_budget=sum(j["input_token_reservation"] for j in jobs),
        content_bytes=262144, transport_bytes=2097152, request_seconds=180, live_seconds=1800,
        request_bytes=8*2**20, memory_rss_bytes=12*2**30, min_available_bytes=8*2**30,
        prelaunch_available_bytes=10*2**30, prompt_sha256=sha(HERE / "prompt.txt"),
        memory_guard_scope="current process only; synchronous API runner spawns no subprocesses",
        response_schema_sha256=sha256(encoded(schema)).hexdigest(), method_files={str(f): sha(f) for f in files},
        runtime={name: version(name) for name in ("docling-slim", "docling-core", "docling-parse", "pydantic", "httpx")},
        input_estimator="prompt/schema UTF8 bytes + 8192 image + 1024 framing reserve; not an exact tokenizer guarantee; actual overrun stops",
        denominators={"original_numeric": 470, "original_comparisons": 23, "collateral": 2,
            "table_math_groups_separate": 4, "T03_crosspage_separate_numeric": 264, "T03_comparisons": 7},
        semantic_acceptance=False, current_round_remote_calls=0,
        provider_identity="temporary OpenAI comparator; service alias is not immutable model weights or Qwen3 evidence")


def verify():
    reg = p.loads((HERE / "candidate.json").read_text())
    assert reg == plan(), "frozen configuration or source changed"
    for job in reg["jobs"]:
        assert (HERE / "requests" / (job["name"] + ".json")).read_bytes() == body(job)
    assert p.loads((HERE / "schema.json").read_text()) == p.Response.model_json_schema()
    return reg


def main():
    args = argparse.ArgumentParser()
    modes = args.add_mutually_exclusive_group(required=True)
    for flag, value in (("--prepare", "prepare"), ("--dry-run", "dry-run"), ("--live", "live")):
        modes.add_argument(flag, dest="mode", action="store_const", const=value)
    args.add_argument("--credential-env", default="OPENAI_API_KEY")
    options = args.parse_args()
    if options.mode == "prepare":
        assert datetime.now(timezone.utc) < datetime.fromisoformat(p.loads((HERE / "registration.json").read_text())["deadline"])
        reg = plan(); (HERE / "requests").mkdir(exist_ok=False)
        for job in reg["jobs"]: (HERE / "requests" / (job["name"] + ".json")).write_bytes(body(job))
        write(HERE / "schema.json", p.Response.model_json_schema()); write(HERE / "candidate.json", reg)
    else:
        reg = verify()
    if options.mode == "live":
        if psutil.virtual_memory().available < reg["prelaunch_available_bytes"]:
            raise SystemExit("start requires 10 GiB available")
        transport = legacy(reg)
        with httpx.Client(timeout=httpx.Timeout(reg["request_seconds"], connect=20), follow_redirects=False, trust_env=False) as client:
            result = transport.execute(reg, client, os.environ.get(options.credential_env, ""), HERE / "live")
        print(json.dumps({"ledger": result["ledger"], "stopped": result["stopped"]}))
    else:
        sample = legacy(reg).resource_guard(time.monotonic())
        print(json.dumps({"mode": options.mode, "request_count": len(reg["jobs"]), "remote_calls": 0,
            "total_input_reservation": reg["total_input_budget"], "completion_cap_total": reg["total_completion_budget"],
            "resource_sample": sample, "credential_status": "not read", "semantic_acceptance": False}))


if __name__ == "__main__": main()
