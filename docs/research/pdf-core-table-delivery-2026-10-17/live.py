"""Two fixed page requests; public mapping only, no oracle or content repair."""
import base64
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = ROOT / "docs/research/pdf-core-native-round-2026-10-17"


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_child():
    import torch
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    spec = importlib.util.spec_from_file_location("old_native", OLD/"run.py")
    native = importlib.util.module_from_spec(spec); spec.loader.exec_module(native)
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    dest = HERE/"memory-r1-p8"
    opts = native.options("S0")
    def comparable(value):
        if isinstance(value,dict):
            return {k:sorted(v) if k=="supported_engines" and isinstance(v,list) else comparable(v) for k,v in value.items()}
        if isinstance(value,list): return [comparable(v) for v in value]
        return value
    assert comparable(opts.model_dump(mode="json",serialize_as_any=True)) == comparable(json.loads((OLD/"S0/effective-options.json").read_text()))
    save(dest/"effective-options.json",opts.model_dump(mode="json",serialize_as_any=True))
    source = ROOT/"docs/fixtures/agent-self-evolution-pilot-2026-10-11/11-2508.19828v5.pdf"
    save(dest/"source.json",{"path":str(source.relative_to(ROOT)),"sha256":sha(source),"page_range":[8,8]})
    converter=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(
        pipeline_cls=StandardPdfPipeline,pipeline_options=opts,backend=PyPdfiumDocumentBackend)})
    result=converter.convert(source,page_range=(8,8))
    save(dest/"conversion.json",{"status":result.status.value,"errors":[e.model_dump(mode="json") for e in result.errors]})
    assert result.status.value=="success"
    result.document.save_as_json(dest/"baseline.json")
    result.pages[0].get_image(scale=2).save(dest/"input.png")


def prepare():
    dest=HERE/"memory-r1-p8";dest.mkdir(exist_ok=False)
    env=os.environ.copy();env.update(HF_HOME="/private/tmp/pdf-core-native-20261017/hf",HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",TOKENIZERS_PARALLELISM="false",OMP_NUM_THREADS="4")
    start=time.monotonic();samples=[];reason=None
    with (dest/"worker.log").open("w") as log:
        proc=subprocess.Popen(["rtk","proxy",sys.executable,str(Path(__file__).resolve()),"--prepare-child"],stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        try:
            while proc.poll() is None:
                try:
                    root=psutil.Process(proc.pid);rss=sum(p.memory_info().rss for p in [root]+root.children(recursive=True) if p.is_running())
                except psutil.NoSuchProcess: rss=0
                available=psutil.virtual_memory().available
                samples.append({"seconds":time.monotonic()-start,"rss":rss,"available":available})
                if samples[-1]["seconds"]>180 or rss>12*2**30 or available<8*2**30:
                    reason="time_or_memory_guard";break
                time.sleep(.1)
        finally:
            if proc.poll() is None: os.killpg(proc.pid,signal.SIGKILL)
            proc.wait()
    save(dest/"execution.json",{"exit_code":proc.returncode,"guard":reason,"samples":samples,"attempts":1})
    assert proc.returncode==0 and reason is None,"S0 preparation failed; no retry"


def freeze():
    from docling_core.types.doc import DoclingDocument
    from mapper import inventory
    config=json.loads((HERE/"api-readiness.json").read_text())
    for name,digest in config["protocol_sha256"].items(): assert sha(HERE/name)==digest
    jobs=[]
    for name,baseline,image in (
        ("memory-r1-p8",HERE/"memory-r1-p8/baseline.json",HERE/"memory-r1-p8/input.png"),
        ("skillopt-p8",OLD/"S0/skillopt/document.json",OLD/"S0/skillopt/page-8.png")):
        doc=DoclingDocument.model_validate_json(baseline.read_text())
        targets=[]
        for key,table in inventory(doc,8).items():
            b=table.prov[0].bbox.to_top_left_origin(page_height=doc.pages[8].size.height)
            targets.append({"target_key":key,"bbox":[2*b.l,2*b.t,2*b.r,2*b.b]})
        jobs.append({"name":name,"baseline":str(baseline),"baseline_sha256":sha(baseline),"image":str(image),"image_sha256":sha(image),"page_no":8,"targets":targets})
    assert len(jobs)==2 and 0<sum(len(j["targets"]) for j in jobs)<=8
    for job in jobs:
        image=Path(job["image"]).read_bytes()
        prompt=(HERE/"prompt.txt").read_text()+"\nSchema:\n"+(HERE/"response-schema.json").read_text()+"\nNative targets:\n"+json.dumps(job["targets"])
        body={k:config[k] for k in ("model","store","reasoning_effort","max_completion_tokens","response_format")}
        body["messages"]=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":"data:image/png;base64,"+base64.b64encode(image).decode(),"detail":"high"}}]}]
        job["http_body_sha256"]=hashlib.sha256(json.dumps(body,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
        body["messages"][0]["content"][1]["image_url"]["url"]="IMAGE_FROM_REGISTERED_PATH"
        job["body_without_image"]=body
    save(HERE/"live-registration.json",{"jobs":jobs,"runner_sha256":sha(Path(__file__)),"credential_storage":"hidden TTY/process memory only; user supplied this turn", "automatic_retries":0,"configuration_count":1})
    print("Frozen page targets:",[(j["name"],len(j["targets"])) for j in jobs],flush=True)


def live():
    import httpx
    from docling_core.types.doc import DoclingDocument
    from mapper import map_response
    assert sys.stdin.isatty()
    credential=getpass.getpass("API credential (hidden; process memory only): ")
    assert credential and not any(c.isspace() for c in credential)
    reg=json.loads((HERE/"live-registration.json").read_text());records=[];start=time.monotonic()
    with httpx.Client(timeout=httpx.Timeout(180,connect=20),follow_redirects=False,trust_env=False) as client:
        for job in reg["jobs"]:
            assert time.monotonic()-start<1800 and psutil.virtual_memory().available>=8*2**30
            assert psutil.Process().memory_info().rss<12*2**30
            dest=HERE/job["name"];dest.mkdir(exist_ok=True)
            assert not (dest/"response.json").exists(),"never replay an already attempted request"
            assert sha(Path(job["baseline"]))==job["baseline_sha256"] and sha(Path(job["image"]))==job["image_sha256"]
            body=job["body_without_image"]
            body["messages"][0]["content"][1]["image_url"]["url"]="data:image/png;base64,"+base64.b64encode(Path(job["image"]).read_bytes()).decode()
            encoded=json.dumps(body,ensure_ascii=False,separators=(",",":")).encode()
            assert hashlib.sha256(encoded).hexdigest()==job["http_body_sha256"]
            begin=time.monotonic()
            try:
                reply=client.post("https://api.openai.com/v1/chat/completions",content=encoded,headers={"Authorization":"Bearer "+credential,"Content-Type":"application/json"})
            except httpx.HTTPError as error:
                save(dest/"transport-error.json",{"type":type(error).__name__,"attempts":1});raise SystemExit("transport failure; no retry") from None
            clean=re.sub(r"sk-(?:proj-)?[A-Za-z0-9_.*-]{6,}","[REDACTED]",reply.text.replace(credential,"[REDACTED]"))
            (dest/"response.json").write_text(clean)
            record={"name":job["name"],"http_status":reply.status_code,"seconds":time.monotonic()-begin,"request_id":reply.headers.get("x-request-id"),"attempts":1};records.append(record);save(HERE/"live-observations.json",records)
            if reply.status_code!=200: raise SystemExit("non-200; no retry")
            result=json.loads(clean);choice=result["choices"][0]
            record.update(model=result.get("model"),usage=result.get("usage"),finish_reason=choice.get("finish_reason"))
            if choice.get("finish_reason")!="stop" or choice["message"].get("refusal"): raise SystemExit("incomplete or refused; no retry")
            payload=json.loads(choice["message"]["content"]);save(dest/"output.json",payload)
            try:
                baseline=DoclingDocument.model_validate_json(Path(job["baseline"]).read_text())
                doc,bindings=map_response(baseline,payload,8,[t["target_key"] for t in job["targets"]])
                (dest/"document.json").write_text(doc.model_dump_json(indent=2))
                (dest/"document.md").write_text(doc.export_to_markdown())
                save(dest/"bindings.json",bindings);record["mapping"]="passed"
            except ValueError as error:
                record["mapping"]="whole-page rejected";record["mapping_error"]=str(error)
            save(HERE/"live-observations.json",records);print(json.dumps(record),flush=True)
    del credential


def guarded_live():
    stop=threading.Event();samples=[];start=time.monotonic()
    def monitor():
        while not stop.is_set():
            sample={"seconds":time.monotonic()-start,"rss":psutil.Process().memory_info().rss,"available":psutil.virtual_memory().available}
            samples.append(sample)
            if sample["seconds"]>1800 or sample["rss"]>12*2**30 or sample["available"]<8*2**30:
                save(HERE/"api-resource-guard.json",{"reason":"time_or_memory_guard","samples":samples})
                os._exit(70)
            stop.wait(.25)
    worker=threading.Thread(target=monitor,daemon=True);worker.start()
    try: live()
    finally:
        stop.set();worker.join();save(HERE/"api-resource-samples.json",samples)


if __name__=="__main__":
    {"--prepare":prepare,"--prepare-child":prepare_child,"--freeze":freeze,"--live":guarded_live}[sys.argv[1]]()
