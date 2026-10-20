"""E0 image: frozen-source caption linking + independent raster bbox geometry. Zero inference."""
import pathlib,json,hashlib,collections,importlib.util,datetime,unicodedata
ROOT=pathlib.Path(__file__).resolve().parent;REPO=ROOT.parents[3];W3=ROOT.parent
R3=REPO/'docs/research/pdf-core-w2-native-coverage-round3-2026-10-20';R4=REPO/'docs/research/pdf-core-w2-native-coverage-round4-2026-10-20'
assert (W3/'oracle-freeze.json').exists(), 'global source oracle freeze required'
sp=importlib.util.spec_from_file_location('w2_mapper',R4/'mapper/map_documents.py');mapper=importlib.util.module_from_spec(sp);sp.loader.exec_module(mapper)
norm=lambda s:''.join(c for c in unicodedata.normalize('NFKD',s or '').casefold() if c.isalnum())
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def getref(x):return x if isinstance(x,str) else x.get('$ref',x.get('cref'))
def box(p):
 b=p['bbox'];return [b['l'],b['b'],b['r'],b['t']] if b.get('coord_origin')=='BOTTOMLEFT' else None

def overlap(a,b):return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
def contains(a,b):return all([a[0]<=b[0]+1e-6,a[1]<=b[1]+1e-6,a[2]>=b[2]-1e-6,a[3]>=b[3]-1e-6])
def ancestors(ref,index):
 out=[];seen=set()
 while ref in index and ref not in seen:
  seen.add(ref);par=index[ref].get('parent');ref=getref(par) if par else None
  if ref:out.append(ref)
 return out

def caption_matches(cap,doc,index,md,mapped_units):
 needles=sorted({norm(cap['text']),*(e['normalized'] for e in cap['page_evidence'])},key=len,reverse=True);needles=[n for n in needles if len(n)>=12]
 out=[]
 for it in doc['texts']:
  if not any(q['page_no'] in cap['pdf_pages'] for q in it.get('prov',[])):continue
  active=norm(it.get('text',''));original=norm(it.get('orig',''));matched=[n for n in needles if n in active or n in original]
  if not matched:continue
  picrefs=[r for r in ancestors(it['self_ref'],index) if r.startswith('#/pictures/')]
  for pic in doc['pictures']:
   if it['self_ref'] in [getref(r) for r in pic.get('captions',[])]:picrefs.append(pic['self_ref'])
  picrefs=sorted(set(picrefs));picrefs=[r for r in picrefs if any(q['page_no'] in cap['pdf_pages'] for q in index[r].get('prov',[]))]
  rawhit=any(n in norm(md) for n in matched);unit=mapped_units.get(it['self_ref'],{});maphit=any(n in norm(unit.get('text','')) for n in matched)
  out.append({'itemref':it['self_ref'],'label':it.get('label'),'parent':it.get('parent'),'pages':[q['page_no'] for q in it.get('prov',[])],'prov':it.get('prov',[]),'text':it.get('text',''),'orig':it.get('orig',''),'matched_fragment':max(matched,key=len),'active_text_match':any(n in active for n in matched),'orig_match':any(n in original for n in matched),'picture_refs':picrefs,'RAW_markdown_fragment_found':rawhit,'MAPPED_unit_fragment_found':maphit,'MAPPED_channel':unit.get('channel'),'MAPPED_source':unit.get('source')})
 return out

def main():
 oraclepath=ROOT/'oracle.json';oracle=json.loads(oraclepath.read_text());freeze=json.loads((ROOT/'freeze.json').read_text());assert sha(oraclepath)==freeze['files']['oracle.json']
 geo=json.loads((ROOT/'pdf-raster-geometry.json').read_text());gmap={p['job_id']:p for p in geo['papers']};inputs=json.loads((W3/'E0-inputs.json').read_text());imap={j['job_id']:j for j in inputs['jobs']};familymap={j['job_id']:j['family'] for j in json.loads((W3/'source-manifest.json').read_text())['jobs']};docs=[]
 for paper in oracle['papers']:
  jid=paper['job_id'];inp=imap[jid];path=REPO/inp['selected_document'];mpath=REPO/inp['selected_markdown'];doc=json.loads(path.read_text());md=mpath.read_text();assert sha(path)==inp['selected_document_sha256'];mapped=mapper.map_document(doc);units={u['ref']:u for u in mapped['units']};index={it['self_ref']:it for k in ['texts','groups','pictures','tables','key_value_items','form_items'] for it in doc.get(k,[])}
  pics=[]
  for pic in doc['pictures']:
   regions=[{'page':p['page_no'],'bbox':box(p)} for p in pic.get('prov',[]) if box(p)];children=[it for it in doc['texts'] if pic['self_ref'] in ancestors(it['self_ref'],index) and it.get('label') not in ['caption','footnote']];pics.append({'ref':pic['self_ref'],'regions':regions,'caption_refs':[getref(r) for r in pic.get('captions',[])],'image_payload_present':bool(pic.get('image')),'raw_picture':pic,'native_text_child_refs':[x['self_ref'] for x in children],'native_text_child_nonspace_chars':sum(len(''.join(c for c in x.get('text','') if not c.isspace())) for x in children),'RAW_substantial_children_in_MD':sum(len(norm(x.get('text','')))>30 and norm(x['text']) in norm(md) for x in children),'MAPPED_children_units':sum(x['self_ref'] in units for x in children),'MAPPED_children_channels':sorted({units[x['self_ref']]['channel'] for x in children if x['self_ref'] in units})})
  caps={c['id']:c for c in paper['captions']};cresults={cid:caption_matches(c,doc,index,md,units) for cid,c in caps.items() if c['selected_scope']=='IN_SCOPE'};figrows=[]
  for fig in paper['figures']:
   capids=fig['caption_ids'];ms=[m for cid in capids for m in cresults.get(cid,[])];linked=sorted({r for m in ms for r in m['picture_refs']});pages=fig['pdf_pages'];pagepics=[p for p in pics if any(r['page'] in pages for r in p['regions'])]
   if fig['selected_scope']!='IN_SCOPE':status=fig['selected_scope'];reason='Frozen source scope or location unknown.'
   elif fig.get('conditional_uncertain'):status='UNKNOWN_SOURCE_CONDITIONAL';reason='Lexical conditional context not executed; source visible presence uncertain.'
   elif linked:status='CAPTION_LINKED_PICTURE';reason='Frozen source caption fragment exact match in same-page native item, explicit parent/caption graph gives picture relation. This is structural linkage, not visual identity certification.'
   elif not pagepics:status='NOT_DETECTED_NO_PICTURE_ON_SOURCE_PAGE';reason='Independently located source figure page has no native picture items.'
   elif ms:status='UNKNOWN_CAPTION_PRESENT_NOT_LINKED';reason='Source caption exists in native text but lacks an explicit same-page picture parent/caption ref; same-page picture alone is insufficient.'
   else:status='UNKNOWN_CAPTION_MATCH_OR_CHILD_MAPPING';reason='No unique explicit caption→picture relation; do not assign source figure from page alone.'
   figrows.append({'source_id':fig['id'],'kind':fig['kind'],'parent_id':fig['parent_id'],'source':fig['source'],'source_caption_ids':capids,'source_pages':pages,'scope':fig['selected_scope'],'status':status,'reason':reason,'picture_refs':linked,'source_page_picture_refs':[p['ref'] for p in pagepics],'caption_matches':ms,'source_includegraphics_count':len(fig['includegraphics_ids']),'RAW':{'caption_fragment_delivered':any(m['RAW_markdown_fragment_found'] for m in ms),'linked_picture_refs':linked},'MAPPED':{'caption_fragment_delivered':any(m['MAPPED_unit_fragment_found'] for m in ms),'linked_picture_refs':linked},'vector_or_source_image_identity':'UNKNOWN unless independent raster objects/source image identity or visual audit resolves it'})
  raster=[]
  for pg in gmap[jid]['pages']:
   for obj in pg['raster_objects']:
    b=obj['bbox_bottomleft'];same=[p for p in pics if any(r['page']==pg['page'] for r in p['regions'])];full=[];partial=[]
    for pic in same:
     for r in pic['regions']:
      if r['page']!=pg['page']:continue
      if contains(r['bbox'],b):full.append(pic['ref'])
      elif overlap(r['bbox'],b)>0:partial.append({'picture_ref':pic['ref'],'intersection_over_raster_bbox':overlap(r['bbox'],b)/obj['bbox_area'] if obj['bbox_area'] else None,'picture_bbox':r['bbox']})
    if not obj['page_intersection_area']:st='OUTSIDE_PAGE'
    elif full:st='FULL_RASTER_OBJECT_BBOX_CONTAINED'
    elif partial:st='PARTIAL_RASTER_OBJECT_BBOX_INTERSECTION_VISIBLE_CROP_UNKNOWN'
    else:st='NO_PICTURE_BBOX_INTERSECTION_VISIBLE_EXISTENCE_UNKNOWN'
    raster.append({'source_object_id':obj['id'],'page':pg['page'],'source_bbox':b,'pixel_size':obj['pixel_size'],'source_visibility':obj['source_visibility'],'clip_path_count':obj['clip_path_count'],'ancestor_clip_path_count':obj['ancestor_clip_path_count'],'status':st,'full_picture_refs':sorted(set(full)),'partial_matches':partial,'RAW_status':st,'MAPPED_status':st,'not_claimed':'No raster payload was rendered/exported. Bbox containment is geometry only; noncontained clipped or occluded objects require visual/clip evidence before declaring lost visible content.'})
  original=json.loads((pathlib.Path(inp['original_conversion_directory'])/'document.json').read_text());clamps=[]
  for pic in doc['pictures']:
   op=next((x for x in original['pictures'] if x['self_ref']==pic['self_ref']),None)
   if op and op.get('prov')!=pic.get('prov'):clamps.append({'ref':pic['self_ref'],'original_prov':op.get('prov'),'selected_prov':pic.get('prov'),'note':'Loader/postprocessing provenance differs; do not label as model improvement.'})
  row={'job_id':jid,'family':familymap[jid],'frozen_jobs_family':paper['family'],'family_source':'W3 source-manifest (pre-E0 source-only classification)','pages':inp['pages'],'source_status':paper['status'],'selected_document':str(path),'selected_document_sha256':sha(path),'selected_markdown_sha256':sha(mpath),'source_figures':figrows,'caption_matches_by_source_id':cresults,'pictures':pics,'raster_object_checks':raster,'loader_picture_bbox_changes':clamps,'mapper_selfcheck':mapped['selfcheck'],'summary':{'source_containers':len(figrows),'source_status_counts':dict(collections.Counter(r['status'] for r in figrows)),'pictures':len(pics),'raster_status_counts':dict(collections.Counter(r['status'] for r in raster)),'images_payload_present':sum(p['image_payload_present'] for p in pics),'loader_picture_bbox_changes':len(clamps)}};docs.append(row);print(jid,row['summary'],flush=True)
 families={}
 for d in docs:
  f=families.setdefault(d['family'],{'documents':0,'pages':0,'source_containers':0,'source_status_counts':collections.Counter(),'pictures':0,'raster_status_counts':collections.Counter(),'raster_objects':0,'RAW_caption_delivered_source_containers':0,'MAPPED_caption_delivered_source_containers':0,'source_unavailable_documents':0})
  f['documents']+=1;f['pages']+=d['pages'];f['source_containers']+=len(d['source_figures']);f['source_status_counts'].update(d['summary']['source_status_counts']);f['pictures']+=len(d['pictures']);f['raster_status_counts'].update(d['summary']['raster_status_counts']);f['raster_objects']+=len(d['raster_object_checks']);f['RAW_caption_delivered_source_containers']+=sum(r['RAW']['caption_fragment_delivered'] for r in d['source_figures']);f['MAPPED_caption_delivered_source_containers']+=sum(r['MAPPED']['caption_fragment_delivered'] for r in d['source_figures']);f['source_unavailable_documents']+=d['source_status']!='SOURCE_PARSED'
 out={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'experiment':'E0','new_conversion':False,'new_model_inference':False,'global_oracle_freeze_sha256':sha(W3/'oracle-freeze.json'),'image_oracle_sha256':sha(oraclepath),'source_raster_geometry_sha256':sha(ROOT/'pdf-raster-geometry.json'),'mapper_source_sha256':sha(R4/'mapper/map_documents.py'),'bbox_numeric_tolerance_points':1e-6,'caption_link_metric_scope':'Explicit graph linkage using independent source caption identity, not audited visual correctness. UNKNOWN kept outside detected/missed fraction.','raster_metric_scope':'Native raster-object bounds containment, not rendered-payload completeness; clip/occlusion/visible-source identity unknowns retained.','families':families,'documents':docs}
 (ROOT/'E0-evaluation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');(ROOT/'E0-family-summary.json').write_text(json.dumps(families,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
