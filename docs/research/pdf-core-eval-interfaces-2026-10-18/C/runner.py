"""Bounded synchronous native-image client; source gates precede credentials/network."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from importlib.metadata import version
import os
from pathlib import Path
import signal
import sys
import time

import httpx
import psutil
import producer as p

HERE = Path(__file__).resolve().parent
ENDPOINT = "https://api.openai.com/v1/chat/completions"


class Stop(Exception): pass


def redact(value, credential):
    if isinstance(value,str): return value.replace(credential,"[REDACTED]")
    if isinstance(value,list): return [redact(v,credential) for v in value]
    if isinstance(value,dict): return {redact(k,credential):redact(v,credential) for k,v in value.items()}
    return value


def loads(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def save(path, value):
    with Path(path).open("x") as stream: json.dump(value, stream, ensure_ascii=False, indent=2)


def source_gate(manifest):
    coverage = p.read(HERE / "source-coverage.json")
    contracts = HERE / "source-contract-index.json"
    if coverage.get("full_C_coverage_gate") != "pass": raise Stop("source_coverage_blocked")
    if not contracts.exists(): raise Stop("source_contracts_not_ready")
    ready = p.read(contracts)
    if ready.get("full_C_source_contracts_ready") is not True:
        raise Stop("source_contracts_not_ready")


def verify(manifest):
    pins = p.read(HERE / "runner-verification.json")["input_hashes"]
    if any(p.sha(path) != expected for path, expected in pins.items()): raise Stop("frozen_input_changed")
    lock = p.read(HERE.parent / "runtime-lock.json")
    if (sys.version.split()[0] != lock["python"] or any(version(v["name"]) != v["version"] for v in lock["packages"])
        or any(p.sha(path) != item["sha256"] for path,item in lock["selected_runtime_source_files"].items())): raise Stop("runtime_changed")
    if manifest["endpoint"] != ENDPOINT or manifest["retry"] != 0 or manifest["concurrency"] != 1:
        raise Stop("endpoint_or_execution_policy_changed")
    jobs = manifest["jobs"]
    if len({j["job_id"] for j in jobs}) != len(jobs): raise Stop("duplicate_job")
    for job in jobs:
        raw = p.materialize(job)
        if len(raw) > 8*2**20 or hashlib.sha256(raw).hexdigest() != job["request_sha256"]:
            raise Stop("request_size_or_hash_changed")
    return manifest


def execute(manifest, client, credential, directory):
    if not credential or any(c.isspace() for c in credential): raise Stop("credential_unavailable")
    directory.mkdir(exist_ok=False)
    save(directory / "attempt.json", {"jobs_max": len(manifest["jobs"]), "started": datetime.now(timezone.utc).isoformat()})
    ledger = {"calls": 0, "input": 0, "completion": 0}; records = []; stopped = None
    started = time.monotonic(); deadline = None
    def guard(signum=None, frame=None):
        if (time.monotonic()-started >= manifest["remote_live_seconds_cap"]
            or psutil.Process().memory_info().rss >= manifest["rss_max_bytes"]
            or psutil.virtual_memory().available < manifest["minimum_available_bytes"]): raise Stop("time_or_memory_guard")
        if deadline is not None and time.monotonic() >= deadline: raise TimeoutError("request_wall_timeout")
    previous = signal.signal(signal.SIGALRM, guard); signal.setitimer(signal.ITIMER_REAL, .25, .25)
    try:
        for job in manifest["jobs"]:
            guard()
            if (ledger["calls"] >= manifest["calls_candidate"]
                or ledger["input"]+job["input_tokens_reserve"] > manifest["input_tokens_reserve_total"]
                or ledger["completion"]+job["output_tokens_cap"] > manifest["completion_tokens_cap_total"]): raise Stop("pre_request_budget")
            request = p.materialize(job)
            if len(request) > 8*2**20 or hashlib.sha256(request).hexdigest() != job["request_sha256"]:
                raise Stop("stale_request_or_crop")
            dest = directory / job["job_id"]; dest.mkdir()
            record = {"job_id": job["job_id"], "input": job["binding"], "request_sha256": job["request_sha256"], "status": "attempted"}
            records.append(record); ledger["calls"] += 1; parts = []; size = 0
            deadline = time.monotonic()+job["max_seconds"]
            try:
                with client.stream("POST", ENDPOINT, content=request,
                    headers={"Authorization": "Bearer "+credential, "Content-Type": "application/json"}) as response:
                    for part in response.iter_bytes(chunk_size=65536):
                        guard(); remaining = job["transport_bytes_max"]-size
                        parts.append(part[:max(0,remaining)]); size += len(part)
                        if size > job["transport_bytes_max"]: raise Stop("transport_bytes_exceeded")
                    raw = b"".join(parts).replace(credential.encode(),b"[REDACTED]")
                    if response.status_code != 200: raise Stop("http_error_usage_unknown")
                try: provider = redact(loads(raw.decode("utf-8")),credential)
                except (ValueError, UnicodeDecodeError): raise Stop("invalid_provider_usage_unknown") from None
                usage = provider.get("usage") if isinstance(provider, dict) else None
                if (not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                    for k in ("prompt_tokens","completion_tokens","total_tokens"))
                    or usage["total_tokens"] != usage["prompt_tokens"]+usage["completion_tokens"]): raise Stop("usage_unknown_or_invalid")
                ledger["input"] += usage["prompt_tokens"]; ledger["completion"] += usage["completion_tokens"]
                record.update(provider_id=provider.get("id"), provider_model=provider.get("model"), usage=usage)
                if (usage["prompt_tokens"] > job["input_tokens_reserve"] or usage["completion_tokens"] > job["output_tokens_cap"]
                    or ledger["input"] > manifest["input_tokens_reserve_total"]
                    or ledger["completion"] > manifest["completion_tokens_cap_total"]): raise Stop("actual_usage_overrun")
                choices = provider.get("choices")
                if (not isinstance(choices,list) or len(choices)!=1 or not isinstance(choices[0],dict)
                    or not isinstance(choices[0].get("message"),dict)): raise Stop("invalid_choice_envelope")
                choice = choices[0]; message = choice["message"]; content = message.get("content")
                if choice.get("finish_reason") != "stop" or message.get("refusal"): raise ValueError("refused_or_truncated")
                if not isinstance(content,str) or len(content.encode()) > job["content_bytes_max"]: raise ValueError("content_limit")
                envelope = {"input": job["binding"], "request_sha256": job["request_sha256"],
                    "model": provider.get("model"), "usage": usage, "finish_reason": choice["finish_reason"],
                    "refusal": message.get("refusal"), "payload": redact(loads(content),credential)}
                payload = p.validate_response(job,envelope)
                receipts = directory / "receipts" / job["binding"]["image_key"]; receipts.mkdir(parents=True,exist_ok=True)
                save(receipts / (job["task"]+".json"), {"input": job["binding"], "request_sha256": job["request_sha256"],
                    "provider_id": provider.get("id"), "provider_model": provider.get("model"), "usage": usage,
                    "payload": payload, "state": "validated_transport_only", "semantic_acceptance": False})
                record["status"] = "validated_transport_only"
            except (httpx.HTTPError, TimeoutError): raise Stop("transport_or_timeout_usage_unknown") from None
            except (ValueError,KeyError,TypeError,IndexError) as error:
                record.update(status="rejected", error_type=type(error).__name__)
            finally:
                deadline = None
                (dest / "response.raw").write_bytes(b"".join(parts).replace(credential.encode(),b"[REDACTED]"))
    except Stop as error: stopped = str(error)
    except Exception as error: stopped = "runner_error:"+type(error).__name__
    finally:
        if stopped and records and records[-1]["status"] == "attempted": records[-1].update(status="stopped",reason=stopped)
        signal.setitimer(signal.ITIMER_REAL,0); signal.signal(signal.SIGALRM,previous)
        save(directory / "execution.json", {"ledger": ledger, "stopped": stopped, "records": records,
            "primary_markdown_mutated": False, "semantic_acceptance": False,
            "memory_scope": "current process; runner spawns no children"})
    return {"ledger": ledger, "stopped": stopped, "records": records}


def main():
    parser = argparse.ArgumentParser(); flags = parser.add_mutually_exclusive_group(required=True)
    flags.add_argument("--dry-run", action="store_true"); flags.add_argument("--live", action="store_true")
    parser.add_argument("--credential-env", default="OPENAI_API_KEY"); args = parser.parse_args()
    manifest = p.read(HERE / "requests.json")
    if args.live: source_gate(manifest)
    verify(manifest)
    if args.dry_run:
        print(json.dumps({"requests_verified":len(manifest["jobs"]),"remote_calls":0,"credential_read":False,
            "source_gate":p.read(HERE / "source-coverage.json")["full_C_coverage_gate"]})); return
    credential = os.environ.get(args.credential_env, "")
    with httpx.Client(timeout=httpx.Timeout(180,connect=20),trust_env=False,follow_redirects=False) as client:
        print(json.dumps(execute(manifest,client,credential,HERE / "live")))


if __name__ == "__main__":
    try: main()
    except Stop as error: raise SystemExit(str(error)) from None
