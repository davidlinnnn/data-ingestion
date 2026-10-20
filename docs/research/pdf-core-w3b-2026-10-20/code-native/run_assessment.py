"""Stage4: fixed source inventory, PDF glyph native reconstruction, E0/E1 diagnostics."""
import collections
import hashlib
import json
import re
import statistics
from pathlib import Path

from extract_native import extract
from metrics import compare, levenshtein

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
W3 = ROOT / 'docs/research/pdf-core-w3-structured-elements-2026-10-20/formula-code'
R3 = ROOT / 'docs/research/pdf-core-w2-native-coverage-round3-2026-10-20'


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(doc, ref):
    node = doc
    for bit in ref.removeprefix('#/').split('/'):
        node = node[int(bit)] if isinstance(node, list) else node[bit]
    return node


def gold(unit):
    raw = unit['raw']
    # Only the environment's initial options are removed. No general macro stripping.
    raw = re.sub(r'^\s*\[[^\]\n]*\]\s*\n?', '', raw, count=1).strip('\r\n')
    if unit['kind'] == 'algorithm':
        lines = unit.get('normalized_lines') or [{'text':x} for x in raw.splitlines()]
        commands = {'Require':'REQUIRE','Ensure':'ENSURE','State':'STATE',
                    'If':'IF','Else':'ELSE','ElsIf':'ELSE IF','EndIf':'END IF',
                    'For':'FOR','ForAll':'FOR ALL','EndFor':'END FOR',
                    'While':'WHILE','EndWhile':'END WHILE','Return':'RETURN',
                    'Repeat':'REPEAT','Until':'UNTIL'}
        mapped=[]
        for line in lines:
            text=line['text']
            for command, keyword in commands.items():
                text=re.sub(r'\\'+command+r'\b',lambda _:keyword,text)
            mapped.append(text)
        return raw, 'UNKNOWN_ALGORITHM_PRINTED_REPRESENTATION_UNEXPANDED_MATH', {
            'normalized_source_lines':lines,'keyword_preserving_diagnostic_lines':mapped,
            'keyword_mapping':commands,'math_operators_not_stripped':True}
    if re.search(r'\\(?:textbf|texttt|textcolor|color|lstinline|begin|end|small|footnotesize|scriptsize)\b',raw):
        return raw,'UNKNOWN_LATEX_MARKUP_PRINTED_REPRESENTATION',{}
    return raw,'LITERAL_LISTING',{}


def channel_text(row, channel):
    return row.get('channels',{}).get(channel,{}).get('delivered_text','')


def main():
    paths = {'oracle':W3/'oracle.json','E0':W3/'e0-delivery-scores.json',
             'E1':W3/'e1-scores.json','E1_inputs':W3/'e1-input-hashes.json',
             'manual':W3/'audit/code-review.json','algorithms':W3/'audit/algorithm-role-review.json',
             'pdf_manifest':HERE.parent/'html-manifest.json'}
    source=load(paths['oracle']); units=[u for u in source['units'] if u['kind'] in ['code','algorithm']]
    e0={r['unit_id']:r for r in load(paths['E0'])}
    e1={r['unit_id']:r for r in load(paths['E1'])}
    actual=load(paths['E1_inputs'])
    manual={r['unit_id']:r for r in load(paths['manual'])['records']}
    algorithms={r['unit_id']:r for r in load(paths['algorithms'])['records']}
    pdfs={j['job_id']:j for j in load(paths['pdf_manifest'])['jobs']}
    docs={};records=[]
    (HERE/'native-evidence').mkdir(exist_ok=True)
    for index,unit in enumerate(units):
        uid=unit['id'];job=unit['job_id'];score=e0[uid];review=manual.get(uid)
        refs=score['matched_refs']
        if uid in algorithms:
            refs=algorithms[uid]['manually_verified_refs']
        identity='FIXED_SOURCE_NATIVE_ALIGNMENT_CANDIDATE'
        if unit['scope']!='IN_SCOPE':identity='UNKNOWN_SOURCE_SCOPE'
        elif not refs:identity='UNKNOWN_FIXED_ALIGNMENT'
        elif score['alignment_status']!='ALIGNED_CANDIDATE' and uid not in algorithms:
            identity='UNKNOWN_FIXED_ALIGNMENT'
        if review:
            identity=('ORACLE_ALIGNMENT_ERROR' if review['status']=='ORACLE_ALIGNMENT_ERROR'
                      else 'HUMAN_REVIEWED_SAME_SOURCE_REGION')
        if uid in algorithms:identity='HUMAN_REVIEWED_ALGORITHM_REGION'
        reference,representation,gold_info=gold(unit)
        row={'unit_id':uid,'job_id':job,'kind':unit['kind'],'family':pdfs[job]['family'],
             'scope':unit['scope'],'source_file':unit['source_file'],'source_line':unit['source_line'],
             'source_raw_sha256':unit['raw_sha256'],'source_text':reference,
             'source_pages':unit['pages'],'fixed_refs':refs,'identity_status':identity,
             'gold_representation':representation,'gold_diagnostic':gold_info,
             'manual_21_subset':review is not None,'channels':{},
             'source_native_identity_independently_reviewed':review is not None or uid in algorithms,
             'Q4_semantic_label':review.get('Q4_meaning_changed') if review else None,
             'Q33_executable_logic':review.get('Q33_executable_logic') if review else None,
             'runtime_executed':False}
        if review:row['manual_status']=review['status']
        comparable=identity.startswith(('FIXED_SOURCE','HUMAN_REVIEWED'))
        regions=[];native=None
        if comparable:
            if job not in docs:docs[job]=load(R3/'runs/V3_B/jobs'/job/'document.json')
            document=docs[job]
            for ref in refs:
                try:item=resolve(document,ref)
                except (KeyError,IndexError):continue
                for prov in item.get('prov',[]):
                    b=prov['bbox'];page=prov['page_no']
                    if b.get('coord_origin')=='TOPLEFT':
                        h=document['pages'][str(page)]['size']['height']
                        box=[b['l'],h-b['b'],b['r'],h-b['t']]
                    else:box=[b['l'],b['b'],b['r'],b['t']]
                    regions.append({'page':page,'bbox':box,'ref':ref})
            if regions:
                native=extract(pdfs[job]['pdf'],regions)
                evidence=HERE/'native-evidence'/(uid.replace(':','__')+'.json')
                evidence.write_text(json.dumps(native,ensure_ascii=False,indent=2)+'\n')
                evidence.with_suffix('.txt').write_text(native['text']+'\n')
                row['native_evidence']={'path':str(evidence),'sha256':sha(evidence),
                                        'pdf_sha256':native['pdf_sha256'],
                                        'glyphs':len(native['characters']),'lines':len(native['lines']),
                                        'space_unit':native['space_unit'],'space_unit_method':native['space_unit_method'],
                                        'regions':regions}
        texts={'native':native['text'] if native else '',
               'E0_RAW':channel_text(score,'RAW'),'E0_MAPPED':channel_text(score,'MAPPED')}
        processed=set(actual.get(job,{}).get('processed_refs',[]))
        row['actual_E1_processed_refs']=[r for r in refs if r in processed]
        enriched=bool(row['actual_E1_processed_refs'])
        texts['E1_RAW']=channel_text(e1.get(uid,{}),'RAW') if enriched else ''
        texts['E1_MAPPED']=channel_text(e1.get(uid,{}),'MAPPED') if enriched else ''
        if uid in algorithms:
            algorithm=algorithms[uid]
            baseline_text='\n'.join(item.get('text',item.get('active_text','')) for item in algorithm['native_items'])
            variant_text='\n'.join(item.get('active_text','') for item in algorithm.get('E1',{}).get('active_items',[]))
            # Frozen scorer missed this known algorithm identity; manual evidence
            # is an explicitly separate supplement, not a change to frozen refs.
            texts['E0_RAW']=texts['E0_MAPPED']=baseline_text
            if enriched:texts['E1_RAW']=texts['E1_MAPPED']=variant_text
            row['algorithm_manual_alignment_supplement']=True
        if review:
            for group,key in [('E0_channels','E0'),('E1_channels','E1')]:
                for channel in ['RAW','MAPPED']:
                    texts[key+'_'+channel]=review.get(group,{}).get(channel,{}).get('delivered_text',texts[key+'_'+channel])
        for name,text in texts.items():
            status='COMPARABLE_FIXED_SOURCE_REGION'
            if not comparable:status=identity
            elif name.startswith('E1') and not enriched:status='NOT_PROCESSED'
            elif name=='native' and not native:status='UNKNOWN_NATIVE_REGION'
            elif representation!='LITERAL_LISTING':status=representation
            entry={'status':status,'text':text,'source_chars':len(reference),'target_chars':len(text)}
            if comparable and (not name.startswith('E1') or enriched) and (name!='native' or native):
                # Nonliteral representation remains visible but never enters primary CER aggregation.
                entry['metrics']=compare(reference,text)
                entry['primary_CER_eligible']=status=='COMPARABLE_FIXED_SOURCE_REGION'
                if name=='native':
                    entry['indentation_evidence_status']=('PDF_SPACE_OR_MONOSPACED_ADVANCE' if native['space_unit'] else 'VISUAL_X_HIERARCHY_ONLY')
                    entry['exact_whitespace_reconstruction_proven']=False
            row['channels'][name]=entry
        row['tri_source_comparable'] = all(row['channels'][c]['status']=='COMPARABLE_FIXED_SOURCE_REGION' for c in ['native','E0_RAW','E1_RAW'])
        records.append(row)
        (HERE/'per-unit.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
        print(index+1,uid,identity,representation,flush=True)
    inputs={name:{'path':str(p),'sha256':sha(p)} for name,p in paths.items()}
    summary={'inventory_units':len(records),'kind_scope':dict(collections.Counter(r['kind']+' / '+r['scope'] for r in records)),
             'original_manual_units':len(manual),'manual_units':dict(collections.Counter(r.get('manual_status') for r in records if r['manual_21_subset'])),
             'channels':{},'tri_source_comparable':sum(r['tri_source_comparable'] for r in records),
             'manual21_tri_source_comparable':sum(r['tri_source_comparable'] for r in records if r['manual_21_subset']),
             'inputs':inputs,'no_inference':True,'no_source_or_previous_results_modified':True}
    for ch in ['native','E0_RAW','E0_MAPPED','E1_RAW','E1_MAPPED']:
        valid=[r['channels'][ch]['metrics']['raw']['CER'] for r in records if r['channels'][ch].get('primary_CER_eligible')]
        summary['channels'][ch]={'status_counts':dict(collections.Counter(r['channels'][ch]['status'] for r in records)),
                                'primary_CER_units':len(valid),'CER_p50':statistics.median(valid) if valid else None,
                                'CER_max':max(valid) if valid else None,
                                'not_semantic_error_rate':True}
    summary['source_inventory_retained']=len(records)==99
    summary['four_alignment_errors_not_primary']=all(not r['channels']['native'].get('primary_CER_eligible') for r in records if r.get('manual_status')=='ORACLE_ALIGNMENT_ERROR')
    (HERE/'inventory.json').write_text(json.dumps({'inputs':inputs,'units':[{k:v for k,v in r.items() if k not in ['channels','gold_diagnostic']} for r in records]},ensure_ascii=False,indent=2)+'\n')
    (HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
