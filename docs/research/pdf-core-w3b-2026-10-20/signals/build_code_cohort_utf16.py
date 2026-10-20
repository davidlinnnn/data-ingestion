"""BEGIN5 only: retain original 21 labels; primary a uses PDF glyph evidence."""
import collections
import hashlib
import importlib.util
import json
from pathlib import Path

P=Path(__file__).resolve().parent
BASE=P.parent
W3=BASE.parent/'pdf-core-w3-structured-elements-2026-10-20/formula-code'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())


def main():
    helper=P/'character_helpers.py'
    spec=importlib.util.spec_from_file_location('pinned_code_character_helper',helper)
    method=importlib.util.module_from_spec(spec);spec.loader.exec_module(method)
    amendment=load(BASE/'signals-character-method-bug-amendment-xml.json')
    assert sha(helper)==amendment['helpers_sha256']['character_helpers.py']
    human_path=W3/'audit/code-review.json';humans=load(human_path)['records']
    assert len(humans)==21
    analysis_path=BASE/'code-native-v4-utf16/per-unit.json';analysis={r['unit_id']:r for r in load(analysis_path)}
    inputs_path=W3/'e1-input-hashes.json';actual=load(inputs_path)
    manifest_path=BASE/'html-manifest.json';pdfs={j['job_id']:j for j in load(manifest_path)['jobs']}
    rows=[];page_sizes={}
    for index,human in enumerate(humans):
        uid=human['unit_id'];job=human['job_id'];stage4=analysis[uid]
        status=human['status'];eligible=status in ['CONFIRMED_MEANING_PRESERVED','CONFIRMED_BLOCKING']
        error=True if status=='CONFIRMED_BLOCKING' else False if status=='CONFIRMED_MEANING_PRESERVED' else None
        native_info=stage4.get('native_evidence');native=load(native_info['path']) if native_info else None
        target=human['E1_channels']['MAPPED']['delivered_text']
        assert target==human['E1_channels']['RAW']['delivered_text']
        e1_folder=Path(actual[job]['folder']);document=e1_folder/'document.json'
        artifact_sha=actual[job]['document_sha256'];assert sha(document)==artifact_sha
        if job not in page_sizes:
            page_sizes[job]={int(n):[p['size']['width'],p['size']['height']] for n,p in load(document)['pages'].items()}
        predicted_refs=human['actual_E1_processed_refs']
        full_refs=human['fixed_E0_refs']
        group_material={'model':'docling-project/CodeFormulaV2','artifact_sha256':artifact_sha,'predicted_refs':sorted(predicted_refs)}
        group='CodeFormulaV2:'+hashlib.sha256(json.dumps(group_material,sort_keys=True).encode()).hexdigest()
        boundary_status=stage4['channels']['E1_MAPPED']['status']
        scope_compatible=boundary_status=='COMPARABLE_FIXED_SOURCE_REGION'
        reasons=[]
        if not scope_compatible:reasons.append(boundary_status)
        if status=='ORACLE_ALIGNMENT_ERROR':reasons.append('Original human source/native alignment error; target extent not independently matched.')
        if not native:reasons.append('No complete source-aligned original-PDF glyph region.')
        regions=[]
        if native:
            for region in native['regions']:
                regions.append({'page':region['page'],'bbox':region['bbox'],'bbox_origin':'BOTTOMLEFT',
                                'page_dimensions':page_sizes[job].get(region['page']),'native_refs':[region['ref']],
                                'source_identity':uid,'crop_sha256':None})
        mixed=[{'ref':ref,'actually_enriched':ref in predicted_refs,
                'copied_native_or_orig_fallback':ref not in predicted_refs} for ref in full_refs]
        channel='MIXED_FALLBACK' if any(not r['actually_enriched'] for r in mixed) else 'MAPPED'
        a={'status':'UNKNOWN','pass':None,'character_similarity':None,'distance':None,
           'left_chars':None,'right_chars':None,'operator_sequence_exact':None,
           'number_sequence_exact':None,'unknown_reasons':list(reasons),
           'evidence_paths':[native_info['path']] if native_info else []}
        if native and scope_compatible:
            print('agreement',index+1,uid,len(native['text']),len(target),flush=True)
            a.update(method.agreement(native['text'],target,'code'))
            a['unknown_reasons']=[]
            a['evidence_kind']='ORIGINAL_PDF_CHAR_LAYER_WITH_X_RECONSTRUCTED_SPACES'
        row={'row_id':'W3_CODE21:'+uid,'original_unit_id':uid,'cohort':'W3_CODE21','category':'code',
             'unit_scope':'SOURCE_CODE_UNIT','model':'docling-project/CodeFormulaV2',
             'model_checkpoint_revision':None,'human_status':status,'human_error':error,
             'primary_label_eligible':eligible,
             'human_label_evidence':{'path':str(human_path),'sha256':sha(human_path),'record_locator':uid,
                                     'scope_note':human['scope']+'; original source-unit semantic label, not full shared prediction item label.'},
             'pdf_sha256':pdfs[job]['pdf_sha256'],'original_pages':human['source_pages'],
             'refs':full_refs,
             'source_identity':{'kind':'FROZEN_SOURCE_UNIT','value':uid,
                                'evidence_paths':[str(human_path)],
                                'visually_verified_source_identity':human['reviewed_visual'] and status!='ORACLE_ALIGNMENT_ERROR'},
             'regions':regions,
             'native_evidence':{'status':'AVAILABLE' if native else 'UNKNOWN',
                                'kind':'ALIGNED_TEXT_LAYER_GLYPHS' if native else 'NONE',
                                'visible_text':native['text'] if native else None,
                                'path':native_info['path'] if native_info else None,
                                'sha256':native_info['sha256'] if native_info else None,
                                'locator':'Original PDF glyph centers in fixed native provenance bbox union; raw_index and actual tight/loose char bbox stored.',
                                'unknown_reasons':list(reasons),
                                'primary_eligible':bool(native and scope_compatible),
                                'space_unit':native.get('space_unit') if native else None,
                                'space_unit_method':native.get('space_unit_method') if native else None,
                                'space_estimation_limitation':'Native adjacent monospaced x-advance estimate; no source/target supplied to extractor; exact original space count not proven.'},
             'reconstruction':{'status':'AVAILABLE','target_text':target,'format':'CODE','visible_text':target,
                               'mathml':None,'path':str(document),'sha256':artifact_sha,
                               'locator':'Original human E1_channels.MAPPED.delivered_text; identical original RAW text.',
                               'unknown_reasons':list(reasons),
                               'human_adjudicated_delivery_channel':channel,
                               'mixed_enrichment_refs':mixed,'prediction_refs':predicted_refs,
                               'feature_scope':'MATCHED_HUMAN_UNIT' if scope_compatible else 'LARGER_PREDICTED_ITEM' if 'BOUNDARY' in boundary_status else 'UNKNOWN'},
             'a':a,
             'b':{'status':'UNKNOWN','pass':None,'paired_row_ids':[],'pairing_provenance':None,
                  'character_similarity':None,'operator_sequence_exact':None,'number_sequence_exact':None,
                  'unknown_reasons':['Integrator must establish independent reconstructor and exact source-region identity.'],
                  'evidence_paths':[]},
             'c':{'status':'NA','pass':None,'renderer':'NA','bbox':None,
                  'unknown_reasons':['Code: mathematical renderability signal not applicable.'],'evidence_paths':[]},
             'a_native_orig_diagnostic':{'status':'NA','note':'Not evaluated; assembled Docling orig is not primary a or an independent reconstructor.'},
             'prediction_group_id':group,'duplicate_prediction_group':None,
             'primary_scope_compatible':scope_compatible,'unknown_reasons':reasons,
             'evidence_paths':[str(human_path),str(analysis_path)]+([native_info['path']] if native_info else []),
             'notes':['Original human label unchanged. No runtime execution. Printed log identity/number changes are Q4 evidence, not Q33 executable logic.',
                      'All original RAW/MAPPED delivery strings equal for these 21 records; retain mixed enriched/native composition.',
                      'No target-text search was used to locate native glyph evidence.'],
             'human_Q33_executable_logic':human['Q33_executable_logic']}
        rows.append(row)
    groups=collections.Counter(r['prediction_group_id'] for r in rows)
    for row in rows:
        if groups[row['prediction_group_id']]>1:row['duplicate_prediction_group']=row['prediction_group_id']
    files=[human_path,analysis_path,inputs_path,manifest_path,helper,P/'cohort-schema.json',
           BASE/'signals-character-method.json',BASE/'signals-character-method-amendment-native.json',
           BASE/'signals-character-method-amendment-scope.json',BASE/'signals-character-method-amendment-syntax.json',
           P/'pdfium_glyph_helpers.py',P/'code-utf16-source-audit.json',P/'cohort-w3-code.json']
    result={'schema_version':'w3b-signals-cohort-v1','cohort':'W3_CODE21','original_human_unit_count':21,
            'inputs':[{'path':str(f),'sha256':sha(f)} for f in files],
            'method_sha256':sha(BASE/'signals-character-method.json'),
            'character_helper_sha256':sha(helper),'rows':rows,
            'summary':{'original_rows':21,'independent_prediction_groups':len(groups),
                       'human_status_counts':dict(collections.Counter(r['human_status'] for r in rows)),
                       'primary_label_eligible':sum(r['primary_label_eligible'] for r in rows),
                       'a_status_counts':dict(collections.Counter(r['a']['status'] for r in rows)),
                       'a_pass_counts':dict(collections.Counter(str(r['a']['pass']) for r in rows)),
                       'scope_compatible_rows':sum(r['primary_scope_compatible'] for r in rows)},
            'notes':['Only original 21 W3 code human records; extra P04 algorithm not included.',
                     'Source-level human labels are not reattached to whole mixed prediction items.',
                     'All signals use pinned helper and pre-BEGIN5 amendments; no threshold change or new inference.']}
    assert result['summary']['human_status_counts']=={'CONFIRMED_MEANING_PRESERVED':9,'ORACLE_ALIGNMENT_ERROR':4,'CONFIRMED_BLOCKING':6,'UNKNOWN':2}
    assert all(r['a']['status']=='UNKNOWN' for r in rows if r['human_status']=='ORACLE_ALIGNMENT_ERROR')
    (P/'cohort-w3-code-utf16-v2.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':main()
