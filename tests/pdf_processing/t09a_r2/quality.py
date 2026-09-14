"""Source-audited checks over delivered full content evidence (private local inputs)."""
import json
import os
import hashlib
import sys
from pathlib import Path

ROOT = Path('/tmp/t09a-r2-'+os.environ['T09A_R2_RUN']+'-results')
ORACLES = Path('/tmp/t09a-oracles')

def normalized(text): return ' '.join(text.split())

def check(sid, trial):
    doc = json.loads((ROOT/(trial+'-document.json')).read_text())
    report = json.loads((ROOT/(trial+'-evidence.json')).read_text())
    checks: dict = {'document_sha256':hashlib.sha256((ROOT/(trial+'-document.json')).read_bytes()).hexdigest(),
              'content_evidence_sha256':hashlib.sha256((ROOT/(trial+'-evidence.json')).read_bytes()).hexdigest()}
    if sid in ('06','07'):
        expected = json.loads((ORACLES/(sid+'-table-full-audit.json')).read_text())
        table = next(t for t in doc['tables'] if t['data']['num_rows']==(26 if sid=='06' else 15))
        cells = {(c['start_row_offset_idx'],c['start_col_offset_idx']):c for c in table['data']['table_cells']}
        for entry in expected:
            actual = cells[(entry['row'],entry['col'])]
            source = entry['parsed_text'] if sid=='07' and '\x02' in entry['source_text'] else entry['source_text']
            assert normalized(actual['text'])==normalized(source), (sid,entry['row'],entry['col'])
            assert actual['row_span']==entry['rowspan']
        checks['source_audited_table_cells'] = len(expected)
    if sid=='08':
        typed = {x['ref']:x for x in report['items']}
        # Source visual inspection of original 101,103,107,108 fixed these pairs.
        expected = [(3,'BREADTH-FIRST-SEARCH','3.11'),(5,'UNIFORM-COST-SEARCH','3.14'),
                    (9,'DEPTH-LIMITED-SEARCH','3.17'),(10,'ITERATIVE-DEEPENING-SEARCH','3.18')]
        pairs = []
        code_oracle = json.loads((ORACLES/'aima-code.json').read_text())
        # Source-backed follow-up audits the actual split/merged items as retained;
        # a missing CodeItem alone is not evidence that algorithm text was lost.
        audited_refs = {3:list(range(43,64)),5:[109,113],9:[299,300],10:list(range(310,315))}
        caption_refs = {3:64,5:114,9:301,10:315}
        for page,name,number in expected:
            matches = [x for x in report['items'] if x.get('text') and name in x['text']
                       and any(r['page']==page for r in x['regions'])]
            source = next(x for x in code_oracle if x['processed_page']==page)
            code = next((x for x in matches if x['actual_type']=='code'),None)
            pair = bool(code and any(number in typed[c['$ref']]['text'] for c in code['captions']))
            actual_items=[typed['#/texts/'+str(n)] for n in audited_refs[page]]
            pieces=[x['text'] for x in actual_items]
            if page==5:
                # Only original-page-103 charspan belongs to the algorithm header.
                span=next(r['provenance']['charspan'] for r in actual_items[0]['regions'] if r['page']==page)
                pieces[0]=pieces[0][span[0]:span[1]]
            equal = ''.join(''.join(pieces).split())==''.join(source['source_native_text'].split())
            caption=typed['#/texts/'+str(caption_refs[page])]
            pairs.append({'processed_page':page,'algorithm':name,'caption_number':number,
                'matching_typed_refs':[{'ref':x['ref'],'type':x['actual_type']} for x in matches],
                'declared_code_caption_expectation_met':pair,
                'complete_sequence_matches_source_native_layer_whitespace_only':equal,
                'actual_content_refs':[{'ref':x['ref'],'type':x['actual_type'],'captions':x['captions']} for x in actual_items],
                'caption_disposition':{'ref':caption['ref'],'actual_type':caption['actual_type']},
                'sequence_audit':'concatenate actual retained items in audited source order; uniform-cost header uses its own provenance charspan; whitespace only',
                'source_font_control_character':source['source_font_control_character'],
                'quality_status':'passed_declared_pair_and_sequence' if pair and equal else 'unqualified_algorithm_structure_or_representation'})
        checks['source_reviewed_algorithm_caption_pairs'] = pairs
        checks['algorithm_quality_gate'] = 'open' if any(not p['declared_code_caption_expectation_met'] or not p['complete_sequence_matches_source_native_layer_whitespace_only'] for p in pairs) else 'passed'
        observations = report['representation_observations']
        assert any(x.get('review_id',x.get('id'))=='uniform-cost-symbols' for x in observations), observations
        checks['region_representation_uncertainty'] = True
        # Source page 103 ends a sentence continued on 104. This checks that join,
        # not total body/marginalia order or all mathematical typography.
        join = next(x for x in report['items'] if x.get('text') and 'second path' in x['text']
                    and any(r['page']==5 for r in x['regions']))
        parts = [{'page':r['page'],'charspan':r['provenance']['charspan']} for r in join['regions']]
        joined_correctly = join['text'].find('to Bucharest with cost',join['text'].index('second path')) > join['text'].index('second path')
        checks['contiguous_103_104_sentence_join'] = {'ref':join['ref'],'original_pages':[103,104],
            'parts':parts,'declared_expectation_met':joined_correctly,
            'expected_continuation_ref':'#/texts/131',
            'expected_continuation_prefix':'to Bucharest with cost',
            'incorrectly_joined_margin_label':'DEPTH-FIRST SEARCH',
            'status':'passed' if joined_correctly else 'unqualified_paragraph_margin_association'}
        checks['source_quality_gate'] = 'open' if checks['algorithm_quality_gate']=='open' or not joined_correctly else 'passed'
    if sid=='09':
        equations = [x for x in report['formula_occurrences'] if x.get('review_id','').startswith('eq')]
        assert {x['review_id'] for x in equations}=={'eq1','eq2','eq3','eq4','eq5','eq6'}
        typed = {x['ref']:x for x in report['items']}
        assert any(typed[r]['actual_type']=='text' for x in equations if x['review_id']=='eq2' for r in x['refs'])
        assert report['representation_observations']
        oracle = json.loads((ORACLES/'quality-oracle.json').read_text())
        def h(text):return hashlib.sha256(json.dumps(text,ensure_ascii=False).encode()).hexdigest()
        for page in [p for p in oracle['pages'] if p['source_id']=='09']:
            actual = [x for x in report['items'] if any(g['page']==page['processed_page'] for g in x['regions'])]
            assert len(actual)==len(page['items'])
            for node,expected in zip(actual,page['items']):
                assert node['actual_type']==expected['type'] and h(node['text'])==expected['text_sha256']
                assert [h(typed[c['$ref']]['text']) for c in node['captions']]==expected['caption_text_hashes']
        checks.update(all_six_equations=True,textitem_equation2=True,full_audited_typed_text_captions_order=True)
    if sid=='10':
        oracle = json.loads((ORACLES/'new-source-oracle.json').read_text())
        regions = next(x for x in oracle if x['source_id']=='10')['regions']
        for region in regions:
            l,t,r,b = region['bbox']; pieces=[]
            for item in report['items']:
                if not item.get('text'):continue
                for g in item['regions']:
                    x1,y1,x2,y2 = g['bbox_top_left_points']
                    if g['page']==1 and l<=(x1+x2)/2<=r and t<=(y1+y2)/2<=b:
                        pieces.append((y1,x1,item['text']));break
            assert normalized(region['expected_text'])==normalized(' '.join(x[2] for x in sorted(pieces))),region['id']
        assert len(regions)==27
        checks['complete_source_textboxes']=27
    return checks

if __name__=='__main__':
    sid,trial=sys.argv[1:3]
    result = check(sid,trial)
    (ROOT/(trial+'-quality.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
