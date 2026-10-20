"""Post-inference source evaluation; never imported by the producer."""
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument, RefItem
from mapper import recover_provider_from_cells
from verify import assert_graph, markdown_tables, signature, walk

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    registry=json.loads((ROOT/'docs/fixtures/pdf-core-g1-2026-10-14/cases.json').read_text())
    cases={c['id']:c['details'] for c in registry['cases']}
    spec=importlib.util.spec_from_file_location('legacy',ROOT/'docs/research/pdf-core-g2-api-2026-10-14/review/evaluate.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    registered=json.loads((HERE/'live-registration.json').read_text())
    summaries=[]
    for job in registered['jobs']:
        dest=HERE/job['name'];baseline=DoclingDocument.model_validate_json(Path(job['baseline']).read_text())
        doc=DoclingDocument.model_validate_json((dest/'document.json').read_text())
        assert_graph(doc)
        bindings=json.loads((dest/'bindings.json').read_text())
        expected_skip=set()
        for t in baseline.tables:
            expected_skip.update(n.self_ref for n in walk(baseline,t))
        actual_skip=set()
        for b in bindings:
            actual_skip.update(n.self_ref for n in walk(doc,RefItem(cref=b['group_ref']).resolve(doc)))
        assert [signature(n) for n in walk(baseline) if n.self_ref not in expected_skip]==[signature(n) for n in walk(doc) if n.self_ref not in actual_skip]
        assert doc.origin==baseline.origin and doc.pages==baseline.pages
        text=(dest/'document.md').read_text();assert text==doc.export_to_markdown()
        rendered=markdown_tables(text)
        cursor=0
        recovered=[]
        for b,t in zip(bindings,baseline.tables,strict=True):
            native_caption=[signature(r.resolve(baseline)) for r in t.captions]
            actual_caption=[signature(RefItem(cref=r).resolve(doc)) for r in b['captions']]
            assert actual_caption==native_caption
            for cap in actual_caption: assert text.count(cap['text'])==1
            for panel,refs in zip(b['provider']['panels'],b['panels'],strict=True):
                item=RefItem(cref=refs['table_ref']).resolve(doc)
                assert rendered[cursor]==[[c.text for c in row] for row in item.data.grid]
                assert RefItem(cref=refs['title_ref']).resolve(doc).text==' '.join(s for s in (panel['panel_label'],panel['title']) if s)
                assert item.prov==t.prov and all(c.bbox is None for c in item.data.table_cells)
                cursor+=1
            reconstructed=recover_provider_from_cells(doc,b)
            assert reconstructed['panels']==b['provider']['panels']
            recovered.append(reconstructed)
        assert cursor==len(rendered)
        if job['name']=='skillopt-p8':
            quality=old.evaluate_table(recovered[0],cases['G1-T02'])
            assert quality['source_numeric_bindings_correct']==quality['printed_numeric_strings_exact']==84
            assert quality['all_critical_numeric_bindings_preserved'] and quality['extra_numeric_observations']==0
            score={'correct_numeric_bindings':84,'critical_comparisons':8,'error_rate':quality['error_rate_including_unmatched_extras'],'panel_header_issues':quality['panel_header_issues']}
            (dest/'typed-quality.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2)+'\n')
            rows=recovered[1]['panels'][0]['rows']
            assert len(rows)==8 and sum(len(r['values']) for r in rows)==24
            score['collateral_table3']={'rows':8,'numeric_values':24,'scope':'all24values manually compared to saved full-page source; original column dimensions merged into setting strings'}
        else:
            oracle=cases['G1-T01'];panel=recovered[0]['panels'][0]
            rows={r['context']['method']:r['row_id'] for r in oracle['rows']}
            headers={h['raw_text']:h['key'] for h in oracle['headers']}
            assert len(panel['rows'])==len(rows) and len({r['setting'] for r in panel['rows']})==len(rows)
            actual={(rows[row['setting']],headers[v['column']]):v['value'] for row in panel['rows'] for v in row['values']}
            assert sum(len(row['values']) for row in panel['rows'])==len(actual), 'duplicate ordinary-table bindings'
            accepted={p['id']:actual[(p['row_id'],p['column_key'])] == p['raw_value'] for p in oracle['expected_datapoints']}
            assert all(accepted.values()) and len(actual)==6
            points={p['id']:Decimal(actual[(p['row_id'],p['column_key'])]) for p in oracle['expected_datapoints']}
            assert all(points[c['left']]>points[c['right']] for c in oracle['critical_comparisons'])
            score={'correct_numeric_bindings':6,'critical_comparisons':3,'printed_metrics':panel['columns']}
        score.update(name=job['name'],non_target_items_unchanged=True,native_captions_preserved_once=True,
            public_tree_and_references_valid=True,json_reload_and_markdown_grid_exact=True,
            omitted_literal_row_dimension_headers=['Method'] if job['name']=='memory-r1-p8' else ['Setting','Component (Table3)'],
            geometry='native table envelope only; no per-panel or per-cell localization',
            verdict='numeric/relationship delivery passes; literal row-dimension headers absent in frozen protocol; not complete source-fidelity qualification')
        summaries.append(score)
        (dest/'evidence.json').write_text(json.dumps({k:job[k] for k in ('name','baseline','baseline_sha256','image','image_sha256','http_body_sha256','targets')},indent=2)+'\n')
    (HERE/'live-evaluation.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summaries,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
