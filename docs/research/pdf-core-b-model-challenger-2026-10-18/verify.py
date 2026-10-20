"""Read-only verification of raw responses, public mapping and saved scoring."""
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    record=sys.argv[1:]==["--record"]
    if sys.argv[1:] not in ([],["--record"]):raise SystemExit("Use no args or --record once")
    runner=load("verify_challenger_runner",HERE/"run.py")
    evaluator=load("verify_challenger_evaluator",HERE/"evaluate.py")
    reg=runner.verify();read=runner.read
    p=runner.bridge.p
    execution=read(HERE/"live/execution.json")
    assert execution["ledger"]["calls"]==7 and execution["stopped"] is None
    assert read(HERE/"model-identity-check.json")["all_received_identities_match"]
    for job in reg["jobs"]:
        directory=HERE/"live"/job["name"]
        response=read(directory/"response.json")
        content=response["choices"][0]["message"]["content"]
        assert content==(directory/"content.txt").read_text()
        assert p.parse(p.loads(content),[job["target_key"]]).model_dump(mode="json")==read(directory/"output.json")
    for page in reg["pages"]:
        jobs=[j for j in reg["jobs"] if j["page_name"]==page["name"]]
        payload=dict(targets=[read(HERE/"live"/j["name"]/"output.json")["targets"][0] for j in jobs])
        baseline=runner.bridge.DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
        document,bindings=p.map_response(baseline,payload,page["page_no"],page["target_keys"])
        directory=HERE/"live"/page["name"]
        assert document.model_dump(mode="json")==read(directory/"document.json")
        assert bindings==read(directory/"bindings.json")
        assert p.adapter.export_markdown(document,bindings).encode("utf-8")== (directory/"document.md").read_bytes()
    summary=read(HERE/"evaluation.json")
    collateral=read(evaluator.B/"evaluator/collateral.json")
    for case,result in summary["cases"].items():
        evidence=read(HERE/(case+"-evaluation.json"))
        worksheet=(read(evaluator.B/"evaluator"/(case+".json")) if case.startswith("G1-") else
                   evaluator.collateral_worksheet(case,collateral[case]))
        actual=evaluator.score(worksheet,evidence["cells"],evidence["review"])
        assert all(actual[k]==result[k] for k in actual),case
    math=read(HERE/"table-math-evaluation.json")
    assert evaluator.score_math(math["observations"],math["explicit_source_decisions"])==math["result"]
    assert not summary["promoted"] and summary["cases"]["G1-T04"]["error_count"]==102
    assert not (HERE/"T03-live").exists(),"gate failed: no T03 inference allowed"
    key=os.environ.get("OPENAI_API_KEY","")
    assert key,"credential expected only for leak check; never written"
    for root in (HERE,evaluator.GATES):
        for path in root.rglob("*"):
            if path.is_file():assert key.encode() not in path.read_bytes(),"secret detected in new artifacts"
    if not record:
        for name,expected in read(HERE/"artifact-seal.json").items():
            assert sha256((HERE/name).read_bytes()).hexdigest()==expected,name
    result=dict(response_reparse=7,public_mapping_reproduced=5,case_scores_reproduced=6,
                math_review_score_reproduced=True,frozen_requests_sources_methods_valid=True,
                T03_not_run=True,credentials_not_in_new_artifacts=True,new_inference_calls=0)
    if record:runner.write(HERE/"verification.json",result)
    print(json.dumps(result))


if __name__=="__main__":main()
