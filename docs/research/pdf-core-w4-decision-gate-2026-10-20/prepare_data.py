"""Read existing adjudications; do not relabel or inject gold into model inputs."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,math
from PIL import Image
ROOT=Path.cwd(); P=Path(__file__).resolve().parent
R=ROOT/'docs/research/pdf-core-r1-method-2026-10-20'; LIVE=R/'live-preflight/round5-strict'
W3=ROOT/'docs/research/pdf-core-w3-structured-elements-2026-10-20/formula-code/audit'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
(P/'inputs').mkdir(exist_ok=True)
items=[];excluded=[];upstream={}
def track(p):upstream[str(p.relative_to(ROOT))]=sha(p);return load(p)
jobs={j['job_id']:j for j in track(LIVE/'jobs.json')['jobs']}
A=track(LIVE/'human-A-review-v3.json');C=track(LIVE/'human-C-review-v1.json');payloads=track(LIVE/'validated-payloads.json')
def exclude(uid,reason,origin):excluded.append({'id':uid,'reason':reason,'origin':origin})
def source_path(asset):return R/'production'/asset

def crop(page, boxes, uid):
    """Fixed geometric pad: 8 source pixels, no error-specific adjustments."""
    im=Image.open(page).convert('RGB'); coords=[]
    for b,scale in boxes:
        l,t,r,bottom=b['l'],b['t'],b['r'],b['b'];sx,sy=scale
        if b.get('coord_origin')=='BOTTOMLEFT':t,bottom=im.height-t*sy,im.height-bottom*sy
        else:t,bottom=t*sy,bottom*sy
        coords.append((l*sx,min(t,bottom),r*sx,max(t,bottom)))
    if not coords:return page,{'mode':'original_page_no_unique_bbox'}
    rect=[max(0,math.floor(min(x[0] for x in coords))-8),max(0,math.floor(min(x[1] for x in coords))-8),min(im.width,math.ceil(max(x[2] for x in coords))+8),min(im.height,math.ceil(max(x[3] for x in coords))+8)]
    assert rect[2]>rect[0] and rect[3]>rect[1]
    path=P/'inputs'/(digest(uid)+'.png');im.crop(rect).save(path)
    return path,{'mode':'union_native_provenance_plus_8px','source_page':str(page.relative_to(ROOT)),'source_sha256':sha(page),'pixel_rectangle':rect}

def add(uid,category,label,reconstruction,images,group,evidence,locator='',geometry=None):
    assert label in ('correct','minor','meaning_changed') and reconstruction.strip()
    for f in images:assert f.is_file()
    items.append({'id':uid,'category':category,'label':label,'reconstruction':reconstruction,'images':[{'path':str(f.relative_to(ROOT)),'sha256':sha(f),'size':list(Image.open(f).size)} for f in images], 'split_group':group,'adjudication_evidence':evidence,'source_locator':locator,'geometry':geometry})

# W3 entire blocks, not artificially independent TeX lines.
for name,category in [('final-selected-reviews-current.json','formula'),('code-review.json','code')]:
    rows=track(W3/name)['records']
    for r in rows:
        uid='W3:'+r['unit_id'];s=r['status']
        if s in ('ORACLE_ALIGNMENT_ERROR','UNKNOWN') or r.get('source_alignment_error'):
            exclude(uid,'Existing human source identity UNKNOWN/alignment error; no reliable semantic label',name);continue
        label='meaning_changed' if s=='CONFIRMED_BLOCKING' else ('minor' if s=='METADATA_ONLY' else 'correct')
        assert s in ('CONFIRMED_BLOCKING','METADATA_ONLY','CONFIRMED_MEANING_PRESERVED','MEANING_PRESERVED'),s
        packet=track(Path(r.get('packet_path') or r.get('packet') or W3/'packets'/(r['unit_id'].replace(':','__')+'.json')))
        native=packet['E1_items'];out='\n'.join(x['active_text'] for x in native)
        if not out.strip():exclude(uid,'No nonempty reconstruction to judge',name);continue
        views=[];gs=[];geoms=[]
        for view in r['source_images']:
            page=Path(view['path']);assert sha(page)==view['sha256'];boxes=[]
            for x in native:
                for pr in x.get('prov',[]):
                    if pr['page_no']==view['page']:boxes.append((pr['bbox'],(1.6,1.6)))
            f,g=crop(page,boxes,uid+':'+str(view['page']));views.append(f);gs.append(sha(page));geoms.append(g)
        # Multi-page groups connected later so no page can leak across split.
        add(uid,category,label,out,views,gs,{'file':str((W3/name).relative_to(ROOT)),'unit_id':r['unit_id'],'status':s,'reason':r.get('meaning_reason')},geometry=geoms)

# A exact output occurrences. Missing role/coverage and mixed group judgements are separately inventoried.
for r in A['old_A_groups']:
    exclude('R5:'+r['unit_id'],'Mixed source group/role verdict; no unique isolated model-output-to-source occurrence in frozen receipt. Do not treat F1/F3 as semantic errors or double count the additional occurrence registry.','old_A_groups')
for r in A['additional_registry']:
    uid='R5:'+r['unit_id'];kind=r['kind']
    if kind=='source_code_font':exclude(uid,'Source typography evidence only, not independent semantic judgement','additional_registry');continue
    if not r.get('observed'):
        exclude(uid,'No uniquely mapped reconstructed occurrence; missing/ambiguous typed role is not an adjudicated wrong string','additional_registry');continue
    o=r['observed'];j=jobs[r['job_id']];page=r['frozen_unit']['page'];v=next(x for x in j['binding']['views'] if x['page_no']==page);native=track(ROOT/j['baseline']);boxes=[]
    for ref in o['consume']:
        field,idx=ref[2:].split('/');node=native[field][int(idx)]
        for pr in node.get('prov',[]):
            if pr['page_no']==page:boxes.append((pr['bbox'],v['pixel_scale_xy']))
    pg=source_path(v['asset']);f,g=crop(pg,boxes,uid)
    add(uid,'formula' if kind in ('math','image_math') else 'code','correct' if r['state'].startswith('PASS') else 'meaning_changed',o['text'],[f],[sha(pg)],{'file':str((LIVE/'human-A-review-v3.json').relative_to(ROOT)),'unit_id':r['unit_id'],'reason':r['reason']},locator=r['frozen_unit']['source_context'],geometry=g)
for r in A['caption_occurrences']:
    uid='R5:'+r['unit_id'];j=jobs[r['job_id']];page=r['frozen']['page'];v=next(x for x in j['binding']['views'] if x['page_no']==page);pg=source_path(v['asset']);native=track(ROOT/j['baseline']);ref=r['observed']['ref'];field,idx=ref[2:].split('/');node=native[field][int(idx)] if int(idx)<len(native[field]) else {}
    boxes=[(pr['bbox'],v['pixel_scale_xy']) for pr in node.get('prov',[]) if pr['page_no']==page]
    # Reconstructed refs can differ from native; only crop with literal source identity, otherwise retain full page.
    if ' '.join(node.get('text','').split())!=' '.join(r['observed']['text'].split()):boxes=[]
    f,g=crop(pg,boxes,uid)
    add(uid,'caption','correct',r['observed']['text'],[f],[sha(pg)],{'file':str((LIVE/'human-A-review-v3.json').relative_to(ROOT)),'unit_id':r['unit_id'],'status':r['state'],'scope':'Literal caption only, no claim of math symbol or ownership correctness'},geometry=g)
for r in C['images']:
    j=jobs[r['description_job']];im=next(x for x in j['binding']['images'] if x['image_key']==r['image_key']);img=source_path(im['asset']);page=source_path(j['binding']['views'][0]['asset']);group=[sha(page)]
    uid='R5:description:'+str(r['image_index'])
    if r['description_state']=='BLOCKED_NOT_DELIVERED':exclude(uid,'No model response due to network loss','C_description')
    else:
        desc=dict(r['observed_description']);desc.pop('visible_text',None)
        add(uid,'description','meaning_changed' if r['description_failure_class']=='F2' else 'correct',json.dumps(desc,ensure_ascii=False),[img],group,{'file':str((LIVE/'human-C-review-v1.json').relative_to(ROOT)),'image_index':r['image_index'],'reason':r['description_reason']})
    for k,n in enumerate(r.get('numeric_receipts',[])):
        if not n.get('observed'):exclude('R5:chart:'+str(r['image_index'])+':'+str(k),'No uniquely matched observed numeric value','chart');continue
        # Only model's observed point, never human expected value or marker-center answer.
        add('R5:chart:'+str(r['image_index'])+':'+str(k),'chart','correct' if n['state']=='PASS' else 'meaning_changed',json.dumps(n['observed'],ensure_ascii=False),[img],group,{'file':str((LIVE/'human-C-review-v1.json').relative_to(ROOT)),'image_index':r['image_index'],'numeric_index':k,'state':n['state'],'scope':'Existing per-point judgement/tolerance, not new numeric threshold'})

# Union all shared ORIGINAL source pages before hashing; category-stratified allocation, label-blind.
parent={}
def find(x):
    parent.setdefault(x,x)
    if parent[x]!=x:parent[x]=find(parent[x])
    return parent[x]
def union(x,y):
    x,y=find(x),find(y)
    if x!=y:parent[max(x,y)]=min(x,y)
for r in items:
    for g in r['split_group']:union(r['split_group'][0],g)
for r in items:r['split_group']=find(r['split_group'][0])
groups=defaultdict(list)
for r in items:groups[r['split_group']].append(r)
totals=Counter(r['category'] for r in items);dev=Counter();selection={};seed='pdf-core-W4-fixed-v1-2026-10-20'
def objective(counts):return sum(((counts[c]-.30*n)/n)**2 for c,n in totals.items())
for g,rows in sorted(groups.items(),key=lambda kv:digest(seed+kv[0])):
    proposed=dev+Counter(x['category'] for x in rows)
    split='dev' if objective(proposed)<objective(dev) else 'test'
    selection[g]=split
    if split=='dev':dev=proposed
for r in items:r['split']=selection[r['split_group']]
assert len({x['id'] for x in items})==len(items)
assert not ({r['split_group'] for r in items if r['split']=='dev'}&{r['split_group'] for r in items if r['split']=='test'})
dump(P/'items-with-gold.json',{'items':items,'excluded':excluded})
# Model runner opens only this gold-free file, filtered by split.
dump(P/'model-inputs.json',{'items':[{k:v for k,v in r.items() if k not in ('label','adjudication_evidence')} for r in items]})
dump(P/'source-integrity.json',upstream)
dump(P/'split-summary.json',{'seed':seed,'rule':'Original source-page connected components; sha256-order label-blind greedy minimum category-normalized squared deviation from30%; no threshold search. No shared page across dev/test.','items':len(items),'groups':len(groups),'category_split_counts':{s:dict(Counter(r['category'] for r in items if r['split']==s)) for s in ('dev','test')},'category_label_counts':{s:{c:dict(Counter(r['label'] for r in items if r['split']==s and r['category']==c)) for c in totals} for s in ('dev','test')},'excluded':len(excluded),'exclusion_reasons':dict(Counter(r['reason'] for r in excluded))})
print(json.dumps(load(P/'split-summary.json'),ensure_ascii=False,indent=2))
