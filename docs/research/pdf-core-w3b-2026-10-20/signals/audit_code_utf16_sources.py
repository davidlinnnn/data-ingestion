"""Inspect original PDF raw Unicode; do not infer absence from old glyph JSON."""
import collections
import hashlib
import json
import struct
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as raw

from pdfium_glyph_helpers import decode_selected_utf16

P=Path(__file__).resolve().parent
BASE=P.parent
R3=BASE.parent/'pdf-core-w2-native-coverage-round3-2026-10-20'


def load(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(doc,ref):
    node=doc
    for key in ref.removeprefix('#/').split('/'):
        node=node[int(key)] if isinstance(node,list) else node[key]
    return node


def main():
    old=load(BASE/'code-native/per-unit.json');signals=load(P/'cohort-w3-code.json')
    jobs={j['job_id']:j for j in load(BASE/'html-manifest.json')['jobs']}
    units={r['unit_id']:{'unit_id':r['unit_id'],'job_id':r['job_id'],
           'regions':r['native_evidence']['regions'],'stage4_primary_native':r['channels']['native'].get('primary_CER_eligible',False),
           'stage4_common':r['tri_source_comparable'],'signals21':r['manual_21_subset'],
           'signals_a_known':False,'region_provenance':'Original Stage4 saved fixed provenance regions'}
           for r in old if 'native_evidence'in r}
    for row in signals['rows']:
        uid=row['original_unit_id'];job=uid.split(':')[0]
        if uid in units:
            units[uid]['signals21']=True;units[uid]['signals_a_known']=row['a']['status']=='KNOWN'
            continue
        doc=load(R3/'runs/V3_B/jobs'/job/'document.json');regions=[]
        for ref in row['refs']:
            for prov in resolve(doc,ref).get('prov',[]):
                b=prov['bbox'];page=prov['page_no']
                assert b.get('coord_origin')=='BOTTOMLEFT'
                regions.append({'page':page,'bbox':[b['l'],b['b'],b['r'],b['t']],'ref':ref})
        units[uid]={'unit_id':uid,'job_id':job,'regions':regions,'stage4_primary_native':False,
                    'stage4_common':False,'signals21':True,'signals_a_known':False,
                    'region_provenance':'Existing refs for original alignment-error cases; diagnostic only, not repaired identity.'}
    page_regions=collections.defaultdict(list)
    for uid,unit in units.items():
        for ri,region in enumerate(unit['regions']):page_regions[unit['job_id'],region['page']].append((uid,ri,region))
    pages=[];per_region=collections.defaultdict(list);problem_records=[]
    pdfs={}
    try:
        for (job,page_number),regions in sorted(page_regions.items()):
            if job not in pdfs:pdfs[job]=pdfium.PdfDocument(jobs[job]['pdf'])
            page=pdfs[job][page_number-1];tp=page.get_textpage();stream=[];problems=[]
            try:
                for i in range(tp.count_chars()):
                    u=int(raw.FPDFText_GetUnicode(tp.raw,i));stream.append(u)
                    if not (0xD800<=u<=0xDFFF or u>0xFFFF):continue
                    box=list(tp.get_charbox(i));cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
                    g={'page':page_number,'raw_index':i,'raw_unicode':u,'hex':hex(u),
                       'bbox':box,'old_get_text_range_i_1':tp.get_text_range(i,1)}
                    selected=[]
                    for uid,ri,region in regions:
                        l,b,r,t=region['bbox']
                        if l<=cx<=r and b<=cy<=t:
                            per_region[uid,ri].append(g);selected.append({'unit_id':uid,'region_index':ri})
                    g['selected_regions']=selected;problems.append(g)
                pages.append({'job_id':job,'page':page_number,'PDF_sha256':jobs[job]['pdf_sha256'],
                              'raw_code_unit_count':len(stream),
                              'raw_unicode_uint32le_sha256':hashlib.sha256(b''.join(struct.pack('<I',x) for x in stream)).hexdigest(),
                              'all_page_surrogate_or_nonBMP_records':problems})
                problem_records.extend(problems)
            finally:tp.close();page.close()
    finally:
        for pdf in pdfs.values():pdf.close()
    for uid,unit in units.items():
        unit['region_decoding_checks']=[]
        for ri,region in enumerate(unit['regions']):
            glyphs=per_region.get((uid,ri),[])
            result=decode_selected_utf16(glyphs)
            unit['region_decoding_checks'].append({'region_index':ri,'region':region,
                'selected_problem_code_units':glyphs,'uniform_helper_result':result})
        unit['affected_by_surrogate_bug']=any(x['selected_problem_code_units'] for x in unit['region_decoding_checks'])
    affected=[u for u in units.values() if u['affected_by_surrogate_bug']]
    result={'method':'Read original PDF FPDFText_GetUnicode for every raw index on every existing source-region page; same tight bbox center, no padding. Decode separately per original region using trace uniform helper. No text matching or bbox expansion.',
            'inputs':[{'path':str(p),'sha256':sha(p)} for p in [BASE/'code-native/per-unit.json',P/'cohort-w3-code.json',P/'pdfium_glyph_helpers.py']],
            'counts':{'original_stage4_native_units':sum('native_evidence'in r for r in old),'original_signals_code_rows':len(signals['rows']),
                      'union_source_units_audited':len(units),'unique_PDF_pages_raw_unicode_scanned':len(pages),
                      'original_raw_code_units_scanned':sum(p['raw_code_unit_count'] for p in pages),
                      'page_problem_code_units_inside_or_outside':len(problem_records),
                      'affected_source_units':len(affected),
                      'affected_stage4_primary_native':sum(u['stage4_primary_native'] for u in affected),
                      'affected_stage4_common':sum(u['stage4_common'] for u in affected),
                      'affected_signals21':sum(u['signals21'] for u in affected),
                      'affected_signals_a_known':sum(u['signals_a_known'] for u in affected)},
            'units':list(units.values()),'pages':pages,
            'existing_code_outputs_or_labels_modified':False,
            'can_retain_sealed_primary_outputs':not any(u['stage4_primary_native'] or u['signals21'] for u in affected)}
    (P/'code-utf16-source-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['counts'],ensure_ascii=False,indent=2))
    (P/'code-utf16-source-audit.md').write_text('# Code UTF-16 原來源稽核\n\n直接讀原 PDF 的 raw Unicode，非根據既有已漏字 evidence 判斷。每個原 region 各自做中心點選取／無 padding，使用統一 decode_selected_utf16；半 surrogate pair 不擴框。\n\n'+json.dumps(result['counts'],ensure_ascii=False,indent=2)+'\n\n原 code-native 與 cohort 未改；是否可保留主結果：'+str(result['can_retain_sealed_primary_outputs'])+'。\n')


if __name__=='__main__':main()
