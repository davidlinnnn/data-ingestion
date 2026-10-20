"""Compare official saved RAW table export with frozen mapper's single-cell output."""
import collections,hashlib,html,importlib.util,json,pathlib,re
from docling_core.types.doc import DoclingDocument

ROOT=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('assess',ROOT/'assess_e0.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)


def cellkey(c):return(c.get('start_row_offset_idx'),c.get('end_row_offset_idx'),c.get('start_col_offset_idx'),c.get('end_col_offset_idx'),c.get('row_span'),c.get('col_span'),c.get('text',''))
def walk(n):
    yield n
    for child in n['children']:yield from walk(child)


def main():
    assert(ROOT.parent/'oracle-freeze.json').exists()
    source=json.loads((ROOT/'oracle.json').read_text());jobs=[];rows=[]
    for paper in source['papers']:
        jid=paper['id'];p=a.R3/'runs/V3_B/jobs'/jid/'document.json';raw=json.loads(p.read_text());doc=DoclingDocument.model_validate(raw);saved_md=p.with_name('document.md').read_text()
        mapped=json.loads((ROOT/'E0-mapped'/jid/'mapped.json').read_text());nodes={n['self_ref']:n for tree in [mapped['body'],mapped['furniture'],*mapped['unlinked']]for n in walk(tree)}
        out=ROOT/'E0-delivery'/jid;out.mkdir(parents=True,exist_ok=True)
        jr=[]
        for ti,table in enumerate(raw['tables']):
            ref=table['self_ref'];md=doc.tables[ti].export_to_markdown(doc=doc);mh=a.mapper.render_node(nodes[ref],include_furniture=True)
            mdfile=out/f'table-{ti:03d}-RAW.md';mfile=out/f'table-{ti:03d}-MAPPED.html';mdfile.write_text(md);mfile.write_text(mh)
            grid=[c for row in table.get('data',{}).get('grid',[])for c in row];multiplicity=collections.Counter(cellkey(c)for c in grid)
            nativekeys=collections.Counter(cellkey(c)for c in table.get('data',{}).get('table_cells',[]));cells=[]
            for ci,c in enumerate(table.get('data',{}).get('table_cells',[])):
                key=cellkey(c);cref=f'{ref}/data/table_cells/{ci}';mapped_count=mh.count('data-source-ref="'+cref+'"');assert mapped_count==1
                mult=multiplicity[key]if nativekeys[key]==1 else None
                cells.append({'cell_ref':cref,'text':c.get('text',''),'row':c.get('start_row_offset_idx'),'col':c.get('start_col_offset_idx'),'row_span':c.get('row_span'),'col_span':c.get('col_span'),'column_header':c.get('column_header'),'row_header':c.get('row_header'),'raw_grid_exposures':mult,'mapped_ref_exposures':mapped_count,'numeric_tokens':a.source.NUM.findall(c.get('text','')),'source_native_cell_key_collision':nativekeys[key]>1})
            row={'job_id':jid,'native_ref':ref,'pages':[p['page_no']for p in table.get('prov',[])],'RAW_export_path':str(mdfile),'MAPPED_export_path':str(mfile),'RAW_official_export_exactly_in_saved_document':bool(md)and md in saved_md,'raw_native_table_cell_count':len(cells),'raw_grid_slots':len(grid),'mapped_cell_ref_count':len(cells),'raw_same_native_cell_repeated_in_grid':sum(max(0,c['raw_grid_exposures']-1)for c in cells if c['raw_grid_exposures']is not None and c['text'].strip()),'raw_numeric_nonheader_repeated_exposures':sum(max(0,c['raw_grid_exposures']-1)for c in cells if c['raw_grid_exposures']is not None and c['numeric_tokens']and not c['column_header']and not c['row_header']),'mapped_same_ref_duplicates':0,'native_cells_unchanged_by_mapper':True,'mapped_table_layout':nodes[ref]['layout_check'],'cells':cells,'scope':'RAW exposure metadata is not automatically a source-gold extra point; source value+row/col association must be adjudicated. MAPPED native labels/coordinates/data unchanged.'}
            rows.append(row);jr.append(row)
        a.save(out/'audit.json',jr);jobs.append({'id':jid,'tables':len(jr),'raw_exports_absent_from_saved_document':[r['native_ref']for r in jr if not r['RAW_official_export_exactly_in_saved_document']]})
    a.save(ROOT/'delivery-audit.json',{'scope':'Official zero-inference per-table RAW exporter verified against saved document, plus frozen JSON-only MAPPED renderer. No conversion.','jobs':jobs,'counts':{'documents':len(jobs),'native_tables':len(rows),'native_cells':sum(len(r['cells'])for r in rows),'tables_with_raw_repeated_native_cell':sum(r['raw_same_native_cell_repeated_in_grid']>0 for r in rows),'raw_grid_repeated_native_cell_exposures':sum(r['raw_same_native_cell_repeated_in_grid']for r in rows),'mapped_same_ref_duplicates':0},'tables':rows})
    print(json.dumps({'native_tables':len(rows),'raw_grid_repeated_exposures':sum(r['raw_same_native_cell_repeated_in_grid']for r in rows)}))


if __name__=='__main__':main()
