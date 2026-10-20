"""Six frozen DEV crops with compact tables, bounded usage and atomic page mapping."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from importlib.metadata import version
import os
from pathlib import Path
import signal
import sys
import time

import httpx
from PIL import Image
import psutil
from docling_core.types.doc import DoclingDocument
import protocol as p
from controls import HERE, RESEARCH, sha

OLD = RESEARCH / "pdf-core-stage1-2026-10-17/B"
ENDPOINT = "https://api.openai.com/v1/chat/completions"
COMPLETION_CAP, CONTENT_LIMIT, TRANSPORT_LIMIT = 32768, 65536, 524288
REQUEST_SECONDS, LIVE_SECONDS = 180, 1800
MODEL = "gpt-6-luna"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def write(path, value):
    with Path(path).open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def body(job):
    result = deepcopy(job["body_without_image"])
    result["messages"][0]["content"][1]["image_url"]["url"] = (
        "data:image/png;base64," + base64.b64encode(Path(job["image"]).read_bytes()).decode())
    return encoded(result)


def preflight():
    samples = {}
    for rows, panels in ((64, 1), (32, 2)):
        grid = [["001.20" for _ in range(16)] for _ in range(rows)]
        sections = (1, rows // 2)
        spans, groups = [], []
        roles = [dict(row=0, col=c, kind="column") for c in range(16)]
        for i, r in enumerate(sections):
            grid[r] = ["Group"] + [None] * 15
            spans.append(dict(row=r, col=0, rows=1, cols=16))
            roles.append(dict(row=r, col=0, kind="section"))
            groups.append(dict(start=r, end=sections[i+1] if i+1 < len(sections) else rows,
                               label_row=r, label_col=0))
        data = dict(grid=grid, spans=spans, roles=roles, row_groups=groups)
        payload = dict(targets=[dict(target_key="synthetic", caption="", conditions=[], diagnostics=[],
            panels=[dict(panel_label=str(i), title="", data=deepcopy(data)) for i in range(panels)])])
        p.parse(payload, ["synthetic"])
        compact = encoded(payload)
        pretty = json.dumps(payload, ensure_ascii=False, indent=2).encode()
        assert max(len(compact), len(pretty)) <= CONTENT_LIMIT
        assert len(compact) + 8192 <= COMPLETION_CAP
        samples[f"{rows}x16-panels{panels}"] = dict(compact_bytes=len(compact), pretty_bytes=len(pretty))
    assert 6 * CONTENT_LIMIT + 65536 <= TRANSPORT_LIMIT
    return dict(samples=samples, source_independent=True, content_bytes=CONTENT_LIMIT,
        transport_bytes=TRANSPORT_LIMIT, completion_cap=COMPLETION_CAP,
        scope="Finite synthetic stress examples and research limits; not a maximum for all schema-valid tables.",
        token_fit="Compact UTF8 byte proxy plus 8192 reasoning reserve; not an exact provider tokenizer count. Pretty JSON fits parser; token-cap truncation remains a recorded failure.")


def freeze():
    gate = json.loads((HERE / "results.json").read_text())
    mocks = json.loads((HERE / "source-mock-results.json").read_text())
    tests = json.loads((HERE / "runner-test-results.json").read_text())
    if (not all(gate["checks"].values()) or mocks["status"] != "pass"
        or not tests["passed"] or tests["tests"] != 22 or tests["failures"] or tests["errors"]):
        raise ValueError("offline controls must pass")
    original = json.loads((OLD / "next-stage-jobs.json").read_text())
    protocol = json.loads((OLD / "prompt-and-schema.json").read_text())
    prompt = protocol["prompt"] + " Return compact JSON. A section label's rowspan must fit inside its declared row_group."
    schema = p.Response.model_json_schema()
    jobs = deepcopy(original["jobs"])
    for page in original["pages"]:
        for key in ("source_path", "baseline", "image", "options"):
            digest_key = "source_sha256" if key == "source_path" else key + "_sha256"
            assert sha(page[key]) == page[digest_key]
        baseline = DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
        assert list(p.adapter.inventory(baseline, page["page_no"])) == page["target_keys"]
    for job in jobs:
        assert sha(job["image"]) == job["image_sha256"]
        with Image.open(job["image"]) as image:
            assert list(image.size) == job["image_size"]
        text = prompt + "\nSchema:\n" + encoded(schema).decode() + "\nTarget:\n" + encoded(dict(
            target_key=job["target_key"], bbox=[0, 0, *job["image_size"]])).decode()
        job.update(input_token_reservation=len(text.encode()) + 8192 + 1024,
            completion_cap=COMPLETION_CAP, status="frozen; not attempted",
            body_without_image=dict(model=MODEL, store=False, reasoning_effort="low",
                max_completion_tokens=COMPLETION_CAP, response_format=dict(type="json_object"),
                messages=[dict(role="user", content=[dict(type="text", text=text),
                    dict(type="image_url", image_url=dict(url="REGISTERED_IMAGE", detail="high"))])]))
        job["http_body_sha256"] = sha256(body(job)).hexdigest()
    assert len(jobs) == 6
    methods = json.loads((HERE / "registration.json").read_text())["method_hashes"]
    sdk = json.loads((OLD / "registration.json").read_text())["public_sdk_source_hashes"]
    for path, expected in sdk.items():
        assert sha(path) == expected
    methods.update(sdk)
    methods.update({str(path): sha(path) for path in (HERE / "runner.py", HERE / "test_runner.py",
        HERE / "protocol.py", HERE / "mock_sources.py", HERE / "next-stage-jobs.json",
        HERE / "results.json", HERE / "source-mock-results.json", HERE / "runner-test-results.json",
        OLD / "next-stage-jobs.json", OLD / "prompt-and-schema.json")})
    reg = dict(jobs=jobs, pages=original["pages"], endpoint=ENDPOINT, model=MODEL,
        calls_max=6, concurrency=1, retries=0, max_completion_tokens=COMPLETION_CAP,
        total_completion_budget=6*COMPLETION_CAP,
        total_input_budget=sum(j["input_token_reservation"] for j in jobs),
        input_estimator="prompt/schema UTF8 bytes + 8192 image estimate + 1024 framing. Research reservation, not a provider guarantee; actual overrun stops subsequent calls.",
        content_bytes=CONTENT_LIMIT, transport_bytes=TRANSPORT_LIMIT, request_seconds=REQUEST_SECONDS,
        live_seconds=LIVE_SECONDS, method_files=methods, denominators=original["denominators"],
        preflight=preflight(), offline_gate="pass", ready_for_remote=True,
        provider_capabilities="Official docs confirm image input, Chat Completions, low reasoning and 128000 max output; account access and exact Luna image tokenizer remain unverified.",
        provider_sources=["https://developers.openai.com/api/docs/models/gpt-6-luna",
            "https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create",
            "https://developers.openai.com/api/docs/guides/images-vision"],
        runtime={name: version(name) for name in ("docling-slim", "docling-core", "docling-parse", "pydantic", "httpx")},
        frozen_at=datetime.now(timezone.utc).isoformat(), new_model_calls=0,
        input_rule=original["input_rule"], mapping_rule=original["mapping_rule"])
    write(HERE / "live-registration.json", reg)
    return reg


def verify():
    reg = json.loads((HERE / "live-registration.json").read_text())
    assert all(version(name) == expected for name, expected in reg["runtime"].items()), "runtime changed"
    for path, expected in reg["method_files"].items():
        assert sha(path) == expected, "frozen method changed"
    for page in reg["pages"]:
        for key in ("source_path", "baseline", "image", "options"):
            assert sha(page[key]) == page["source_sha256" if key == "source_path" else key+"_sha256"]
    for job in reg["jobs"]:
        assert sha(job["image"]) == job["image_sha256"]
        assert sha256(body(job)).hexdigest() == job["http_body_sha256"]
    assert len(reg["jobs"]) == reg["calls_max"] == 6
    return reg


class BudgetStop(Exception):
    pass


def reserve(reg, ledger, job):
    if (ledger["calls"] >= reg["calls_max"]
        or ledger["input"] + job["input_token_reservation"] > reg["total_input_budget"]
        or ledger["completion"] + job["completion_cap"] > reg["total_completion_budget"]):
        raise BudgetStop("pre_request_budget_stop")


def valid_usage(usage):
    return isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
                                           for k in ("prompt_tokens", "completion_tokens"))


def charge(reg, ledger, job, usage):
    if not valid_usage(usage):
        raise BudgetStop("usage_unavailable_or_invalid")
    ledger["input"] += usage["prompt_tokens"]
    ledger["completion"] += usage["completion_tokens"]  # Includes reasoning; do not add it again.
    if (usage["prompt_tokens"] > job["input_token_reservation"]
        or usage["completion_tokens"] > job["completion_cap"]
        or ledger["input"] > reg["total_input_budget"]
        or ledger["completion"] > reg["total_completion_budget"]):
        raise BudgetStop("actual_usage_overrun")


def assemble(reg, records, directory):
    accepted = {r["name"] for r in records if r.get("result") == "valid_target"}
    results = []
    for page in reg["pages"]:
        page_started = time.monotonic()
        jobs = [j for j in reg["jobs"] if j["page_name"] == page["name"]]
        result = dict(name=page["name"], status="unaccepted: missing or failed target", quality_evaluated=False)
        if all(j["name"] in accepted for j in jobs):
            payload = dict(targets=[json.loads((directory / j["name"] / "output.json").read_text())["targets"][0] for j in jobs])
            try:
                baseline = DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
                mapping_started = time.monotonic()
                doc, bindings = p.map_response(baseline, payload, page["page_no"], page["target_keys"])
                result["mapping_seconds"] = time.monotonic()-mapping_started
                export_started = time.monotonic()
                markdown = p.adapter.export_markdown(doc, bindings)
                reloaded = DoclingDocument.model_validate_json(doc.model_dump_json())
                assert p.adapter.export_markdown(reloaded, json.loads(json.dumps(bindings))) == markdown
                dest = directory / page["name"]
                dest.mkdir(exist_ok=True)
                write(dest / "document.json", doc.model_dump(mode="json"))
                write(dest / "bindings.json", bindings)
                (dest / "document.md").write_text(markdown)
                result["serialize_reload_save_seconds"] = time.monotonic()-export_started
                result["status"] = "mapped and reloaded; semantic quality not evaluated"
            except (ValueError, KeyError, IndexError, TypeError, AssertionError) as error:
                result.update(status="unaccepted: mapping failed", error_type=type(error).__name__)
        result["page_assembly_seconds"] = time.monotonic()-page_started
        results.append(result)
    write(directory / "page-assembly.json", results)
    return results


def resource_guard(started):
    process = psutil.Process()
    rss = 0
    for item in [process] + process.children(recursive=True):
        try:
            rss += item.memory_info().rss
        except psutil.NoSuchProcess:
            pass
    sample = dict(seconds=time.monotonic()-started, rss=rss, available=psutil.virtual_memory().available)
    if sample["seconds"] >= LIVE_SECONDS or rss >= 12*2**30 or sample["available"] < 8*2**30:
        raise BudgetStop("time_or_memory_guard")
    return sample


def execute(reg, client, credential, directory):
    if not credential or any(c.isspace() for c in credential):
        raise ValueError("configure OPENAI_API_KEY; credential is never saved")
    directory.mkdir(exist_ok=False)  # An attempted run is never silently replayed.
    write(directory / "attempt.json", dict(calls_max=6, started_unix=time.time()))
    started = time.monotonic()
    ledger, records, stopped = dict(input=0, completion=0, calls=0), [], None
    samples, pages, request_deadline = [], None, None

    def tick(signum, frame):
        sample = resource_guard(started)
        if isinstance(sample, dict):
            samples.append(sample)
        if request_deadline is not None and time.monotonic() >= request_deadline:
            raise TimeoutError("request wall-clock limit reached")

    previous_handler = signal.signal(signal.SIGALRM, tick)
    signal.setitimer(signal.ITIMER_REAL, .25, .25)
    try:
        for job in reg["jobs"]:
            resource_guard(started)
            reserve(reg, ledger, job)
            dest = directory / job["name"]
            dest.mkdir()
            write(dest / "attempt.json", dict(request_sha256=job["http_body_sha256"], attempts=1))
            ledger["calls"] += 1
            record = dict(name=job["name"], page_name=job["page_name"], result="attempted", usage=None, usage_valid=False)
            records.append(record)
            begin = time.monotonic()
            parts = []
            try:
                request_deadline = begin + REQUEST_SECONDS
                request_body = body(job)
                http_started = time.monotonic()
                with client.stream("POST", ENDPOINT, content=request_body,
                    headers={"Authorization": "Bearer " + credential, "Content-Type": "application/json"}) as reply:
                    parts, size = [], 0
                    for part in reply.iter_bytes():
                        resource_guard(started)
                        size += len(part)
                        if size > reg["transport_bytes"]:
                            prefix = b"".join(parts) + part
                            (dest / "response.partial.txt").write_text(prefix[:reg["transport_bytes"]].decode(
                                "utf-8", errors="replace").replace(credential, "[REDACTED]"))
                            raise BudgetStop("transport_bytes_exceeded")
                        parts.append(part)
                    try:
                        raw = b"".join(parts).decode().replace(credential, "[REDACTED]")
                    except UnicodeDecodeError:
                        raise BudgetStop("invalid_provider_encoding_usage_unknown") from None
                    record["http_status"] = reply.status_code
                record["http_response_seconds"] = time.monotonic()-http_started
                (dest / "response.json").write_text(raw)
                if record["http_status"] != 200:
                    raise BudgetStop("http_error_usage_unknown")
                try:
                    response = json.loads(raw)
                except (ValueError, TypeError):
                    raise BudgetStop("invalid_provider_envelope_usage_unknown") from None
                if not isinstance(response, dict):
                    raise BudgetStop("invalid_provider_envelope_usage_unknown")
                record.update(usage=response.get("usage"), model=response.get("model"))
                record["usage_valid"] = valid_usage(record["usage"])
                charge(reg, ledger, job, record["usage"])
                choices = response.get("choices")
                if (not isinstance(choices, list) or len(choices) != 1
                    or not isinstance(choices[0], dict) or not isinstance(choices[0].get("message"), dict)):
                    raise BudgetStop("invalid_provider_choice_envelope")
                choice = choices[0]
                content = choice["message"].get("content")
                record["finish_reason"] = choice.get("finish_reason")
                if isinstance(content, str):
                    (dest / "content.txt").write_text(content)
                if (choice.get("finish_reason") != "stop" or choice["message"].get("refusal")
                    or not isinstance(content, str) or len(content.encode()) > reg["content_bytes"]):
                    raise ValueError("incomplete, refused or out-of-envelope content")
                payload = p.parse(json.loads(content), [job["target_key"]])
                for target in payload.targets:
                    for panel in target.panels:
                        p.adapter.Data.model_validate(panel.data.data())
                write(dest / "output.json", payload.model_dump(mode="json"))
                record["result"] = "valid_target"
            except (httpx.HTTPError, TimeoutError):
                record["result"] = "transport_or_timeout_usage_unknown"
                raise BudgetStop(record["result"]) from None
            except BudgetStop as error:
                record["result"] = str(error)
                raise
            except (ValueError, KeyError, IndexError, TypeError) as error:
                record.update(result="target_rejected", error_type=type(error).__name__)
            finally:
                request_deadline = None
                record["seconds"] = time.monotonic()-begin
                if parts and not (dest / "response.json").exists() and not (dest / "response.partial.txt").exists():
                    (dest / "response.partial.txt").write_text(b"".join(parts)[:reg["transport_bytes"]].decode(
                        "utf-8", errors="replace").replace(credential, "[REDACTED]"))
        pages = assemble(reg, records, directory)
    except BudgetStop as error:
        stopped = str(error)
    except Exception as error:
        stopped = "runner_error:" + type(error).__name__
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        write(directory / "observations.json", records)
        write(directory / "resource-samples.json", samples)
        write(directory / "execution.json", dict(ledger=ledger, stopped=stopped,
            all_six_attempted=ledger["calls"] == 6, elapsed_seconds=time.monotonic()-started,
            unknown_usage=any(not r["usage_valid"] for r in records), new_baseline_inferences=0))
        if pages is None and not (directory / "page-assembly.json").exists():
            write(directory / "page-assembly.json", [dict(name=page["name"],
                status="unaccepted: run stopped before complete assembly", quality_evaluated=False) for page in reg["pages"]])
    return dict(ledger=ledger, stopped=stopped, records=records)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode == "--freeze":
        result = freeze()
        print(json.dumps({k: result[k] for k in ("calls_max", "total_input_budget", "total_completion_budget")}))
    elif mode == "--verify":
        verify()
        print("frozen methods, sources and six requests verified; no API")
    elif mode == "--live":
        reg = verify()
        if psutil.virtual_memory().available < 10*2**30:
            raise SystemExit("start requires 10 GiB available")
        with httpx.Client(timeout=httpx.Timeout(REQUEST_SECONDS, connect=20), follow_redirects=False, trust_env=False) as client:
            result = execute(reg, client, os.environ.get("OPENAI_API_KEY", ""), HERE / "live")
        print(json.dumps(dict(ledger=result["ledger"], stopped=result["stopped"])))
    else:
        raise SystemExit("use --freeze, --verify or --live")
