"""BEGIN5: original W3 human50; pinned signals; no inference or relabeling."""
import collections
import hashlib
import json
import re
from pathlib import Path
import sys

P = Path(__file__).resolve().parent
BASE = P.parent
ROOT = BASE.parent
W3 = ROOT / 'pdf-core-w3-structured-elements-2026-10-20/formula-code'
sys.path.insert(0, str(P))
from character_helpers import agreement, tex_visible, tex_syntax_preflight
from render_helpers import render_batch
from pdfium_glyph_helpers import decode_selected_utf16
import pypdfium2 as pdfium
import pypdfium2.raw as pdfraw


def load(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, v):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
def digest(v): return hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()
def unknown(reason):
    return dict(status='UNKNOWN', pass_=None, character_similarity=None, distance=None,
                left_chars=None, right_chars=None, operator_sequence_exact=None,
                number_sequence_exact=None, unknown_reasons=[reason], evidence_paths=[])
def blank_signal(reason):
    v = unknown(reason); v['pass'] = v.pop('pass_'); return v
def resolve(doc, ref):
    obj = doc
    for part in ref[2:].split('/'):
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def main():
    amendment = load(BASE / 'signals-character-method-amendment-syntax.json')
    entity_amendment = BASE / 'signals-character-method-bug-amendment-xml.json'
    if entity_amendment.exists():
        amendment = load(entity_amendment)
    for filename, expected in amendment['helpers_sha256'].items():
        assert sha(P / filename) == expected
    utf16_amendment = BASE / 'signals-character-method-bug-amendment-pdfium-utf16.json'
    for filename, expected in load(utf16_amendment)['helpers_sha256'].items():
        assert sha(P / filename) == expected
    hp = W3 / 'audit/final-selected-reviews-current.json'
    sp = W3 / 'e1-scores.json'
    ip = W3 / 'e1-input-hashes.json'
    mp = BASE / 'html-manifest.json'
    humans = load(hp)['records']
    scores = {v['unit_id']: v for v in load(sp)}
    actual = load(ip)
    pdfs = {v['job_id']: v for v in load(mp)['jobs']}
    assert len(humans) == len({h['unit_id'] for h in humans}) == 50
    docs, pdfdocs, pages, glyph_cache = {}, {}, {}, {}
    rows, ready = [], []
    for index, h in enumerate(humans):
        uid, job = h['unit_id'], h['job_id']
        s = scores[uid]
        dp = Path(actual[job]['folder']) / 'document.json'
        if job not in docs:
            assert sha(dp) == actual[job]['document_sha256']
            docs[job] = load(dp)
            assert sha(pdfs[job]['pdf']) == pdfs[job]['pdf_sha256']
            pdfdocs[job] = pdfium.PdfDocument(pdfs[job]['pdf'])
        doc = docs[job]
        refs = s.get('reconstruction_ref_order') or s['matched_refs']
        assert set(refs) == set(s['matched_refs'])
        processed = s['actual_processed_refs']
        native_items = [resolve(doc, r) for r in refs]
        target = s['channels']['MAPPED']['delivered_text']
        assert target == s['channels']['RAW']['delivered_text']
        # Preserve exactly the original judged delivery, rather than source or orig replacement.
        assert target == '\n\n'.join(i.get('text', '') or i.get('orig', '') for i in native_items) or target == '\n'.join(i.get('text', '') or i.get('orig', '') for i in native_items) or len(refs) > 1
        scope_ok = not bool(h.get('source_alignment_caveat'))
        scope_reason = h.get('source_alignment_caveat')
        reasons = [] if scope_ok else ['Original human source block excludes neighboring predicted equation; complete fixed prediction extent is larger.']
        region_info, glyph_parts = [], []
        native_known = True
        # Original bbox, no padding or target-driven search; preserve raw PDF character order.
        for ref, item in zip(refs, native_items):
            for prov in item.get('prov', []):
                pg = prov['page_no']; box = prov['bbox']; key = (job, pg)
                if key not in glyph_cache:
                    page = pdfdocs[job][pg - 1]
                    tp = page.get_textpage()
                    glyphs = []
                    for ci in range(tp.count_chars()):
                        try:
                            cb = list(tp.get_charbox(ci)); ch = tp.get_text_range(ci, 1)
                            glyphs.append(dict(page=pg,raw_char_index=ci, raw_unicode=int(pdfraw.FPDFText_GetUnicode(tp.raw,ci)),text=ch, bbox=cb))
                        except Exception as exc:
                            glyphs.append(dict(raw_char_index=ci, text='', bbox=None, error=type(exc).__name__))
                    glyph_cache[key] = glyphs
                    pages[key] = list(page.get_size())
                    tp.close(); page.close()
                width, height = pages[key]
                if box['coord_origin'] == 'BOTTOMLEFT':
                    l, b, r, t = box['l'], box['b'], box['r'], box['t']
                else:
                    l, b, r, t = box['l'], height-box['b'], box['r'], height-box['t']
                selected = [g for g in glyph_cache[key] if g['bbox'] is not None and
                            l <= (g['bbox'][0]+g['bbox'][2])/2 <= r and
                            b <= (g['bbox'][1]+g['bbox'][3])/2 <= t]
                decoded = decode_selected_utf16(selected)
                selected = decoded['glyphs']
                native_known = native_known and decoded['status']=='KNOWN'
                glyph_parts.append(decoded['text'])
                region_info.append(dict(page=pg, bbox=[l,b,r,t], bbox_origin='BOTTOMLEFT',
                                        page_dimensions=[width,height], native_refs=[ref],
                                        source_identity=uid, crop_sha256=None, glyphs=selected,
                                        raw_char_indices=[g['raw_char_index'] for g in selected],
                                        utf16_decoder_status=decoded['status'],
                                        decoded_pair_count=decoded['decoded_pair_count'],
                                        unpaired_surrogate_indices=decoded['unpaired_surrogate_indices']))
        native_text = '\n'.join(glyph_parts)
        tail_tags = [m.group(1) for text in glyph_parts if (m := re.search(r'\(\s*(\d+)\s*\)\s*$', text))]
        source_tag = tail_tags[0] if len(region_info)==1 and len(tail_tags)==1 else None
        native_path = P / 'formula-native' / (uid.replace(':','__') + '.json')
        if not native_known:reasons.append('Selected region contains an unpaired UTF16 surrogate; no bbox expansion or partial-pair repair.')
        save(native_path, dict(unit_id=uid, pdf=pdfs[job]['pdf'], pdf_sha256=pdfs[job]['pdf_sha256'],
                               text=native_text, regions=region_info,
                               decoder_status='KNOWN' if native_known else 'UNKNOWN',
                               selection_policy='Glyph center within unchanged native provenance bbox; zero padding; raw PDF char index order within region, declared fixed ref order across regions; retain selected original whitespace. Decode adjacent selected UTF16 pairs to Unicode scalar; retain both raw indices; unpaired selected surrogate UNKNOWN. No target search or x/y reorder.'))
        public_regions = [{k:v for k,v in x.items() if k not in ('glyphs','raw_char_indices')} for x in region_info]
        projection = tex_visible(target)
        try:
            preflight = tex_syntax_preflight(target)
        except Exception as exc:
            # Converter/adapter failure is UNKNOWN, never proof of invalid input.
            preflight = dict(status='UNKNOWN', **{'pass':None}, reason='Pinned preflight converter/XML adapter exception: '+type(exc).__name__, exception_detail=str(exc))
        a = blank_signal('Missing complete native glyph region or supported visible projection.')
        if scope_ok and native_known and native_text and projection['status'] == 'KNOWN':
            a.update(agreement(native_text, projection['visible_text'], 'formula'))
            a['unknown_reasons'] = [] if a['status']=='KNOWN' else [a.get('reason','Unknown comparison')]
        else:
            a['unknown_reasons'] = reasons + ([] if native_text else ['Empty original-PDF bbox glyph stream.']) + ([] if projection['status']=='KNOWN' else [projection.get('reason','Unsupported visible projection')])
        a['evidence_paths'] = [str(native_path)]
        if preflight['status'] == 'READY_FOR_ACTUAL_RENDER':
            ready.append(dict(unit_id=uid, mathml=preflight['mathml']))
            c = dict(status='UNKNOWN', **{'pass':None}, renderer='Chrome155',bbox=None,
                     unknown_reasons=['Awaiting actual local Chrome rendering.'],evidence_paths=[])
        else:
            c = dict(status=preflight['status'], **{'pass':preflight.get('pass')}, renderer='Chrome155',bbox=None,
                     unknown_reasons=[preflight.get('reason',preflight.get('syntax_error','Unsupported syntax'))],
                     evidence_paths=[],syntax_preflight=preflight)
        per_ref_groups = ['CodeFormulaV2:'+digest(dict(model='docling-project/CodeFormulaV2',artifact_sha256=actual[job]['document_sha256'],predicted_refs=[r])) for r in processed]
        group = 'CodeFormulaV2:'+digest(dict(model='docling-project/CodeFormulaV2',artifact_sha256=actual[job]['document_sha256'],predicted_refs=sorted(processed)))
        orig = '\n'.join(i.get('orig','') for i in native_items)
        diagnostic = agreement(orig, projection.get('visible_text'), 'formula') if projection['status']=='KNOWN' else blank_signal('Unsupported visible projection; assembled-orig diagnostic not compared to partial projection.')
        diagnostic['note'] = 'Docling assembled orig diagnostic only; not primary a or independent reconstruction.'
        mixed = [dict(ref=r,actually_enriched=r in processed,copied_native_or_orig_fallback=r not in processed) for r in refs]
        status = h['status']; error = True if status=='CONFIRMED_BLOCKING' else False if status in ('MEANING_PRESERVED','CONFIRMED_MEANING_PRESERVED') else None
        row = dict(row_id='W3_FORMULA50:'+uid, original_unit_id=uid, cohort='W3_FORMULA50', category='formula',
                   unit_scope='SOURCE_BLOCK',model='docling-project/CodeFormulaV2',model_checkpoint_revision='ecedbe111d15c2dc60bfd4a823cbe80127b58af4',
                   human_status=status,human_error=error,primary_label_eligible=error is not None,
                   human_label_evidence=dict(path=str(hp),sha256=sha(hp),record_locator=uid,scope_note='Original whole source block label; not copied to separate rows or neighboring predicted equation.'),
                   pdf_sha256=pdfs[job]['pdf_sha256'],original_pages=h['source_pages'],refs=refs,
                   source_identity=dict(kind='FROZEN_SOURCE_UNIT',value=uid,evidence_paths=[str(hp)]+[i['path'] for i in h.get('source_images',[])],visually_verified_source_identity=True,
                                        source_equation_tag=source_tag,equation_tag_provenance='Original PDF glyph stream has parenthesized integer at the end of the single source-verified formula bbox; never E1-derived.' if source_tag else 'UNKNOWN: no unique single-region terminal PDF equation tag.',
                                        source_pdf_equation_locator=(pdfs[job]['pdf_sha256']+':p'+str(region_info[0]['page'])+':eq'+source_tag) if source_tag else None,
                                        source_pdf_equation_identity=None,
                                        equation_tag_locator_is_whole_block_identity=False,
                                        equation_tag_set_status='PARTIAL_TERMINAL_LOCATORS_NOT_COMPLETE_EQUATION_SET',
                                        terminal_equation_tag_locators=tail_tags,
                                        whole_block_native_refs=refs,whole_block_regions=public_regions,
                                        whole_block_source_row_field_count=h.get('source_rows_field_count'),
                                        block_scope_note='Terminal tag is only a locator, not proof of an entire multi-row/compound block. Independent b requires matching the full original human-unit scope/region; no labels expanded to rows.'),
                   regions=public_regions,
                   native_evidence=dict(status='AVAILABLE' if native_text else 'UNKNOWN',kind='ALIGNED_TEXT_LAYER_GLYPHS',visible_text=native_text,
                                        path=str(native_path),sha256=sha(native_path),locator='Per-region raw_char_indices and glyph bboxes; original PDF center-in-bbox selection, no padding or target search.',
                                        unknown_reasons=reasons,primary_eligible=bool(scope_ok and native_known and native_text),
                                        utf16_decoder_status='KNOWN' if native_known else 'UNKNOWN'),
                   reconstruction=dict(status='AVAILABLE',target_text=target,format='LATEX',visible_text=projection.get('visible_text'),mathml=preflight.get('mathml'),
                                       path=str(dp),sha256=actual[job]['document_sha256'],locator=refs,
                                       unknown_reasons=reasons,human_adjudicated_delivery_channel='MIXED_FALLBACK' if any(not v['actually_enriched'] for v in mixed) else 'MAPPED',
                                       mixed_enrichment_refs=mixed,prediction_refs=processed,
                                       feature_scope='MATCHED_HUMAN_UNIT' if scope_ok else 'LARGER_PREDICTED_ITEM'),
                   syntax_pipeline=preflight,
                   a=a,b=dict(status='UNKNOWN',**{'pass':None},paired_row_ids=[],pairing_provenance=None,character_similarity=None,operator_sequence_exact=None,number_sequence_exact=None,
                              unknown_reasons=['Integrator must establish independent reconstructor and exact source-region identity.'],evidence_paths=[]),c=c,
                   a_native_orig_diagnostic=diagnostic,prediction_group_id=group,prediction_group_ids=per_ref_groups,
                   duplicate_prediction_group=None,primary_scope_compatible=scope_ok,unknown_reasons=reasons,
                   evidence_paths=[str(hp),str(sp),str(native_path)],
                   notes=['RAW and MAPPED judged texts identical; actual nonempty E1 text retained, not rescued by orig.',
                          'Original human50 block scope retained. Render/character agreement are not mathematical semantic proof.'],
                   family=h['family'],job_id=job,source_alignment_caveat=scope_reason)
        rows.append(row)
        print('prepared',index+1,uid,preflight['status'],len(native_text),flush=True)
    render = render_batch(ready, BASE, tag='w3-formula')
    rp = P / 'formula-render-evidence.json'; save(rp,render)
    rendered = {v['unit_id']:v for v in render['results']}
    for row in rows:
        if row['original_unit_id'] in rendered:
            v=rendered[row['original_unit_id']]
            row['syntax_pipeline']['actual_render']=v
            row['c']=dict(status=v['status'],**{'pass':v.get('pass')},renderer='Chrome155',bbox=v.get('bbox'),
                          unknown_reasons=[] if v['status']=='KNOWN' else [v.get('reason','Render environment unknown')],
                          evidence_paths=[str(rp)],render_evidence=v,
                          note='Actual supported syntax/rendering only; no semantic correctness inference.')
        else:
            row['c']['evidence_paths']=[str(rp),str(P/'build_w3_formula_cohort.py')]
    groups=collections.Counter(r['prediction_group_id'] for r in rows)
    refgroups=collections.Counter(g for r in rows for g in r['prediction_group_ids'])
    for row in rows:
        if groups[row['prediction_group_id']]>1:row['duplicate_prediction_group']=row['prediction_group_id']
        row['overlapping_prediction_groups']=[g for g in row['prediction_group_ids'] if refgroups[g]>1]
    files=[hp,sp,ip,mp,P/'character_helpers.py',P/'render_helpers.py',P/'pdfium_glyph_helpers.py',P/'cohort-schema.json']+[BASE/n for n in ['signals-character-method.json','signals-character-method-amendment-native.json','signals-character-method-amendment-scope.json','signals-character-method-amendment-syntax.json']]
    if entity_amendment.exists():files.append(entity_amendment)
    files.append(utf16_amendment)
    summary=dict(original_rows=len(rows),human_status_counts=dict(collections.Counter(r['human_status'] for r in rows)),
                 primary_label_eligible=sum(r['primary_label_eligible'] for r in rows),independent_prediction_groups=len(groups),
                 distinct_item_prediction_groups=len(refgroups),overlapping_item_groups=sum(n>1 for n in refgroups.values()),
                 a_status_counts=dict(collections.Counter(r['a']['status'] for r in rows)),a_pass_counts=dict(collections.Counter(str(r['a']['pass']) for r in rows)),
                 c_status_counts=dict(collections.Counter(r['c']['status'] for r in rows)),c_pass_counts=dict(collections.Counter(str(r['c']['pass']) for r in rows)),
                 scope_compatible_rows=sum(r['primary_scope_compatible'] for r in rows))
    assert sum(r['human_error'] is True for r in rows)==15
    assert sum(r['human_error'] is False for r in rows)==28
    assert sum(r['human_error'] is None for r in rows)==7
    result=dict(schema_version='w3b-signals-cohort-v1',cohort='W3_FORMULA50',original_human_unit_count=50,
                inputs=[dict(path=str(f),sha256=sha(f)) for f in files],method_sha256=sha(BASE/'signals-character-method.json'),rows=rows,summary=summary,
                notes=['Original W3 human50 only; new W3b single-formula40 not included.',
                       'Glyph adapter approved before extraction: original PDF raw char centers in unchanged provenance bbox; no padding; native raw index order.',
                       '50 original rows are correlated where their predicted refs overlap; per-ref and composite groups both retained.',
                       'Scalar character agreement does not capture 2D scope/attachment; c is actual syntax/render support only.'])
    save(P/'cohort-w3-formula.json',result)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
