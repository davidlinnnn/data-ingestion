"""Frozen owner/context replay. No inference, transcription repair or writeback."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import sys
import unicodedata

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DISCOVERY=ROOT/'docs/research/pdf-core-page-discovery-2026-10-17'
INVENTORY=ROOT/'docs/research/pdf-core-stage1-followup-2026-10-17/A/inventory.json'
RULE=dict(max_owners_per_job=4,max_pages_per_job=2,max_fraction_per_page=.5,
          max_jobs_per_route=64,max_crop_pixels_in_source_page_equivalents=1,
          mapping='positive intersection and either rectangle center contained; no geometry recursion, padding or nearest-owner fallback',
          merge='connected components of shared target owners; bound checked after merge',
          native_gate='Existing Unicode Sm/Greek/math-alphanumeric or _=<>^{} signal, plus native code/formula and existing pure-formula-picture disposition',
          replacement='Only explicit target owners may be consumed. Other intersecting owners are context-only. Mixed component bindings remain unresolved.')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def sha(path):return sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)


def gate(text):
    # Reuse the registered 2026-10-15 character rule, without filename/case rules.
    return any(unicodedata.category(c)=='Sm' or '\u0370'<=c<='\u03ff'
               or '\U0001d400'<=c<='\U0001d7ff' or c in '_=<>^{}' for c in text)


def intersects(a,b):return min(a[2],b[2])>max(a[0],b[0]) and min(a[3],b[3])>max(a[1],b[1])


def inside(box,x,y):return box[0]<=x<=box[2] and box[1]<=y<=box[3]


def matches(a,b):
    return intersects(a,b) and (inside(a,(b[0]+b[2])/2,(b[1]+b[3])/2)
                                or inside(b,(a[0]+a[2])/2,(a[1]+a[3])/2))


def merge(seeds):
    result=[]
    for seed in seeds:
        current=deepcopy(seed)
        changed=True
        while changed:
            changed=False
            for other in result[:]:
                if set(current['owners']) & set(other['owners']):
                    current['owners']=sorted(set(current['owners'])|set(other['owners']))
                    current['reasons']=sorted(set(current['reasons'])|set(other['reasons']))
                    result.remove(other);changed=True
        result.append(current)
    return sorted(result,key=lambda r:r['owners'])


def catalog(source,discovery):
    primary={r['target_ref']:r for r in source['rows'] if '/data/table_cells/' not in r['target_ref']}
    owners={}
    for ref,row in primary.items():
        if row['responsibility']=='unresolved':continue
        if row['responsibility']=='picture' and ref.startswith('#/texts/'):continue
        fragments=[]
        for prov in row['native_provenance']:
            page=next(j for j in discovery['jobs'] if j['id']==f"{source['source']}-p{prov['page_no']}")
            box=load_discovery.native_box(prov,page['size_points'])
            fragments.append(dict(page=prov['page_no'],bbox=box))
        if fragments:
            owners[ref]=dict(ref=ref,label=row['native_label'],parent=row['parent_ref'],
                responsibility=row['responsibility'],method=row.get('method'),
                pure_formula_picture=row.get('disposition')=='formula_picture_envelope',fragments=fragments,
                native_signal=(row['native_label'] in {'code','formula'} or gate(row.get('native_text') or '')
                               or row.get('disposition')=='formula_picture_envelope'))
    for row in source['rows']:
        if '/data/table_cells/' in row['target_ref'] and gate(row.get('native_text') or ''):
            owners[row['parent_ref']]['native_signal']=True
    return owners


def context(group,owners,page_jobs,raw,adapter):
    refs=group['owners'];selected=[owners[r] for r in refs]
    pages=sorted({f['page'] for owner in selected for f in owner['fragments']})
    reasons=[];crops=[]
    if len(refs)>RULE['max_owners_per_job']:reasons.append('owner_limit')
    if len(pages)>RULE['max_pages_per_job']:reasons.append('page_limit')
    for number in pages:
        page=page_jobs[number];w,h=page['pixels_wh']
        boxes=[f['bbox'] for owner in selected for f in owner['fragments'] if f['page']==number]
        box=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
        pixels=[math.floor(box[0]*2),math.floor(box[1]*2),min(w,math.ceil(box[2]*2)),min(h,math.ceil(box[3]*2))]
        area=(pixels[2]-pixels[0])*(pixels[3]-pixels[1])
        if area/(w*h)>RULE['max_fraction_per_page']:reasons.append('page_area_limit')
        readonly=sorted(r for r,owner in owners.items() if r not in refs
            and any(f['page']==number and intersects(box,f['bbox']) for f in owner['fragments']))
        crops.append(dict(page=number,pixels=pixels,bbox_top_left_points=box,pixel_area=area,
            page_fraction=area/(w*h),context_only_owner_refs=readonly))
    kinds={owner['responsibility'] for owner in selected}
    binding='unresolved';binding_reason='mixed_or_unsupported_component'
    if kinds=={'body'}:
        try:
            adapter.scope(raw,refs)
            binding='public_core_ordered_scope_available';binding_reason=None
        except (ValueError,KeyError,TypeError,IndexError) as error:binding_reason=type(error).__name__
    elif len(refs)==1 and selected[0]['pure_formula_picture']:
        binding='existing_pure_formula_picture_seam';binding_reason=None
    elif kinds=={'table'} and len(refs)==1:
        binding='B_responsibility_not_reopened';binding_reason='table_source_quality_and_crosspage_still_pending'
    elif kinds=={'caption'} and len(refs)==1:
        binding='existing_plain_caption_seam';binding_reason='typed_inline_not_assumed'
    return dict(target_owner_refs=refs,reasons=group['reasons'],context_crops=crops,
        input_within_bounds=not reasons,budget_failures=sorted(set(reasons)),
        binding=binding,binding_limit=binding_reason,source_quality_verified=False,
        replacement_scope='explicit owners only; input context grants no extra write permission',
        planned_request_count=1,planned_images=len(crops),planned_pixel_area=sum(c['pixel_area'] for c in crops))


def freeze():
    seal=json.loads((DISCOVERY/'live-verification.json').read_text())
    for name,expected in seal['files'].items():
        if sha(DISCOVERY/name)!=expected:raise ValueError('changed discovery evidence')
    files=[INVENTORY,DISCOVERY/'registration.json',DISCOVERY/'live/results.json',
        ROOT/'docs/research/pdf-core-g2-inline-2026-10-15/inputs/prepare.py',
        ROOT/'docs/research/pdf-core-stage1-followup-2026-10-17/A/method.py']
    files.extend(sorted((DISCOVERY/'live').glob('*/binding.json')))
    write(HERE/'registration.json',dict(rule=RULE,methods={p.name:sha(p) for p in (HERE/'method.py',HERE/'test_method.py')},
        inputs={str(p.relative_to(ROOT)):sha(p) for p in files},
        scope='All eight DEV pages and all40 saved proposals; no case bbox/answer input to routing',
        budgets=dict(model_calls=0,api_calls=0,downloads=0,installs=0,holdout_reads=0),
        status='Routing feasibility only. Bounds are research ceilings, not product acceptance criteria.'))


def run():
    reg=json.loads((HERE/'registration.json').read_text())
    if reg['rule']!=RULE:raise ValueError('changed routing rule')
    for name,expected in reg['methods'].items():
        if sha(HERE/name)!=expected:raise ValueError('changed method')
    for name,expected in reg['inputs'].items():
        if sha(ROOT/name)!=expected:raise ValueError('changed source input')
    inventory=json.loads(INVENTORY.read_text())
    discovery=json.loads((DISCOVERY/'registration.json').read_text())
    adapter=load('owner_context_existing_adapter',ROOT/'docs/research/pdf-core-stage1-followup-2026-10-17/A/method.py')
    routes={name:[] for name in ('native_only','native_plus_discovery')};mapping=[]
    for source in sorted(inventory['sources'],key=lambda s:s['source']):
        owners=catalog(source,discovery)
        pages={j['physical_page']:j for j in discovery['jobs'] if j['id'].startswith(source['source']+'-p')}
        raw=json.loads((ROOT/source['document_path']).read_text())
        native=[dict(owners=[r],reasons=['native_signal']) for r,v in owners.items() if v['native_signal']]
        extra=[]
        for page_no,page in pages.items():
            binding=json.loads((DISCOVERY/'live'/page['id']/'binding.json').read_text())
            for candidate in binding['candidates']:
                refs=sorted(r for r,owner in owners.items()
                    if any(f['page']==page_no and matches(candidate['bbox_top_left_points'],f['bbox']) for f in owner['fragments']))
                mapping.append(dict(source=source['source'],candidate_id=candidate['candidate_id'],page=page_no,
                    selected_owner_refs=refs,status='matched' if refs else 'unresolved_no_native_owner',
                    original_detector_bbox=candidate['bbox_top_left_points']))
                if refs:extra.append(dict(owners=refs,reasons=[candidate['candidate_id']]))
        for route,seeds in (('native_only',native),('native_plus_discovery',native+extra)):
            for number,group in enumerate(merge(seeds)):
                value=context(group,owners,pages,raw,adapter)
                value.update(source=source['source'],job_id=f"{source['source']}:{number}")
                routes[route].append(value)
    total_page_pixels=sum(j['pixels_wh'][0]*j['pixels_wh'][1] for j in discovery['jobs'])
    summaries={}
    for route,jobs in routes.items():
        total=sum(j['planned_pixel_area'] for j in jobs)
        summaries[route]=dict(jobs=len(jobs),images=sum(j['planned_images'] for j in jobs),
            summed_input_pixels=total,source_page_equivalents=total/total_page_pixels,
            bounded_jobs=sum(j['input_within_bounds'] for j in jobs),
            budget_exceeded=len(jobs)>RULE['max_jobs_per_route'] or total>total_page_pixels,
            bindings={kind:sum(j['binding']==kind for j in jobs) for kind in sorted({j['binding'] for j in jobs})})
    result=dict(rule=RULE,mapping=mapping,routes=routes,summaries=summaries,
        raw_candidates=len(mapping),unmatched=sum(not m['selected_owner_refs'] for m in mapping),
        new_model_calls=0,source_quality_verified=False,all_native_candidates_retained=True,
        context_only_is_not_consumption=True,new_reconstruction_calls=0)
    write(HERE/'results.json',result)
    print(json.dumps(dict(raw_candidates=result['raw_candidates'],unmatched=result['unmatched'],routes=summaries)))


load_discovery=load('owner_context_source_geometry',DISCOVERY/'discovery.py')

if __name__=='__main__':
    if sys.argv[1:]==['--freeze']:freeze();print('zero-inference routing method frozen')
    elif sys.argv[1:]==['--run']:run()
    else:raise SystemExit('Use --freeze once before replay or --run once; no network mode.')
