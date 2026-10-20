"""Offline synthetic protocol/real public Core controls. Never runs inference."""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
import json,sys,time
import protocol as p
from docling_core.types.doc import (DoclingDocument,RefItem,TableData,TableCell,
    DocItemLabel,PageItem,Size,BoundingBox,ProvenanceItem)
HERE=Path(__file__).resolve().parent
RESEARCH=HERE.parents[1]
sys.path.insert(0,str(RESEARCH/"pdf-core-direct-cell-2026-10-17"))
gate=p.load("stage1_old_gate",RESEARCH/"pdf-core-direct-cell-2026-10-17/gate.py")
sys.path.pop(0)

def sha(path): return sha256(Path(path).read_bytes()).hexdigest()
def save(name,value): (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
def compact(old):
    result=deepcopy(old)
    for target in result["targets"]:
        target["diagnostics"]=target.pop("uncertainties")
        for panel in target["panels"]:
            source=panel["data"]
            grid=[[None]*source["num_cols"] for _ in range(source["num_rows"])]
            spans=[];roles=[];sections=[]
            for cell in source["table_cells"]:
                r,c=cell["start_row_offset_idx"],cell["start_col_offset_idx"]
                grid[r][c]=cell["text"]
                if (cell["row_span"],cell["col_span"])!=(1,1):
                    spans.append(dict(row=r,col=c,rows=cell["row_span"],cols=cell["col_span"]))
                role=("section" if cell["row_section"] else "corner" if cell["column_header"] and cell["row_header"] else "column" if cell["column_header"] else "row" if cell["row_header"] else None)
                if role: roles.append(dict(row=r,col=c,kind=role))
                if role=="section": sections.append((r,c))
            groups=[dict(start=r,end=sections[i+1][0] if i+1<len(sections) else len(grid),label_row=r,label_col=c) for i,(r,c) in enumerate(sections)]
            panel["data"]=dict(grid=grid,spans=spans,roles=roles,row_groups=groups)
    return result

def main():
    checks={};errors={};began=time.monotonic()
    def check(name,fn):
        try:
            value=fn()
            if value is False: raise AssertionError("predicate returned false")
            checks[name]=True
        except Exception as exc:
            checks[name]=False;errors[name]=repr(exc)
    reg=json.loads((HERE/"registration.json").read_text())
    assert datetime.now(timezone.utc)<datetime.fromisoformat(reg["deadline"])
    runtime={name:version(name) for name in ("docling-slim","docling-core","docling-parse","pydantic","markdown-it-py")}
    assert [runtime[n] for n in ("docling-slim","docling-core","docling-parse")]==["2.132.0","2.99.0","7.22.3"]
    method_files=[Path(__file__),HERE/"protocol.py",RESEARCH/"pdf-core-direct-cell-2026-10-17/adapter.py",RESEARCH/"pdf-core-direct-cell-2026-10-17/gate.py",RESEARCH/"pdf-core-caption-ownership-2026-10-17/policy.py",RESEARCH/"pdf-core-table-delivery-2026-10-17/mapper.py"]
    method_hashes={str(f):sha(f) for f in method_files}
    reg.update(runtime=runtime,method_hashes=method_hashes,schema_policy="Strict extra=forbid at every level; diagnostics separate from required table content; no field relocation. Empty string=known blank, literal dash=printed missing mark, null=covered only, {unknown:true}=unresolved and blocks delivery.",scope="Synthetic protocol plus pinned Core controls; historical cached source compatibility; no accuracy assessment",production_or_sdk_modified=False)
    save("registration.json",reg)
    save("schema.json",p.Response.model_json_schema())
    doc,keys,old,literals=gate.fixture()
    payload=compact(old)
    save("synthetic-input.json",payload)
    save("baseline.json",doc.model_dump(mode="json"))
    parsed=p.parse(payload,keys)
    check("compact physical cells equal original synthetic public fields",lambda: all(panel.data.data()==legacy["data"] for target,src in zip(parsed.targets,old["targets"],strict=True) for panel,legacy in zip(target.panels,src["panels"],strict=True)))
    baseline_snapshot=doc.model_dump_json()
    native=p.adapter.inventory(doc,1)
    excluded={n.self_ref for target in native.values() for n in gate.old.walk(doc,target)}
    untouched=[gate.source_signature(n,doc) for n in gate.old.walk(doc) if n.self_ref not in excluded]
    out,bindings=p.map_response(doc,payload,1,keys)
    save("document.json",out.model_dump(mode="json"));save("bindings.json",bindings)
    serialized=p.adapter.serialize(out,bindings);md=serialized.text
    (HERE/"document.md").write_text(md)
    tables,html=gate.rendered_tables(md);(HERE/"rendered.html").write_text(html)
    check("public graph references valid",lambda: gate.old.assert_graph(out))
    check("baseline immutable",lambda: doc.model_dump_json()==baseline_snapshot)
    changed={n.self_ref for b in bindings for n in gate.old.walk(out,RefItem(cref=b["group_ref"]).resolve(out))}
    check("non-target text and rich table content provenance order unchanged",lambda: [gate.source_signature(n,out) for n in gate.old.walk(out) if n.self_ref not in changed]==untouched)
    check("pages origin furniture unchanged",lambda: (out.pages,out.origin,out.furniture)==(doc.pages,doc.origin,doc.furniture))
    for i,(binding,target,source) in enumerate(zip(bindings,parsed.targets,native.values(),strict=True)):
        for j,(panel,refs) in enumerate(zip(target.panels,binding["panels"],strict=True)):
            table=RefItem(cref=refs["table_ref"]).resolve(out)
            check(f"target{i} panel{j} exact public TableData",lambda table=table,panel=panel: table.data.model_dump(include={"num_rows","num_cols","table_cells"})==TableData.model_validate(panel.data.data()).model_dump(include={"num_rows","num_cols","table_cells"}))
            check(f"target{i} panel{j} provenance and no invented bbox",lambda table=table,source=source: table.prov==source.prov and all(c.bbox is None for c in table.data.table_cells))
        check(f"target{i} compact provider exact",lambda binding=binding,target=target: binding["compact_provider"]==target.model_dump(mode="json"))
    check("literal true Markdown render preserves text no HTML activation",lambda: tables[0]==[["Method","Value"]]+[[f"Literal {i}"," ".join(t.splitlines())] for i,t in enumerate(literals,1)])
    expected_complex=[["Method","Setting","A - Score","A - Spread","B - Score","B - Spread"],["Group alpha"]*6,["Method X","Setting one","001.20","0","","1.2 ± 0.3"],["Method X","Setting two","—","-0.0","1e-3","10 / 20"],["Group beta"]*6,["Method Y","Setting three","9","0.00","8","2.0 ± 0.4"]]
    check("two dimensions multilevel same metric spans rowgroups paired precision rendered",lambda: tables[1]==expected_complex)
    check("non-target table true rendered unchanged",lambda: tables[2]==gate.rendered_tables(doc.export_to_markdown())[0][-1])
    check("source captions exactly once in original order",lambda: all(md.count(f"Synthetic source caption {i}")==1 for i in (1,2)) and md.index("Body before target tables")<md.index("Synthetic source caption 1")<md.index("Body after target 1")<md.index("Synthetic source caption 2")<md.index("Body after target 2"))
    check("serializer spans resolve to original canonical items",lambda: all(s.item.model_dump_json()==s.item.get_ref().resolve(out).model_dump_json() for s in serialized.spans))
    loaded=DoclingDocument.model_validate_json((HERE/"document.json").read_text());loaded_bindings=json.loads((HERE/"bindings.json").read_text())
    check("JSON reload canonical exact",lambda: loaded.model_dump(mode="json")==out.model_dump(mode="json"))
    check("JSON reload true Markdown exact",lambda: p.adapter.export_markdown(loaded,loaded_bindings)==md)
    check("explicit rowgroup scopes persist supplement",lambda: loaded_bindings[1]["compact_provider"]["panels"][0]["data"]["row_groups"]==[{"start":2,"end":5,"label_row":2,"label_col":0},{"start":5,"end":7,"label_row":5,"label_col":0}])
    # More than one panel exercises the existing owner/ref mechanics without a new graph path.
    panels=deepcopy(payload);panels["targets"][0]["panels"].append(deepcopy(panels["targets"][0]["panels"][0]))
    panels["targets"][0]["panels"][1].update(panel_label="Panel B",title="literal *title*")
    pan_doc,pan_bind=p.map_response(doc,panels,1,keys)
    save("two-panel-document.json",pan_doc.model_dump(mode="json"));save("two-panel-bindings.json",pan_bind)
    check("multiple panel identity and caption once",lambda: len(pan_bind[0]["panels"])==2 and p.adapter.export_markdown(pan_doc,pan_bind).count("Synthetic source caption 1")==1 and RefItem(cref=pan_bind[0]["panels"][1]["title_ref"]).resolve(pan_doc).text=="Panel B literal *title*")
    negatives=[]
    def negative(name,change,mapper=False):
        bad=deepcopy(payload);change(bad)
        try:
            (p.map_response(doc,bad,1,keys) if mapper else p.parse(bad,keys))
            negatives.append(dict(name=name,rejected=False))
        except (ValueError,TypeError) as exc:
            negatives.append(dict(name=name,rejected=True,error=str(exc)))
    def grid(v):return v["targets"][1]["panels"][0]["data"]
    negative("nonrectangular",lambda v:grid(v)["grid"][0].append("x"))
    negative("span overlap",lambda v:grid(v)["spans"].append(deepcopy(grid(v)["spans"][0])))
    negative("span out of bounds",lambda v:grid(v)["spans"][0].update(rows=999))
    negative("zero span",lambda v:grid(v)["spans"][0].update(rows=0))
    negative("covered slot contradicts anchor",lambda v:grid(v)["grid"][1].__setitem__(0,"duplicate"))
    negative("null anchor",lambda v:grid(v)["grid"][0].__setitem__(0,None))
    negative("unowned null",lambda v:grid(v)["grid"][3].__setitem__(2,None))
    negative("duplicate role",lambda v:grid(v)["roles"].append(deepcopy(grid(v)["roles"][0])))
    negative("role on covered cell",lambda v:grid(v)["roles"].append(dict(row=1,col=0,kind="column")))
    negative("role outside grid",lambda v:grid(v)["roles"].append(dict(row=999,col=0,kind="row")))
    negative("unknown role",lambda v:grid(v)["roles"][0].update(kind="guessed"))
    negative("missing section scope",lambda v:grid(v)["row_groups"].pop())
    negative("group overlap",lambda v:grid(v)["row_groups"][0].update(end=6))
    negative("scope outside grid",lambda v:grid(v)["row_groups"][1].update(end=99))
    negative("scope wrong label",lambda v:grid(v)["row_groups"][0].update(label_col=1))
    negative("group order",lambda v:grid(v)["row_groups"].reverse())
    negative("illegal header scope",lambda v:grid(v)["roles"].append(dict(row=4,col=5,kind="column")))
    negative("unknown root field",lambda v:v.update(uncertainties=[]))
    negative("diagnostics at wrong level",lambda v:grid(v).update(diagnostics=[]))
    negative("unknown cell field",lambda v:grid(v)["spans"][0].update(bbox=[0,0,1,1]))
    negative("numeric cell coercion",lambda v:grid(v)["grid"][3].__setitem__(2,1.2))
    negative("boolean span coercion",lambda v:grid(v)["spans"][0].update(rows=True))
    negative("missing target",lambda v:v["targets"].pop())
    negative("duplicate target",lambda v:v["targets"].append(deepcopy(v["targets"][0])))
    negative("unknown target",lambda v:v["targets"][0].update(target_key="foreign"))
    negative("missing required content",lambda v:grid(v).pop("grid"))
    negative("provider caption reconstruction forbidden",lambda v:v["targets"][0].update(caption="guessed"))
    negative("unknown distinct from blank blocks complete delivery",lambda v:grid(v)["grid"][3].__setitem__(2,{"unknown":True}),True)
    for value in ("",json.dumps(payload)[:-1]):
        try: json.loads(value);rejected=False
        except json.JSONDecodeError: rejected=True
        negatives.append(dict(name="empty/truncated raw JSON",rejected=rejected))
    check("all negative controls reject",lambda: all(n["rejected"] for n in negatives))
    unknown=deepcopy(payload);grid(unknown)["grid"][3][2]={"unknown":True}
    check("unknown sentinel distinct and syntactically retained",lambda: p.parse(unknown,keys).targets[1].panels[0].data.grid[3][2].unknown is True)
    diagnostics=deepcopy(payload);diagnostics["targets"][0]["diagnostics"]=["source is ambiguous"]
    check("diagnostics preserved without relocation",lambda: p.parse(diagnostics,keys).targets[0].diagnostics==["source is ambiguous"])
    # Structural legality is independent of oracle shape/values.
    legal=deepcopy(payload);legal["targets"][0]["panels"][0]["data"]["grid"].append(["unseen valid row","999"])
    check("valid extra row not compared against oracle",lambda: p.parse(legal,keys).targets[0].panels[0].data.grid[-1]==["unseen valid row","999"])
    multipage=DoclingDocument(name="synthetic logical table two fragments")
    for num in (1,2):multipage.pages[num]=PageItem(page_no=num,size=Size(width=100,height=100))
    cells=[TableCell(**gate.cell(text,r,c,header=r in (0,2))) for r,row in enumerate([["Method","Score"],["A","1.20"],["Method","Score"],["B","2.50"]]) for c,text in enumerate(row)]
    table=multipage.add_table(data=TableData(num_rows=4,num_cols=2,table_cells=cells))
    table.prov=[ProvenanceItem(page_no=num,bbox=BoundingBox(l=1,t=1,r=99,b=99),charspan=(0,0)) for num in (1,2)]
    save("multipage-public-core.json",multipage.model_dump(mode="json"));(HERE/"multipage-public-core.md").write_text(multipage.export_to_markdown())
    multi_reload=DoclingDocument.model_validate_json((HERE/"multipage-public-core.json").read_text())
    direct_checks={"one_logical_item":len(multi_reload.tables)==1,"source_fragment_order":[v.page_no for v in multi_reload.tables[0].prov]==[1,2],"repeated_header_rows_exact":multi_reload.tables[0].data==table.data,"no_cell_bbox":all(c.bbox is None for c in table.data.table_cells)}
    try:p.adapter.inventory(multipage,1); multi_error=None
    except ValueError as exc:multi_error=str(exc)
    save("multipage-result.json",dict(public_core_checks=direct_checks,mapper_status="fail" if multi_error else "pass",error=multi_error,interpretation="Core stores a single logical item and ordered provenance; existing page mapper rejects it. No repair, merge or new renderer added."))
    check("multipage mapper fails explicitly without source mutation",lambda: multi_error is not None and "multi-page" in multi_error and all(direct_checks.values()))
    save("negative-results.json",negatives)
    save("results.json",dict(status="partial",single_page_gate="pass" if all(checks.values()) else "fail",multipage_gate="fail" if multi_error else "pass",checks=checks,errors=errors,negative_count=len(negatives),runtime=runtime,synthetic_only=True,model_calls=0,api_requests=0,model_loads=0,holdout_reads=0,elapsed_control_seconds=time.monotonic()-began,method_hashes=method_hashes))
    print(json.dumps(dict(checks=checks,errors=errors,negative_count=len(negatives),multipage_error=multi_error),indent=2))

if __name__=="__main__":main()
