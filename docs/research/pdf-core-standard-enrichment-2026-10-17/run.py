"""Single native enrichment experiment; reuse the previous bounded supervisor."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
PREVIOUS=HERE.parent/"pdf-core-native-round-2026-10-17"
spec=importlib.util.spec_from_file_location("native_supervisor",PREVIOUS/"run.py")
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
original_options=base.options
base.HERE=HERE
# Reuse the supervisor, but launch this experiment child rather than the historical runner.
base.__file__=str(Path(__file__).resolve())
save=base.save
sha=base.sha

class BudgetStop(BaseException):
    pass

class EvidenceStop(BaseException):
    pass

def reserve(count, size):
    if count+size>10:
        raise BudgetStop("region input budget exceeded before sending whole batch")
    return count+size

def options(profile="E1"):
    from docling.datamodel.pipeline_options import CodeFormulaVlmOptions
    from docling.datamodel.vlm_engine_options import TransformersVlmEngineOptions
    o=original_options("S0")
    c=CodeFormulaVlmOptions.from_preset("codeformulav2",engine_options=TransformersVlmEngineOptions(
        device="cpu",torch_dtype="float32",compile_model=False,quantized=False,
        load_in_8bit=False,trust_remote_code=False))
    c.model_spec.revision="ecedbe111d15c2dc60bfd4a823cbe80127b58af4"
    o.code_formula_options=c
    o.do_code_enrichment=True
    o.do_formula_enrichment=True
    return o
base.options=options
old_reason=base.reason
def reason(elapsed,*args):
    if elapsed>1800:return "model_stage_time_limit"
    return old_reason(elapsed,*args)
base.reason=reason

class Observer:
    def __init__(self,out,original_call,real=True):
        self.out=out
        self.original_call=original_call
        self.real=real
        self.count=0
        self.batches=0
        self.initial_docs=set()
        self.exchanges=[]

    def invoke(self,stage,doc,element_batch):
        batch=list(element_batch)
        try:self.count=reserve(self.count,len(batch))
        except BudgetStop:
            save(self.out/"budget-stop.json",dict(attempted=self.count,next_batch=len(batch)))
            raise
        if self.real:
            job=json.loads((self.out/"stage.json").read_text())["job"]
        else:job=doc.name
        dst=self.out/job
        dst.mkdir(parents=True,exist_ok=True)
        if job not in self.initial_docs:
            doc.save_as_json(dst/"pre-enrichment.json")
            (dst/"pre-enrichment.md").write_text(doc.export_to_markdown())
            self.initial_docs.add(job)
        self.batches+=1
        number=self.batches
        before=[el.item.model_dump(mode="json") for el in batch]
        images=[el.image for el in batch]
        engine=stage.engine
        original_predict=engine.predict_batch
        if self.real:
            import collections
            effective=collections.Counter((str(x.device),str(x.dtype)) for x in engine.vlm_model.parameters())
            assert all(device=="cpu" and dtype=="torch.float32" for device,dtype in effective),effective
            save(self.out/"loaded-engine.json",dict(parameter_tensor_counts={str(k):v for k,v in effective.items()},
                engine_options=engine.options.model_dump(mode="json"),model_config=engine.model_config.model_dump(mode="json")))
        def predict(inputs):
            assert len(inputs)==len(batch)
            requests=[]
            try:
                for i,(request,el) in enumerate(zip(inputs,batch)):
                    assert request.image is images[i]
                    image=request.image.convert("RGB")
                    image.save(dst/f"batch-{number}-input-{i}.png")
                    requests.append(dict(item_ref=el.item.self_ref,label=el.item.label,
                        image_size=image.size,pixel_sha256=__import__("hashlib").sha256(image.tobytes()).hexdigest(),
                        input=request.model_dump(mode="json",exclude={"image"})))
                save(dst/f"batch-{number}-request.json",requests)
            except Exception:
                save(self.out/"evidence-stop.json",dict(traceback=traceback.format_exc()))
                raise EvidenceStop()
            started=time.monotonic()
            try:
                outputs=original_predict(inputs)
            except Exception:
                save(dst/f"batch-{number}-engine-error.json",dict(traceback=traceback.format_exc(),seconds=time.monotonic()-started))
                raise
            try:
                save(dst/f"batch-{number}-raw.json",dict(outputs=[x.model_dump(mode="json") for x in outputs],seconds=time.monotonic()-started))
            except Exception:
                save(self.out/"evidence-stop.json",dict(traceback=traceback.format_exc()))
                raise EvidenceStop()
            self.exchanges.append(dict(job=job,batch=number,inputs=len(inputs)))
            return outputs
        engine.predict_batch=predict
        try:
            result=list(self.original_call(stage,doc,batch))
        finally:engine.predict_batch=original_predict
        save(dst/f"batch-{number}-items.json",dict(before=before,after=[x.model_dump(mode="json") for x in result]))
        save(self.out/"region-counts.json",dict(reserved_inputs=self.count,batches=self.batches,exchanges=self.exchanges))
        for el in result:yield el

def child():
    from docling.models.stages.code_formula.code_formula_vlm_model import CodeFormulaVlmModel
    original=CodeFormulaVlmModel.__call__
    observer=Observer(HERE/"E1",original)
    def observe(stage,doc,element_batch):
        yield from observer.invoke(stage,doc,element_batch)
    CodeFormulaVlmModel.__call__=observe
    try:base.child("E1")
    finally:CodeFormulaVlmModel.__call__=original

if __name__=="__main__":
    if sys.argv[1:]==["--child","E1"]:child()
    elif sys.argv[1:]==["--selfcheck"]:
        assert reserve(8,2)==10
        try:reserve(8,3)
        except BudgetStop:pass
        else:raise AssertionError("budget guard failed")
        assert reason(1801,0,180,0,20*2**30,"E1")=="model_stage_time_limit"
        print("budget/resource self-check passed; no model initialized")
    else:
        assert not sys.argv[1:]
        base.parent("E1")
        p=HERE/"E1/execution.json"
        record=json.loads(p.read_text())
        record.update(supervisor_sha256=sha(PREVIOUS/"run.py"),runner_sha256=sha(__file__))
        if (HERE/"E1/budget-stop.json").exists():record["status"]="budget_stop"
        if (HERE/"E1/evidence-stop.json").exists():record["status"]="evidence_stop"
        save(p,record)
