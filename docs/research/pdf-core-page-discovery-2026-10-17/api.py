"""One immutable eight-page run; credential only in process memory, no retries."""
import base64
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import signal
import sys
import time

import httpx
import discovery as d

HERE = Path(__file__).resolve().parent
RESPONSE_BYTES = 262144


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def body(reg, job):
    config, budget = reg["detector"], reg["budgets"]
    image = base64.b64encode((d.ROOT/job["image"]).read_bytes()).decode()
    return encoded(dict(model=config["model"], store=config["store"],
        reasoning_effort=config["reasoning_effort"], response_format=config["response_format"],
        max_completion_tokens=budget["max_completion_tokens"],
        messages=[dict(role="user",content=[dict(type="text",text=config["prompt"]),
            dict(type="image_url",image_url=dict(url="data:image/png;base64,"+image,
                                                detail=config["image_detail"]))])]))


def seal_check(records, root=HERE):
    for name, expected in records.items():
        if d.file_hash(root/name) != expected:
            raise ValueError("changed sealed input: " + name)


def freeze():
    old = json.loads((HERE/"verification.json").read_text())
    seal_check(old["inputs_and_methods_seal"])
    d.verify()
    reg = json.loads((HERE/"registration.json").read_text())
    if reg["budgets"]["calls_max"] != 8 or reg["budgets"]["reconstruction_calls"] != 0:
        raise ValueError("unexpected frozen budget")
    value = dict(frozen_at=datetime.now(timezone.utc).isoformat(),
        files={name:d.file_hash(HERE/name) for name in ("registration.json","verification.json",
            "discovery.py","test_discovery.py","api.py","test_api.py","api-test-results.json")},
        requests={j["id"]:d.sha256(body(reg,j)).hexdigest() for j in reg["jobs"]},
        response_bytes=RESPONSE_BYTES, credential_storage="process memory only",
        endpoint=reg["detector"]["endpoint"], calls_max=8, retries=0,
        provider_sources=["https://developers.openai.com/api/docs/models/gpt-6-luna",
            "https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create"],
        evaluation="Freeze evaluator before requests; producer receives no source census or manual boxes.")
    tests=json.loads((HERE/"api-test-results.json").read_text())
    if not tests["passed"] or tests["tests"] < 1:
        raise ValueError("runner controls not passed")
    d.write(HERE/"live-registration.json",value)
    return value


def verify():
    live=json.loads((HERE/"live-registration.json").read_text())
    seal_check(live["files"])
    d.verify()
    reg=json.loads((HERE/"registration.json").read_text())
    expected={j["id"]:d.sha256(body(reg,j)).hexdigest() for j in reg["jobs"]}
    if expected != live["requests"]:
        raise ValueError("changed request")
    return reg,live


class BudgetStop(Exception):
    pass


def reserve(budget, ledger):
    if (ledger["calls"] >= budget["calls_max"]
            or ledger["input"]+budget["input_reservation_per_job"] > budget["aggregate_input_reservation"]
            or ledger["completion"]+budget["max_completion_tokens"] > budget["total_completion_tokens"]):
        raise BudgetStop("pre_request_budget")


def charge(budget, ledger, usage):
    if (not isinstance(usage,dict)
            or any(type(usage.get(key)) is not int or usage[key] < 0
                   for key in ("prompt_tokens","completion_tokens"))):
        raise BudgetStop("usage_unavailable")
    ledger["input"] += usage["prompt_tokens"]
    ledger["completion"] += usage["completion_tokens"]
    if (usage["prompt_tokens"] > budget["input_reservation_per_job"]
            or usage["completion_tokens"] > budget["max_completion_tokens"]
            or ledger["input"] > budget["aggregate_input_reservation"]
            or ledger["completion"] > budget["total_completion_tokens"]):
        raise BudgetStop("actual_usage_overrun")


def unique_fields(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key]=value
    return result


def parse_content(reply):
    choices=reply.get("choices")
    if not isinstance(choices,list) or len(choices) != 1:
        raise ValueError("invalid choices")
    choice=choices[0]
    if choice.get("finish_reason") != "stop":
        raise ValueError("non_stop_finish")
    message=choice.get("message",{})
    if message.get("refusal") or not isinstance(message.get("content"),str):
        raise ValueError("refusal_or_missing_content")
    return json.loads(message["content"],object_pairs_hook=unique_fields)


def progress(directory,ledger,records):
    path=directory/"progress.json"
    tmp=directory/"progress.tmp"
    tmp.write_bytes(encoded(dict(ledger=ledger,records=records)))
    tmp.replace(path)


def timeout_handler(signum,frame):
    raise TimeoutError("request wall-clock deadline")


def execute(reg,live,credential,client,directory):
    if not credential or any(c.isspace() for c in credential):
        raise ValueError("missing credential")
    directory.mkdir(exist_ok=False)
    d.write(directory/"attempt.json",dict(started_at=datetime.now(timezone.utc).isoformat(),
        registration_sha256=d.file_hash(HERE/"live-registration.json"),calls_max=8,retries=0))
    started=time.monotonic()
    ledger=dict(calls=0,input=0,completion=0)
    records=[]
    stopped=None
    previous=signal.signal(signal.SIGALRM,timeout_handler)
    try:
        for job in reg["jobs"]:
            remaining=reg["budgets"]["total_seconds"]-(time.monotonic()-started)
            if remaining <= 0:
                stopped="total_wall_limit"; break
            try:
                reserve(reg["budgets"],ledger)
            except BudgetStop as error:
                stopped=str(error); break
            request=body(reg,job)
            if d.sha256(request).hexdigest() != live["requests"][job["id"]]:
                stopped="request_binding_changed"; break
            dest=directory/job["id"]
            dest.mkdir()
            d.write(dest/"attempt.json",dict(request_sha256=live["requests"][job["id"]],attempts=1))
            record=dict(job_id=job["id"],status="attempted",usage=None)
            records.append(record); ledger["calls"]+=1
            progress(directory,ledger,records)
            begin=time.monotonic()
            signal.setitimer(signal.ITIMER_REAL,min(remaining,reg["budgets"]["per_request_seconds"]))
            try:
                with client.stream("POST",live["endpoint"],content=request,
                        headers={"Authorization":"Bearer "+credential,"Content-Type":"application/json"}) as reply:
                    record["http_status"]=reply.status_code
                    if reply.status_code != 200:
                        raise BudgetStop("http_error_usage_unknown")
                    chunks=[]; size=0
                    for chunk in reply.iter_bytes():
                        size+=len(chunk)
                        if size > RESPONSE_BYTES:
                            raise BudgetStop("transport_limit_usage_unknown")
                        chunks.append(chunk)
                raw=b"".join(chunks)
                if credential.encode() in raw:
                    raise BudgetStop("credential_in_response_not_saved")
                (dest/"response.json").write_bytes(raw)
                packet=json.loads(raw,object_pairs_hook=unique_fields)
                record["usage"]=packet.get("usage")
                charge(reg["budgets"],ledger,record["usage"])
                record["reported_model"]=packet.get("model")
                record["finish_reason"]=(packet.get("choices") or [{}])[0].get("finish_reason")
                try:
                    output=d.bind_response(job,parse_content(packet))
                    d.write(dest/"binding.json",output)
                    record.update(status="valid_detector_output",regions=len(output["candidates"]),
                                  claimed_complete=output["model_claimed_complete"])
                except (ValueError,KeyError,TypeError,IndexError) as error:
                    record.update(status="invalid_detector_output",validation_error_type=type(error).__name__)
            except BudgetStop as error:
                record["status"]=str(error); stopped=str(error)
            except (httpx.HTTPError,TimeoutError,ValueError,TypeError,KeyError) as error:
                record.update(status="request_or_packet_failure_usage_uncertain",error_type=type(error).__name__)
                stopped=record["status"]
            finally:
                signal.setitimer(signal.ITIMER_REAL,0)
                record["seconds"]=time.monotonic()-begin
                progress(directory,ledger,records)
            print(json.dumps(record),flush=True)
            if stopped:
                break
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)
    result=dict(ledger=ledger,records=records,stopped=stopped,seconds=time.monotonic()-started,
        requested_pages=8,unattempted_pages=8-ledger["calls"],retries=0,
        reconstruction_calls=0,source_coverage_verified=False,
        cost_scope="Detector requests only; no Standard rerun or reconstruction cost.")
    d.write(directory/"results.json",result)
    return result


if __name__ == "__main__":
    mode=sys.argv[1:]
    if mode == ["--freeze"]:
        print(json.dumps(dict(status="live_method_frozen",requests=len(freeze()["requests"]))))
    elif mode == ["--verify"]:
        reg,live=verify()
        print(json.dumps(dict(status="live_inputs_verified",requests=len(live["requests"]))))
    elif mode == ["--live"]:
        reg,live=verify()
        credential=os.environ.get("OPENAI_API_KEY") or getpass.getpass("API credential (not saved): ")
        with httpx.Client(timeout=180,transport=httpx.HTTPTransport(retries=0),
                          follow_redirects=False,trust_env=False) as client:
            result=execute(reg,live,credential,client,HERE/"live")
        credential=None
        print(json.dumps(dict(status="run_closed",ledger=result["ledger"],stopped=result["stopped"])))
    else:
        raise SystemExit("Use --freeze once, --verify, or --live once.")
