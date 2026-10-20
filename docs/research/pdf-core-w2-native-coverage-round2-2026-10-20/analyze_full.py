"""Zero-inference metrics; frozen oracle, native JSON, Markdown and PDF geometry only."""
from pathlib import Path
import bisect,collections,hashlib,json,re,unicodedata
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'analysis'
BODY_LABELS={'text','paragraph','list_item'}
def dump(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s).casefold() if c.isalnum())
def hits(text,needle):return [m.start() for m in re.finditer(re.escape(needle),text)] if needle else []
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def earliest_lis(values):
    """Indices of lexicographically earliest output-position maximum increasing subsequence."""
    lengths=[1]*len(values)
    for i in range(len(values)-1,-1,-1):
        lengths[i]=1+max((lengths[j] for j in range(i+1,len(values)) if values[j]>values[i]),default=0)
    left=max(lengths,default=0);last=-1;result=[]
    for i,v in enumerate(values):
        if v>last and lengths[i]>=left and left:
            result.append(i);last=v;left-=1
    return result

def collect(doc):
    items=[];seen=set()
    def resolve(ref):
        node=doc
        for part in ref.lstrip('#/').split('/'):node=node[int(part)] if isinstance(node,list) else node[part]
        return node
    def parents(node):
        refs=[]
        while node.get('parent'):
            ref=node['parent']['$ref']
            if ref in refs:break
            refs.append(ref);node=resolve(ref)
        return tuple(reversed(refs))
    def visit(ref,ancestors=()):
        if ref in seen:return
        seen.add(ref);x=resolve(ref);ancestors=tuple(dict.fromkeys(ancestors+parents(x)))
        if 'text' in x:
            items.append({'ref':ref,'text':x['text'],'label':x.get('label'),'layer':x.get('content_layer','body'),'prov':x.get('prov',[]),'ancestor_refs':list(ancestors),'inside_picture_or_table':any(a.startswith(('#/pictures/','#/tables/')) for a in ancestors)})
        if ref.startswith('#/tables/'):
            for n,c in enumerate(x.get('data',{}).get('table_cells',[])):
                items.append({'ref':ref+'/table_cells/'+str(n),'text':c.get('text',''),'label':'table_cell','layer':x.get('content_layer','body'),'prov':x.get('prov',[]),'ancestor_refs':list(ancestors)+[ref],'inside_picture_or_table':True})
        for child in x.get('children',[]):visit(child['$ref'],ancestors+(ref,))
    visit('#/body')
    if 'furniture' in doc:visit('#/furniture')
    return items

def is_body(item):return item['layer']=='body' and item['label'] in BODY_LABELS and not item.get('inside_picture_or_table',False)

def stream(items,predicate):
    chunks=[];spans=[];offset=0
    for item in items:
        if not predicate(item):continue
        n=norm(item['text']);chunks.append(n);spans.append((offset,offset+len(n),item));offset+=len(n)
    return ''.join(chunks),spans

def mapped_occurrences(text,spans,needle):
    return [{'offset':offset,'itemrefs':[x['ref'] for b,e,x in spans if b<offset+len(needle) and e>offset],
             'items':[{'ref':x['ref'],'label':x['label'],'layer':x['layer'],'prov':x['prov'],'ancestor_refs':x.get('ancestor_refs',[]),'inside_picture_or_table':x.get('inside_picture_or_table',False)} for b,e,x in spans if b<offset+len(needle) and e>offset]} for offset in hits(text,needle)]
def bbox_bottom(prov,dimensions):
    b=prov['bbox'];page=prov['page_no']
    if b.get('coord_origin')=='TOPLEFT':
        h=dimensions[page]['height'];return [b['l'],h-b['b'],b['r'],h-b['t']]
    return [b['l'],b['b'],b['r'],b['t']]
def overlap(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    area=max(0,a[2]-a[0])*max(0,a[3]-a[1]);return inter/area if area else 0

def score(job,op):
    oracle=json.loads(op.read_text());trusted=[a for a in oracle['anchors'] if a['status']=='TRUSTED'];prose=[a for a in trusted if a['kind']=='prose'];base=ROOT/'jobs'/job['id'];target=OUT/job['id'];conversion=json.loads((base/'conversion.json').read_text()) if (base/'conversion.json').exists() else {}
    summary={'id':job['id'],'set':job['set'],'family':oracle['template']['family'],'title':job['title'],'selected_pages':job['last']-job['first']+1,'conversion_status':conversion.get('status','pending'),'oracle':oracle['summary']['oracle'],'oracle_sha256':sha(op),'trusted_prose':len(prose),'oracle_counts':oracle['summary']['counts'],'F01_Q4':'UNKNOWN','F02_Q4':'UNKNOWN','Q4_basis':'Candidates are not semantic verdicts; entire-document completeness not manually established.'}
    if not (base/'document.json').exists() or not (base/'document.md').exists():
        summary.update(metric_status='MISSING_OUTPUT_UNKNOWN',missing=None,duplicate=None,md_lis_outside=None,md_lis_ratio=None,mixed_paragraphs=None,furniture_contamination=None,body_or_md_found=None,anchor_coverage=None);dump(target/'metrics.json',summary);dump(target/'pages.json',[{'page':p,'evaluation_status':'MISSING_OUTPUT_UNKNOWN','missing':None,'duplicate':None,'md_lis_outside':None,'F01_Q4':'UNKNOWN','F02_Q4':'UNKNOWN'} for p in range(job['first'],job['last']+1)]);dump(target/'anchors.json',[{'anchor_id':a['id'],'kind':a['kind'],'text':a['text'],'pdf_pages':a['pdf_pages'],'evaluation_status':'MISSING_OUTPUT_UNKNOWN','found_body_or_markdown':None} for a in trusted]);dump(target/'candidates.json',[]);return summary,[]
    doc=json.loads((base/'document.json').read_text());md=norm((base/'document.md').read_text());items=collect(doc);body,bsp=stream(items,is_body);visible,vsp=stream(items,lambda x:x['layer']=='body');alltext,asp=stream(items,lambda x:True);byref={x['ref']:x for x in items}
    geometrypath=ROOT/'diagnostics/geometry'/f'{job["id"]}.json';geometry=json.loads(geometrypath.read_text()) if geometrypath.exists() else {};locations=geometry.get('anchor_locations',{});candidates=[];rows=[];proseranks={a['id']:i for i,a in enumerate(prose)}
    def candidate(kind,**data):
        c={'id':job['id']+':'+kind+':'+str(len(candidates)).zfill(5),'job_id':job['id'],'kind':kind,'machine_candidate':True,'Q4':'UNKNOWN',**data};candidates.append(c);return c
    for a in trusted:
        n=a['normalized'];bh=mapped_occurrences(body,bsp,n);vh=mapped_occurrences(visible,vsp,n);ah=mapped_occurrences(alltext,asp,n);mh=hits(md,n)
        row={'anchor_id':a['id'],'kind':a['kind'],'text':a['text'],'normalized':n,'source_order':a['order'],'source_file':a['source_file'],'source_line':a['source_line'],'source_offset':a['source_offset'],'pdf_pages':a['pdf_pages'],'source_location':locations.get(a['id']),'native_body':bh,'native_visible':vh,'native_all_layers':ah,'markdown_offsets':mh,'found_body_or_markdown':bool(bh or mh),'max_channel_occurrences':max(len(bh),len(mh))}
        rows.append(row)
        if a['kind']=='prose':
            if not bh and not mh:candidate('missing_anchor',anchor_ids=[a['id']],pages=a['pdf_pages'],text=a['text'],native_visible_occurrences=vh,native_all_layers_occurrences=ah)
            if row['max_channel_occurrences']>1:candidate('duplicate_anchor',anchor_ids=[a['id']],pages=a['pdf_pages'],text=a['text'],native_body_occurrences=bh,markdown_offsets=mh)
            if not bh and (vh or ah):candidate('prose_role_or_layer_mismatch',anchor_ids=[a['id']],pages=a['pdf_pages'],text=a['text'],native_occurrences=vh or ah)
        else:
            expected='caption' if a['kind']=='caption' else 'footnote';correct=[x for x in items if x['layer']=='body' and x['label']==expected and n in norm(x['text'])]
            separate_picture_text=[x for x in items if a['kind']=='caption' and x['layer']=='body' and x.get('inside_picture_or_table') and n in norm(x['text']) and x['label']!='caption']
            row['correct_label_itemrefs']=[x['ref'] for x in correct]
            row['picture_text_separate_itemrefs']=[x['ref'] for x in separate_picture_text]
            if bh:candidate(a['kind']+'_in_body',anchor_ids=[a['id']],pages=a['pdf_pages'],text=a['text'],occurrences=bh)
            if not (vh or mh):candidate(a['kind']+'_missing',anchor_ids=[a['id']],pages=a['pdf_pages'],text=a['text'])
            elif not correct and not separate_picture_text:candidate(a['kind']+'_role_not_separate',anchor_ids=[a['id']],pages=a['pdf_pages'],text=a['text'],native_occurrences=vh)
    prose_rows=[r for r in rows if r['kind']=='prose']
    def order_metrics(channel):
        key='markdown_offsets' if channel=='md' else 'native_body';aligned=[r for r in prose_rows if len(r[key])==1];aligned.sort(key=lambda r:r[key][0] if channel=='md' else r[key][0]['offset']);seq=[proseranks[r['anchor_id']] for r in aligned];keep=set(earliest_lis(seq));outside=[r for i,r in enumerate(aligned) if i not in keep]
        for r in outside:candidate(channel+'_lis_outside',anchor_ids=[r['anchor_id']],pages=r['pdf_pages'],text=r['text'],output_position=r[key][0],source_rank=proseranks[r['anchor_id']])
        return {'aligned':len(aligned),'lis_length':len(keep),'outside':len(outside),'ratio':len(outside)/len(aligned) if aligned else None,'outside_anchor_ids':[r['anchor_id'] for r in outside],'output_order_anchor_ids':[r['anchor_id'] for r in aligned]}
    md_order=order_metrics('md');native_order=order_metrics('native')
    mixed=[]
    if oracle['summary']['oracle']!='textlayer_fallback':
        for item in items:
            if not is_body(item):continue
            matches=[r for r in prose_rows if r['normalized'] in norm(item['text'])]
            witnesses=[(a,b) for i,a in enumerate(matches) for b in matches[i+1:] if (a['source_file'],a['source_offset'])!=(b['source_file'],b['source_offset']) and abs(proseranks[a['anchor_id']]-proseranks[b['anchor_id']])>=5]
            if witnesses:
                a,b=witnesses[0];c=candidate('mixed_paragraph',anchor_ids=[a['anchor_id'],b['anchor_id']],pages=sorted({p['page_no'] for p in item['prov']}),itemref=item['ref'],text=item['text'],prov=item['prov'],source_rank_gap=abs(proseranks[a['anchor_id']]-proseranks[b['anchor_id']]));mixed.append(c)
    jumping=[];jump_unknown=0;jump_evaluable=0
    for page in range(job['first'],job['last']+1):
        local=[r for r in prose_rows if (loc:=locations.get(r['anchor_id'])) and loc.get('pages')==[page] and loc.get('column') in ('L','R')]
        local.sort(key=lambda r:r['source_order']);cols=[locations[r['anchor_id']]['column'] for r in local]
        if not ('L' in cols and 'R' in cols):continue
        source_valid=max(i for i,c in enumerate(cols) if c=='L')<min(i for i,c in enumerate(cols) if c=='R')
        if not source_valid:jump_unknown+=1;continue
        jump_evaluable+=1
        aligned=[r for r in local if len(r['markdown_offsets'])==1];aligned.sort(key=lambda r:r['markdown_offsets'][0]);runs=[]
        for r in aligned:
            col=locations[r['anchor_id']]['column']
            if not runs or runs[-1][0]!=col:runs.append((col,[r]))
            else:runs[-1][1].append(r)
        for i in range(len(runs)-2):
            if [x[0] for x in runs[i:i+3]]!=['L','R','L']:continue
            a,b,c=runs[i][1][-1],runs[i+1][1][0],runs[i+2][1][0]
            if c['source_order']>a['source_order']:jumping.append(candidate('right_column_inserts_left',anchor_ids=[a['anchor_id'],b['anchor_id'],c['anchor_id']],pages=[page],texts=[a['text'],b['text'],c['text']]))
    furniture=[];seen=set();dims={p['page']:p['page_dimensions'] for p in geometry.get('pages',[])}
    for f in geometry.get('furniture_candidates',[]):
        unique=(f['page'],tuple(f.get('raw_char_range',[])))
        if unique in seen:continue
        seen.add(unique);needle=norm(f['text'])
        if not needle:continue
        page_dims=dims.get(f['page']);box=f['bbox']
        margin_eligible=bool(page_dims and (box[0]<45 or box[2]>page_dims['width']-45 or box[1]<50 or box[3]>page_dims['height']-45))
        for item in items:
            if not is_body(item) or needle not in norm(item['text']):continue
            relevant=[p for p in item['prov'] if p['page_no']==f['page']]
            if any(overlap(f['bbox'],bbox_bottom(p,dims))>=0.2 for p in relevant):furniture.append(candidate('furniture_in_body',pages=[f['page']],text=f['text'],candidate_reasons=f['candidate_reasons'],eligible_pdf_margin=margin_eligible,source_identity_status='PDF_MARGIN_CANDIDATE' if margin_eligible else 'NOT_PAGE_MARGIN_IDENTITY_UNCERTAIN',source_bbox=f['bbox'],source_raw_char_range=f.get('raw_char_range'),itemref=item['ref'],item_text=item['text'],prov=item['prov']))
    def cnt(kind):return sum(c['kind']==kind for c in candidates)
    classes={}
    for kind in ('caption','footnote'):
        rr=[r for r in rows if r['kind']==kind];classes[kind]={'trusted':len(rr),'found_visible_or_md':sum(bool(r['native_visible'] or r['markdown_offsets']) for r in rr),'correct_role':sum(bool(r['correct_label_itemrefs']) for r in rr),'picture_text_separate':sum(bool(r.get('picture_text_separate_itemrefs')) for r in rr),'in_body':cnt(kind+'_in_body'),'missing':cnt(kind+'_missing'),'role_not_separate':cnt(kind+'_role_not_separate')}
    summary.update(metric_status='SCORED_CANDIDATES',body_or_md_found=sum(r['found_body_or_markdown'] for r in prose_rows),anchor_coverage=sum(r['found_body_or_markdown'] for r in prose_rows)/len(prose_rows) if prose_rows else None,missing=cnt('missing_anchor'),missing_all_native_or_md=sum(not r['found_body_or_markdown'] and not r['native_all_layers'] for r in prose_rows),missing_body_or_md_but_visible=sum(not r['found_body_or_markdown'] and bool(r['native_all_layers']) for r in prose_rows),duplicate=cnt('duplicate_anchor'),role_or_layer_mismatch=cnt('prose_role_or_layer_mismatch'),md_order=md_order,native_order=native_order,md_lis_outside=md_order['outside'],md_lis_ratio=md_order['ratio'],mixed_paragraphs=len(mixed) if oracle['summary']['oracle']!='textlayer_fallback' else None,mixed_paragraph_status='UNKNOWN_TEXTLAYER_FALLBACK' if oracle['summary']['oracle']=='textlayer_fallback' else 'CANDIDATES',column_jumps=len(jumping) if oracle['summary']['oracle']!='textlayer_fallback' else None,column_jump_status='UNKNOWN_TEXTLAYER_FALLBACK' if oracle['summary']['oracle']=='textlayer_fallback' else 'CANDIDATES',column_jump_evaluable_source_pages=jump_evaluable,column_jump_source_order_unknown_pages=jump_unknown,furniture_contamination=sum(c['eligible_pdf_margin'] for c in furniture),furniture_raw_body_matches=len(furniture),furniture_reason_breakdown={reason:{'raw':sum(reason in c['candidate_reasons'] for c in furniture),'page_margin_eligible':sum(reason in c['candidate_reasons'] and c['eligible_pdf_margin'] for c in furniture)} for reason in sorted({r for c in furniture for r in c['candidate_reasons']})},furniture_source_candidates_deduplicated=len(seen),classes=classes,candidate_count=len(candidates),geometry_sha256=sha(geometrypath) if geometrypath.exists() else None)
    pages=[]
    for page in range(job['first'],job['last']+1):
        local=[r for r in prose_rows if page in r['pdf_pages']];alerts=[c for c in candidates if page in c.get('pages',[])]
        pages.append({'page':page,'trusted_prose_overlapping_page':len(local),'body_or_md_found':sum(r['found_body_or_markdown'] for r in local),'missing':sum(c['kind']=='missing_anchor' for c in alerts),'duplicate':sum(c['kind']=='duplicate_anchor' for c in alerts),'md_lis_outside':sum(c['kind']=='md_lis_outside' for c in alerts),'mixed_paragraph_candidates':sum(c['kind']=='mixed_paragraph' for c in alerts),'furniture_margin_candidates':sum(c['kind']=='furniture_in_body' and c.get('eligible_pdf_margin',False) for c in alerts),'candidate_ids':[c['id'] for c in alerts],'F01_Q4':'UNKNOWN','F02_Q4':'UNKNOWN','counting_note':'Cross-page anchors overlap and count on each involved page; page counts are not additive across pages.'})
    dump(target/'pages.json',pages);dump(target/'anchors.json',rows);dump(target/'metrics.json',summary);dump(target/'candidates.json',candidates);return summary,candidates

def main():
    assert earliest_lis([2,1,3])==[0,2]
    assert earliest_lis([2,3,1,4])==[0,1,3]
    assert earliest_lis([])==[]
    assert hits(norm('not allowed not allowed'),norm('not allowed'))==[0,10]
    assert overlap([0,0,10,10],[5,5,10,10])==.25
    synthetic={'body':{'children':[{'$ref':'#/pictures/0'}]},'pictures':[{'children':[{'$ref':'#/texts/0'}]}],'texts':[{'text':'Inside figure text','label':'text','content_layer':'body','children':[]}]}
    assert not is_body(collect(synthetic)[0])
    jobs=json.loads((ROOT/'jobs.json').read_text())['jobs'];index=json.loads((ROOT/'oracle/job-index.json').read_text());seal=json.loads((ROOT/'oracle/freeze.json').read_text())
    for rel,want in seal['files'].items():assert sha(ROOT/'oracle'/rel)==want,('oracle seal changed',rel)
    summaries=[];catalog=[]
    for j in jobs:
        s,c=score(j,Path(index[j['id']]));summaries.append(s);catalog.extend(c);print(j['id'],s['metric_status'],s.get('missing'),s.get('md_lis_outside'),flush=True)
    dump(OUT/'summary.json',summaries);dump(OUT/'candidate-catalog.json',catalog);dump(OUT/'run.json',{'analyzer_sha256':sha(Path(__file__)),'oracle_seal_sha256':sha(ROOT/'oracle/freeze.json'),'scored_jobs':sum(s['metric_status']=='SCORED_CANDIDATES' for s in summaries),'total_jobs':len(jobs),'machine_candidates_only':True,'q4_default':'UNKNOWN'})
if __name__=='__main__':main()
