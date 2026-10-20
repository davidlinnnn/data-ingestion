"""One generic legal mock for every cached page target; no oracle/candidate answers."""
from pathlib import Path
import json,time
from datetime import datetime,timezone
from docling_core.types.doc import DoclingDocument,RefItem
import protocol as p
from controls import gate,HERE,sha,save

def main():
    reg=json.loads((HERE/"registration.json").read_text())
    assert datetime.now(timezone.utc)<datetime.fromisoformat(reg["deadline"])
    planning=json.loads((HERE/"next-stage-jobs.json").read_text());results=[]
    for page in planning["pages"]:
        started=time.monotonic()
        path=Path(page["baseline"]);before=sha(path)
        baseline=DoclingDocument.model_validate_json(path.read_text())
        keys=page["target_keys"]
        native=p.adapter.inventory(baseline,page["page_no"])
        excluded={n.self_ref for t in native.values() for n in gate.old.walk(baseline,t)}
        non_targets=[gate.source_signature(n,baseline) for n in gate.old.walk(baseline) if n.self_ref not in excluded]
        payload={"targets":[dict(target_key=k,caption="",conditions=["MOCK CONDITION"],diagnostics=[],panels=[dict(panel_label="",title="MOCK ONLY",data=dict(grid=[["Method","Score"],["MOCK *literal*","001.20"]],spans=[],roles=[dict(row=0,col=0,kind="column"),dict(row=0,col=1,kind="column"),dict(row=1,col=0,kind="row")],row_groups=[]))]) for k in keys]}
        doc,bindings=p.map_response(baseline,payload,page["page_no"],keys)
        changed={n.self_ref for b in bindings for n in gate.old.walk(doc,RefItem(cref=b["group_ref"]).resolve(doc))}
        checks={"all_page_targets_once":[b["target_key"] for b in bindings]==keys,"untouched_content_order_sources":[gate.source_signature(n,doc) for n in gate.old.walk(doc) if n.self_ref not in changed]==non_targets,"baseline_bytes_unchanged":sha(path)==before,"pages_origin_preserved":doc.pages==baseline.pages and doc.origin==baseline.origin}
        gate.old.assert_graph(doc)
        for b,source in zip(bindings,native.values(),strict=True):
            table=RefItem(cref=b["panels"][0]["table_ref"]).resolve(doc)
            checks[b["target_key"]+" provenance"]=(table.prov==source.prov and all(c.bbox is None for c in table.data.table_cells))
            checks[b["target_key"]+" caption ownership"]=[gate.old.signature(RefItem(cref=c).resolve(doc)) for c in b["captions"]]==[gate.old.signature(c.resolve(baseline)) for c in source.captions]
            checks[b["target_key"]+" conditions supplement exact"]=b["compact_provider"]["conditions"]==["MOCK CONDITION"]
        md=p.adapter.export_markdown(doc,bindings)
        tables,html=gate.rendered_tables(md)
        checks["actual_render_mock_literal_and_precision"]=sum(t==[["Method","Score"],["MOCK *literal*","001.20"]] for t in tables)==len(keys)
        loaded=DoclingDocument.model_validate_json(doc.model_dump_json())
        checks["JSON_reload_markdown_exact"]=p.adapter.export_markdown(loaded,json.loads(json.dumps(bindings)))==md
        dest=HERE/"source-mocks"/page["name"];dest.mkdir(parents=True,exist_ok=True)
        for name,value in (("input.json",payload),("document.json",doc.model_dump(mode="json")),("bindings.json",bindings)):(dest/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
        (dest/"document.md").write_text(md);(dest/"rendered.html").write_text(html)
        results.append(dict(page=page["name"],status="pass" if all(checks.values()) else "fail",checks=checks,seconds=time.monotonic()-started,native_targets=len(keys),data="generic mock; no numeric accuracy assertion"))
    save("source-mock-results.json",dict(status="pass" if all(r["status"]=="pass" for r in results) else "fail",pages=results,new_model_calls=0,notes="conditions preserved in exact same-version bindings; outside-caption/body source ownership remains baseline. Generic MOCK contents are deliberately unrelated to source accuracy."))
    print(json.dumps({r["page"]:r["status"] for r in results},indent=2))
if __name__=="__main__":main()
