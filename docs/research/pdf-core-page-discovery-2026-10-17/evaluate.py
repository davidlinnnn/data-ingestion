"""Post-freeze evaluator only: glyph/context coverage is not transcription accuracy."""
from collections import Counter
import json
from pathlib import Path
import sys

import pypdfium2 as pdfium
import discovery as d

HERE=Path(__file__).resolve().parent
OLD=d.ROOT/'docs/research/pdf-core-stage1-2026-10-17/A-evaluator'
CONTRACT=d.ROOT/'docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json'


def contains(box,x,y):
    return box[0]-2 <= x <= box[2]+2 and box[1]-2 <= y <= box[3]+2


def counts(points,boxes):
    covered=sum(any(contains(b,x,y) for b in boxes) for _,x,y in points)
    return dict(source_nonspace_glyphs=len(points),covered_glyphs=covered,
                all_context_glyph_centers_covered=bool(points) and covered==len(points))


def overlap(a,b):
    area=(a[2]-a[0])*(a[3]-a[1])
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return intersection/max(area,1e-10)


def freeze():
    producer=HERE/'live-registration.json'
    inputs=[OLD/'source-census.json',OLD/'source-census.freeze.json',CONTRACT]
    census=json.loads(inputs[0].read_text())
    if d.file_hash(inputs[0]) != json.loads(inputs[1].read_text())['sha256']:
        raise ValueError('changed source census')
    d.write(HERE/'evaluation-registration.json',dict(
        producer_frozen_before_evaluator=True,producer_registration_sha256=d.file_hash(producer),
        method_sha256=d.file_hash(HERE/'evaluate.py'),
        inputs={str(p.relative_to(d.ROOT)):d.file_hash(p) for p in inputs},
        denominators=dict(source_groups=len(census['targets']),ordinary_negatives=len(census['ordinary_negatives']),legacy_units=41),
        metrics='Nonspace glyph centers with existing 2pt tolerance. Report native, detector and union separately. Full context is a geometric proxy, not required-symbol recall or content delivery. Old41 overlap>=0.45 is only a locator.',
        false_positive_measure='Report detector overlap with each ordinary negative, both any and full context; inspect broad boxes and unnecessary work separately.',
        visual_review='Review original pages and detector overlays for missed required notation, wrong or clipped regions and figure/body boundaries; no producer feedback or reconstruction.',
        quality_boundary='Original source requirements and confirmed minor tolerance retained. Empty output, complete=true or native image storage do not prove source quality.',
        calls=0,holdout_reads=0))


def evaluate():
    registration=json.loads((HERE/'evaluation-registration.json').read_text())
    if d.file_hash(HERE/'live-registration.json') != registration['producer_registration_sha256'] or d.file_hash(HERE/'evaluate.py') != registration['method_sha256']:
        raise ValueError('changed frozen evaluation')
    for name,expected in registration['inputs'].items():
        if d.file_hash(d.ROOT/name) != expected:raise ValueError('changed source evaluator input')
    manifest=json.loads((HERE/'registration.json').read_text())
    results=json.loads((HERE/'live/results.json').read_text())
    rows={}; points={}; page_sources={}
    for job in manifest['jobs']:
        source,page=job['id'].rsplit('-p',1);page=int(page)
        page_sources[source,page]=job
        rows[source,page]=dict(native=[r['bbox_top_left_points'] for r in job['native_scopes']],detector=[])
        binding=HERE/'live'/job['id']/'binding.json'
        if binding.exists():
            value=json.loads(binding.read_text())
            rows[source,page]['detector']=[c['bbox_top_left_points'] for c in value['candidates']]
        with pdfium.PdfDocument(d.ROOT/job['source']) as pdf:
            pdfpage=pdf[page-1]; textpage=pdfpage.get_textpage()
            try:
                raw=textpage.get_text_range()
                if raw.replace('\r','') != (OLD/f'{source}-p{page}.txt').read_text():
                    raise ValueError('source evaluator text changed')
                glyphs=[]; utf16_index=normalized_index=0
                for char in raw:
                    if char!='\r':
                        if not char.isspace():
                            index=pdfium.raw.FPDFText_GetCharIndexFromTextIndex(textpage.raw,utf16_index)
                            if index < 0:raise ValueError('unmapped glyph')
                            left,bottom,right,top=textpage.get_charbox(index)
                            glyphs.append((normalized_index,(left+right)/2,pdfpage.get_height()-(bottom+top)/2))
                        normalized_index+=1
                    utf16_index+=2 if ord(char)>0xffff else 1
                points[source,page]=glyphs
            finally:
                textpage.close();pdfpage.close()
    census=json.loads((OLD/'source-census.json').read_text())
    groups=[]
    for unit in census['targets']:
        key=unit['source'],unit['physical_page']
        start,end=unit['span']['char_0based_halfopen']
        glyphs=[p for p in points[key] if start<=p[0]<end]
        native,detector=rows[key]['native'],rows[key]['detector']
        groups.append(dict(id=unit['id'],source=key[0],page=key[1],kind=unit['kind'],
            native=counts(glyphs,native),detector=counts(glyphs,detector),union=counts(glyphs,native+detector),
            union_uncovered_centers=[list(p) for p in glyphs if not any(contains(b,p[1],p[2]) for b in native+detector)]))
    negatives=[]
    for unit in census['ordinary_negatives']:
        key=unit['source'],unit['physical_page']
        lines=(OLD/f'{key[0]}-p{key[1]}.txt').read_text().splitlines(keepends=True)
        first,last=unit['lines_1based'];start=sum(map(len,lines[:first-1]));end=sum(map(len,lines[:last]))
        glyphs=[p for p in points[key] if start<=p[0]<end]
        negatives.append(dict(id=unit['id'],source=key[0],page=key[1],detector=counts(glyphs,rows[key]['detector'])))
    legacy=[]
    for unit in json.loads(CONTRACT.read_text())['units']:
        fragments=[]
        for fragment in unit['scope_fragments']:
            key=unit['source'],fragment['physical_page_1based']; box=fragment['bbox_top_left_points']
            native,detector=rows[key]['native'],rows[key]['detector']
            fragments.append(dict(page=key[1],native_locator=max([overlap(box,b) for b in native]+[0]),
                detector_locator=max([overlap(box,b) for b in detector]+[0])))
        legacy.append(dict(id=unit['unit_id'],fragments=fragments,
            all_fragments_union_locator=all(max(f['native_locator'],f['detector_locator'])>=.45 for f in fragments)))
    summary=dict(groups=44,native_full_context=sum(g['native']['all_context_glyph_centers_covered'] for g in groups),
        detector_full_context=sum(g['detector']['all_context_glyph_centers_covered'] for g in groups),
        union_full_context=sum(g['union']['all_context_glyph_centers_covered'] for g in groups),
        negatives=27,negative_any_detector_overlap=sum(n['detector']['covered_glyphs']>0 for n in negatives),
        negative_full_detector_overlap=sum(n['detector']['all_context_glyph_centers_covered'] for n in negatives),
        legacy_units=41,legacy_union_locator=sum(u['all_fragments_union_locator'] for u in legacy),
        detector_regions=sum(len(r['detector']) for r in rows.values()),
        geometric_proxy_only=True,source_quality_accepted=False)
    value=dict(summary=summary,groups=groups,negatives=negatives,legacy=legacy,
        live_cost=results['ledger'],live_seconds=results['seconds'],source_transcription_verified=False,
        producer_frozen_before_evaluator=True,holdout_reads=0,new_reconstruction_calls=0)
    d.write(HERE/'coverage.json',value)
    print(json.dumps(summary))


if __name__=='__main__':
    if sys.argv[1:]==['--freeze']:freeze();print('evaluation frozen before requests')
    elif sys.argv[1:]==['--evaluate']:evaluate()
    else:raise SystemExit('Use --freeze once before inference, or --evaluate once after.')
