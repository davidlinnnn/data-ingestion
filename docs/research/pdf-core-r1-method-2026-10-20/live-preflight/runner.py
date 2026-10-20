"""Sequential bounded runner, transport injected. CLI can only use offline MOCKs."""
from collections import defaultdict
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import sys
import time

import protocol as p


def write(path, value):
    path = Path(path)
    data = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with path.open("x") as stream:
        stream.write(data)


def offline_guard(event, args):
    if event in {"socket.connect", "socket.getaddrinfo"}:
        raise RuntimeError("ZERO_INFERENCE: network denied")
    if event == "open" and isinstance(args[0], (str, bytes)):
        name = os.fsdecode(args[0])
        if any(s in name for s in ("holdout", "live-preflight/evaluator", "pdf-core-w2-native-coverage", "/.ssh/", "/.aws/")):
            raise RuntimeError("runner cannot read evaluator/holdout/W2/credentials")
        if any(c in (args[1] or "") for c in "wax+") and not Path(name).resolve().is_relative_to(p.HERE):
            raise RuntimeError("write outside preflight")


def timeout_alarm(signum, frame):
    raise TimeoutError("hard request/batch wall deadline")


def validate_provider(job, body, response, reservation):
    if response.get("model") != p.MODEL:
        raise ValueError("provider model mismatch")
    usage = response.get("usage", {})
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if type(usage.get(key)) is not int or usage[key] < 0:
            raise ValueError("invalid usage")
    if usage["prompt_tokens"] + usage["completion_tokens"] != usage["total_tokens"]:
        raise ValueError("incoherent usage")
    if (usage["prompt_tokens"] > reservation or
            usage["completion_tokens"] > body["max_completion_tokens"]):
        raise ValueError("token reservation exceeded")
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError("exactly one completion required")
    choice = choices[0]
    if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
        raise ValueError("refused/truncated completion")
    content = choice["message"].get("content")
    if not isinstance(content, str) or len(content.encode()) > 1048576:
        raise ValueError("invalid/oversize content")
    value = json.loads(content)
    p.validate_payload(job, value)
    return value


def mock_transport(job, body, timeout_seconds):
    value = p.mock_payload(job)
    return {"id": "MOCK-" + job["job_id"], "model": p.MODEL,
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value, ensure_ascii=False), "refusal": None}}]}


def http_transport(job, body, timeout_seconds, *, client=None):
    """Prepared bounded HTTP seam, unreachable from this offline-only CLI."""
    import httpx
    key=os.environ.get("OPENAI_API_KEY")
    if not key:raise RuntimeError("credential unavailable")
    if not 0 < timeout_seconds <= 180:raise ValueError("HTTP time budget")
    request=p.encoded(body)
    if len(request)>16777216:raise ValueError("HTTP input byte budget")
    owned=client is None
    if owned:
        client=httpx.Client(transport=httpx.HTTPTransport(retries=0),follow_redirects=False,trust_env=False)
    try:
        with client.stream("POST",p.ENDPOINT,content=request,
                headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},
                timeout=timeout_seconds,follow_redirects=False) as response:
            if response.status_code!=200:raise RuntimeError("HTTP status "+str(response.status_code))
            chunks=[];size=0
            for chunk in response.iter_bytes(chunk_size=16384):
                size+=len(chunk)
                if size>1048576:raise ValueError("HTTP response byte budget")
                chunks.append(chunk)
            return json.loads(b"".join(chunks))
    finally:
        if owned:client.close()


def run(jobs, destination, transport, *, mock_only, reservations=None,
        request_seconds=180, batch_seconds=3600):
    # shortcut: UNIX main-thread alarm, matching this macOS DEV runtime; use an
    # isolated worker before adopting this runner on other runtimes/threads.
    if not mock_only:
        raise RuntimeError("LIVE_DISABLED: separate mainline authorization and verified reservations required")
    if request_seconds <= 0 or batch_seconds <= 0 or request_seconds > 180 or batch_seconds > 3600:
        raise ValueError("invalid/increased time budget")
    if len({j["job_id"] for j in jobs}) != len(jobs) or len(jobs) > 43:
        raise ValueError("duplicate/excess jobs")
    destination = Path(destination)
    if not destination.resolve().is_relative_to(p.HERE):
        raise ValueError("output escaped preflight")
    destination.mkdir()
    started = time.monotonic()
    ledger = []
    payloads = {}
    stop = None
    previous = signal.signal(signal.SIGALRM, timeout_alarm)
    try:
        for job in jobs:
            row = {"job_id": job["job_id"], "task": job["task"], "mode": "MOCK",
                "attempts": 0, "state": "NOT_RUN", "new_inference_calls": 0}
            ledger.append(row)
            if stop:
                row["reason"] = "previous failure; no retry or automatic resume"
                continue
            if time.monotonic() - started >= batch_seconds:
                stop = "batch deadline before request"
                row["reason"] = stop
                continue
            request_start = time.monotonic()
            raw_response = None
            try:
                signal.setitimer(signal.ITIMER_REAL, min(request_seconds, batch_seconds - (request_start-started)))
                body = p.materialize(job)
                request = p.encoded(body)
                if len(request) > 16777216:
                    raise ValueError("input byte budget")
                reservation = (reservations or {}).get(job["job_id"], 922000)
                if type(reservation) is not int or not 0 < reservation <= 922000:
                    raise ValueError("invalid reservation")
                if body["max_completion_tokens"] > 128000 or reservation + body["max_completion_tokens"] > 1050000:
                    raise ValueError("endpoint token capacity")
                row.update(request_sha256=p.sha(request), request_bytes=len(request),
                    completion_cap=body["max_completion_tokens"], input_reservation=reservation,
                    reservation_status="MOCK_ONLY_UNVERIFIED_FOR_LIVE")
                row["attempts"] = 1
                raw_response = transport(job, body, min(request_seconds,
                    batch_seconds-(time.monotonic()-started)))
                if time.monotonic()-request_start >= request_seconds or time.monotonic()-started >= batch_seconds:
                    raise TimeoutError("transport returned after deadline")
                if len(p.encoded(raw_response)) > 1048576:
                    raise ValueError("transport byte budget")
                value = validate_provider(job, body, raw_response, reservation)
                payloads[job["job_id"]] = value["payload"]
                row["state"] = "MOCK_VALIDATED"
                row["response_sha256"] = p.sha(p.encoded(raw_response))
            except Exception as error:
                stop = type(error).__name__ + ": " + str(error)[:240]
                row.update(state="FAILED", reason=stop)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                row["elapsed_seconds"] = time.monotonic() - request_start
                if raw_response is not None:
                    response_bytes = p.encoded(raw_response)
                    write(destination / (job["job_id"] + ".json"), {"mode": "MOCK", "record": row,
                        "raw_provider_response": raw_response if len(response_bytes)<=1048576 else None,
                        "raw_response_bytes":len(response_bytes), "raw_response_sha256":p.sha(response_bytes),
                        "oversize_body_omitted":len(response_bytes)>1048576,"source_quality_verified": False})
                # Exclusive per-job receipts survive an interruption; final ledger
                # uses a new name so an earlier receipt is never overwritten.
                write(destination / (job["job_id"] + ".receipt.json"), row)
        write(destination / "final-ledger.json", ledger)
        if not stop and len(payloads) == len(jobs):
            try:
                remaining = batch_seconds-(time.monotonic()-started)
                if remaining <= 0:
                    raise TimeoutError("batch deadline before delivery")
                signal.setitimer(signal.ITIMER_REAL, remaining)
                deliver(jobs, payloads, destination)
            except Exception as error:
                stop = "DELIVERY_FAILED: " + type(error).__name__ + ": " + str(error)[:240]
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
        summary = {"mode": "MOCK", "jobs": len(jobs), "validated": len(payloads),
            "failed": sum(r["state"] == "FAILED" for r in ledger),
            "not_run": sum(r["state"] == "NOT_RUN" for r in ledger), "stop": stop,
            "elapsed_seconds": time.monotonic()-started, "new_inference_calls": 0,
            "concurrency": 1, "retry": 0, "best_of": 1,
            "request_seconds": request_seconds, "batch_seconds": batch_seconds,
            "live_ready": False, "source_quality_verified": False}
        write(destination / "summary.json", summary)
        return summary
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def deliver(jobs, payloads, destination):
    output = destination / "delivery-pending"
    output.mkdir()
    sources = defaultdict(list)
    images = defaultdict(dict)
    for job in jobs:
        payload = payloads[job["job_id"]]
        if job["task"] == "source_reconstruction":
            sources[job["baseline"]].append((job["binding"], payload))
        else:
            images[p.m.digest(job["binding"])][job["task"]] = (job, payload)
    for baseline, members in sources.items():
        result = p.assemble.apply_groups(p.read(p.ROOT / baseline), members)
        name = p.sha(baseline.encode())[:16]
        write(output / (name + ".source.json"), {"mode": "MOCK", "baseline": baseline, "result": result})
    for lanes in images.values():
        description_job, description = lanes["description_with_context_OCR"]
        chart_job, chart = lanes["chart_assessment"]
        bound = description_job["binding"]
        if bound != chart_job["binding"]:
            raise ValueError("different C lane scopes")
        observations = {key: {"context_key": bound["context_key"],
            "image_ocr": {"scope": "crop", "text": "", "status": "unreadable"},
            **description["images"][key], "chart": chart["images"][key]} for key in description["images"]}
        supplement = p.m.supplement(p.read(p.ROOT / description_job["baseline"]), bound, observations)
        write(output / (p.m.digest(bound) + ".supplement.json"), {"mode": "MOCK",
            "local_crop_OCR": "MOCK_UNREADABLE_NOT_EXECUTED", "supplement": supplement})
    output.rename(destination / "delivery")


if __name__ == "__main__":
    os.environ.pop("OPENAI_API_KEY", None)
    sys.addaudithook(offline_guard)
    jobs = p.read(p.R1 / "planning/jobs.json")["jobs"]
    print(json.dumps(run(jobs, p.HERE / "dry-run", mock_transport, mock_only=True)))
