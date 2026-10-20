"""Evaluate frozen context inputs using the existing source census/geometry proxy."""
import json
from pathlib import Path
import sys

import pypdfium2 as pdfium
import method as m

HERE=Path(__file__).resolve().parent
OLD=m.ROOT/'docs/research/pdf-core-stage1-2026-10-17/A-evaluator'
CONTRACT=m.ROOT/'docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json'
sys.path.insert(0,str(m.DISCOVERY))
metrics=m.load('owner_context_fixed_metrics',m.DISCOVERY/'evaluate.py')


def source_points(job):
    with pdfium.PdfDocument(m.ROOT/job['source']) as pdf:
        page=pdf[job['physical_page']-1];tp=page.get_textpage()
        try:
            raw=tp.get_text_range()
            expected=(OLD/f"{job['id']}.txt").read_text()
            if raw.replace('\r','')!=expected:raise ValueError('changed evaluator source text')
            result=[];index=utf16_index=0
            for char in raw:
                if char!='\r':
                    if not char.isspace():
                        ci=pdfium.raw.FPDFText_GetCharIndexFromTextIndex(tp.raw,utf16_index)
                        if ci<0:raise ValueError('unmapped glyph')
                        left,bottom,right,top=tp.get_charbox(ci)
                        result.append((index,(left+right)/2,page.get_height()-(bottom+top)/2))
                    index+=1
                utf16_index+=2 if ord(char)>0xffff else 1
            return result
        finally:tp.close();page.close()


def run():
    census_path=OLD/'source-census.json'
    if m.sha(census_path)!=json.loads((OLD/'source-census.freeze.json').read_text())['sha256']:
        raise ValueError('changed frozen source census')
    result=json.loads((HERE/'results.json').read_text())
    manifest=json.loads((m.DISCOVERY/'registration.json').read_text())
    inputs=[census_path,OLD/'source-census.freeze.json',CONTRACT,m.DISCOVERY/'evaluate.py',HERE/'results.json']
    m.write(HERE/'evaluation-registration.json',dict(method_sha256=m.sha(HERE/'evaluate.py'),
        inputs={str(p.relative_to(m.ROOT)):m.sha(p) for p in inputs},
        order='Routing frozen and replayed before source evaluator; no routing changes or producer feedback.',
        metric='Reuse original2pt nonspace-glyph/context proxy and old41 >=0.45 locator; not semantic accuracy.',
        model_calls=0,holdout_reads=0))
    glyphs={};rows={}
    for job in manifest['jobs']:
        source,page=job['id'].rsplit('-p',1);key=source,int(page)
        glyphs[key]=source_points(job)
    for route,jobs in result['routes'].items():
        rows[route]={key:[] for key in glyphs}
        for job in jobs:
            for crop in job['context_crops']:rows[route][job['source'],crop['page']].append(crop['bbox_top_left_points'])
    census=json.loads(census_path.read_text())
    groups=[]
    for unit in census['targets']:
        key=unit['source'],unit['physical_page'];start,end=unit['span']['char_0based_halfopen']
        points=[p for p in glyphs[key] if start<=p[0]<end]
        groups.append(dict(id=unit['id'],source=key[0],page=key[1],
            routes={name:metrics.counts(points,boxes[key]) for name,boxes in rows.items()}))
    negatives=[]
    for unit in census['ordinary_negatives']:
        key=unit['source'],unit['physical_page'];lines=(OLD/f'{key[0]}-p{key[1]}.txt').read_text().splitlines(keepends=True)
        first,last=unit['lines_1based'];start=sum(map(len,lines[:first-1]));end=sum(map(len,lines[:last]))
        points=[p for p in glyphs[key] if start<=p[0]<end]
        negatives.append(dict(id=unit['id'],source=key[0],page=key[1],
            routes={name:metrics.counts(points,boxes[key]) for name,boxes in rows.items()}))
    legacy=[]
    for unit in json.loads(CONTRACT.read_text())['units']:
        checks={}
        for route,boxes in rows.items():
            checks[route]=all(max([metrics.overlap(f['bbox_top_left_points'],b)
                for b in boxes[unit['source'],f['physical_page_1based']]]+[0])>=.45 for f in unit['scope_fragments'])
        legacy.append(dict(id=unit['unit_id'],locators=checks))
    summary={name:dict(source_groups=44,full_context_groups=sum(g['routes'][name]['all_context_glyph_centers_covered'] for g in groups),
        negatives=27,negative_any_context_overlap=sum(n['routes'][name]['covered_glyphs']>0 for n in negatives),
        negative_full_context_overlap=sum(n['routes'][name]['all_context_glyph_centers_covered'] for n in negatives),
        legacy_units=41,legacy_locators=sum(u['locators'][name] for u in legacy)) for name in rows}
    m.write(HERE/'coverage.json',dict(summary=summary,groups=groups,negatives=negatives,legacy=legacy,
        geometric_proxy_only=True,includes_unresolved_or_overlimit_proposed_inputs=True,
        source_quality_accepted=False,model_calls=0))
    print(json.dumps(summary))


if __name__=='__main__':run()
