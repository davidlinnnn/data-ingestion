"""Use the byte-identical frozen v3 scorer with read-only external inputs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
PREV=HERE.parent/"pdf-core-w2-native-coverage-round2-2026-10-20"
JOBS=json.loads((PREV/"jobs.json").read_text())["jobs"]
INDEX=json.loads((PREV/"oracle/job-index.json").read_text())


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def scorer(name, input_map=None):
    folder=HERE/"runs"/name
    if input_map is not None:
        folder.mkdir(parents=True,exist_ok=True)
        (folder/"jobs").mkdir(exist_ok=True)
        for jid,source in input_map.items():
            target=folder/"jobs"/jid
            if not target.exists():target.symlink_to(source,target_is_directory=True)
    (folder/"diagnostics").mkdir(exist_ok=True)
    geometry=folder/"diagnostics/geometry"
    if not geometry.exists():geometry.symlink_to(PREV/"diagnostics/geometry",target_is_directory=True)
    spec=importlib.util.spec_from_file_location("frozen_v3",PREV/"analyze_full.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.ROOT=folder;module.OUT=HERE/"analysis"/name
    return module


def evaluate(name,input_map=None, ids=None):
    m=scorer(name,input_map)
    summaries=[];catalog=[]
    for job in JOBS:
        if ids is not None and job["id"] not in ids:continue
        summary,candidates=m.score(job,Path(INDEX[job["id"]]))
        summaries.append(summary);catalog.extend(candidates)
    save(m.OUT/"summary.json",summaries);save(m.OUT/"candidate-catalog.json",catalog)
    save(m.OUT/"provenance.json",dict(analyzer_path=str(PREV/"analyze_full.py"),
        analyzer_sha256=hashlib.sha256((PREV/"analyze_full.py").read_bytes()).hexdigest(),
        source_oracle=str(PREV/"oracle"), source_geometry=str(PREV/"diagnostics/geometry"),
        source_code_modified=False,input_map=input_map))
    return summaries


def without_images(value):
    if isinstance(value,dict):return {k:without_images(v) for k,v in value.items() if k!="image"}
    if isinstance(value,list):return [without_images(v) for v in value]
    return value


def diffs(a,b,path=""):
    if type(a) is not type(b):return [dict(path=path,before=a,after=b)]
    if isinstance(a,dict):
        out=[]
        for key in sorted(a.keys()|b.keys()):
            if key not in a or key not in b:out.append(dict(path=path+"/"+key,before=a.get(key),after=b.get(key)))
            else:out.extend(diffs(a[key],b[key],path+"/"+key))
        return out
    if isinstance(a,list):
        if len(a)!=len(b):return [dict(path=path+"/length",before=len(a),after=len(b))]
        return [d for i,(x,y) in enumerate(zip(a,b)) for d in diffs(x,y,path+"/"+str(i))]
    return [] if a==b else [dict(path=path,before=a,after=b)]


def controls():
    name="controls-v1";ids=json.loads((HERE/"plans"/(name+".json")).read_text())["job_ids"]
    evaluate(name,ids=ids)
    cases=[]
    for jid in ids:
        old=PREV/"jobs"/jid;new=HERE/"runs"/name/"jobs"/jid
        olddoc=without_images(json.loads((old/"document.json").read_text()))
        newdoc=without_images(json.loads((new/"document.json").read_text()))
        dd=diffs(olddoc,newdoc)
        same_md=(old/"document.md").read_bytes()==(new/"document.md").read_bytes()
        checks={}
        for artifact in ("metrics.json","anchors.json","candidates.json","pages.json"):
            before=json.loads((PREV/"analysis"/jid/artifact).read_text())
            after=json.loads((HERE/"analysis"/name/jid/artifact).read_text())
            delta=diffs(before,after);checks[artifact]=dict(equal=not delta,differences=delta)
        cases.append(dict(id=jid,pages=next(j["last"]-j["first"]+1 for j in JOBS if j["id"]==jid),
            document_except_image_fields_equal=not dd,document_differences=dd,markdown_bytes_equal=same_md,
            w2_v3=checks,equivalent=not dd and same_md and all(c["equal"] for c in checks.values())))
    save(HERE/"controls-equivalence.json",dict(equivalent=all(c["equivalent"] for c in cases),
        run=name,excluded_fields="Only dictionary key named image, recursively; no text/label/structure/provenance omission",cases=cases))
    print(json.dumps({"equivalent":all(c["equivalent"] for c in cases),"cases":[{k:v for k,v in c.items() if k not in {"w2_v3","document_differences"}} for c in cases]},indent=2))


if __name__=="__main__":
    assert without_images({"image":1,"texts":[{"text":"a","image":2}]})=={"texts":[{"text":"a"}]}
    assert diffs({"x":1},{"x":2})==[{"path":"/x","before":1,"after":2}]
    if sys.argv[1:]==["controls"]:controls()
    elif len(sys.argv)==2:evaluate(sys.argv[1])
    else:raise SystemExit("controls or run-name")
