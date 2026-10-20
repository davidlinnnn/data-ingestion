"""Conservative analysis-only extent guard; never alters source or human labels."""
import collections
import json
import re
from pathlib import Path

P=Path(__file__).resolve().parent


def main():
    path=P/'per-unit.json';records=json.loads(path.read_text())
    reviews=json.loads((P.parents[1]/'pdf-core-w3-structured-elements-2026-10-20/formula-code/audit/code-review.json').read_text())['records']
    reviews={r['unit_id']:r for r in reviews}
    for filename in ['per-unit.json','summary.json','report.md','inventory.json']:
        src=P/filename;dest=P/(src.stem+'.v2-pre-extent-guard'+src.suffix)
        if src.exists() and not dest.exists():dest.write_bytes(src.read_bytes())
    refs=collections.defaultdict(list)
    for row in records:
        for ref in row['fixed_refs']:refs[row['job_id'],ref].append(row['unit_id'])
    for row in records:
        shared={ref:refs[row['job_id'],ref] for ref in row['fixed_refs'] if len(refs[row['job_id'],ref])>1}
        row['shared_ref_source_units']=shared
        review=reviews.get(row['unit_id']);identity=review.get('identity_reason','') if review else ''
        note=identity+' '+review.get('meaning_reason','') if review else ''
        baseline_superset=bool(re.search(r'shared superset|shared refs|shared/ref|前一.*尾部',identity,re.I))
        variant_neighbors=bool(re.search(r'E1[^。]*(?:鄰|夾入|頁首|截斷|下章|下一)',note))
        row['boundary_guard']={'policy':'All99 reverse source/ref graph; independent boundary evidence required; manual superset/neighbor evidence is exclusion, never gold text slicing.',
                               'shared_ref':bool(shared),'manual_baseline_superset':baseline_superset,
                               'manual_E1_neighbor_fragments':variant_neighbors,
                               'independent_human_identity':review is not None,
                               'human_label_unchanged':True}
        for channel,entry in row['channels'].items():
            if not entry.get('primary_CER_eligible'):continue
            cause=None
            if shared or baseline_superset:cause='MANY_TO_ONE_BOUNDARY_UNRESOLVED'
            elif not review:cause='BOUNDARY_NOT_INDEPENDENTLY_VERIFIED'
            elif channel.startswith('E1') and variant_neighbors:cause='E1_SOURCE_UNIT_BOUNDARY_UNRESOLVED_NEIGHBOR_FRAGMENTS'
            if cause:
                entry['pre_boundary_guard_status']=entry['status'];entry['status']=cause
                entry['primary_CER_eligible']=False
                entry['whole_item_diagnostic_metrics']=entry.pop('metrics')
                entry['diagnostic_not_independent_unit_error']=True
        row['tri_source_comparable']=all(row['channels'][c]['status']=='COMPARABLE_FIXED_SOURCE_REGION' for c in ['native','E0_RAW','E1_RAW'])
    path.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    summary=json.loads((P/'summary.json').read_text())
    summary['channels']={}
    import statistics
    for c in ['native','E0_RAW','E0_MAPPED','E1_RAW','E1_MAPPED']:
        valid=[r['channels'][c]['metrics']['raw']['CER'] for r in records if r['channels'][c].get('primary_CER_eligible')]
        summary['channels'][c]={'status_counts':dict(collections.Counter(r['channels'][c]['status'] for r in records)),
                               'primary_CER_units':len(valid),'CER_p50':statistics.median(valid) if valid else None,
                               'CER_max':max(valid) if valid else None,'not_semantic_error_rate':True}
    summary['tri_source_comparable']=sum(r['tri_source_comparable'] for r in records)
    summary['manual21_tri_source_comparable']=sum(r['tri_source_comparable'] for r in records if r['manual_21_subset'])
    summary['extent_guard_applied_to_all_99']=True
    summary['human_source_identity_usable_17_is_not_boundary_comparable_17']=True
    (P/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print({c:summary['channels'][c]['primary_CER_units'] for c in summary['channels']})


if __name__=='__main__':main()
