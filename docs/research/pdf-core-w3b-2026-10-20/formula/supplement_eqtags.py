from pathlib import Path
from lxml import html
import json,re,hashlib,collections,importlib.util
import pypdfium2 as pf
P=Path(__file__).resolve().parent;W=P.parent;O=P/'assessment-v2';REPO=P.parents[3]
sp=importlib.util.spec_from_file_location('phase3',P/'score_html.py');s=importlib.util.module_from_spec(sp);sp.loader.exec_module(s)
def read(p):return json.loads(p.read_text())
def dump(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def hasclass(n,c):return c in n.get('class','').split()
def eqgroup(d,u):
 nn=d.xpath(u['html_xpath'])
 if not nn:return None,[]
 n=nn[0]
 for a in [n]+list(n.iterancestors()):
  if a.tag=='table'and any('ltx_eqn'in c or'ltx_equation'in c for c in a.get('class','').split()):
   tags=[''.join(t.itertext()).strip()for t in a.iter()if any(c.startswith('ltx_tag_equation')for c in t.get('class','').split())];tags=sorted(set(tags));return a.get('id')or d.getroottree().getpath(a),tags
 return None,[]
def main():
 units=read(P/'oracle.json')['units'];v1=read(P/'assessment/per-formula.json');v1by={r['unit_id']:r for r in v1};jobs={j['job_id']:j for j in read(W/'html-manifest.json')['jobs']};inputs=read(P/'assessment/input-hashes.json');base=REPO/'docs/research/pdf-core-w2-native-coverage-round3-2026-10-20/runs/V3_B/jobs';htmls={};groups={};bygroup=collections.defaultdict(list);pdfcache={};docs={};outs=[]
 for u in units:
  j=u['job_id']
  if j not in htmls:htmls[j]=html.fromstring(Path(jobs[j]['html_path']).read_bytes())
  group,tags=eqgroup(htmls[j],u);groups[u['unit_id']]=(group,tags);bygroup[(j,group)].append(u)
 for u in units:
  old=v1by[u['unit_id']]
  if not old['source_evaluable_after_adjudication']or old['fixed_E0_refs']:continue
  j=u['job_id'];group,tags=groups[u['unit_id']];r={'unit_id':u['unit_id'],'job_id':j,'family':old['family_analysis'],'source_page':u['page'],'source_latex':u['latex'],'html_equation_group':group,'source_tags':tags,'status':'UNKNOWN_NO_UNIQUE_SOURCE_EQTAG','fixed_E0_refs':[],'E1':None,'source_to_E0_only':True};outs.append(r)
  if j not in inputs or not inputs[j].get('E1_folder')or len(tags)!=1:continue
  tag=tags[0]
  if not re.fullmatch(r'\([A-Za-z0-9.\-]*\d[A-Za-z0-9.\-]*\)',tag):continue
  pn=u['page'];key=(j,pn)
  if key not in pdfcache:
   doc=pf.PdfDocument(jobs[j]['pdf']);pg=doc[pn-1];tp=pg.get_textpage();raw=tp.get_text_range();boxes=[tp.get_charbox(i)for i in range(tp.count_chars())];pdfcache[key]=(raw,boxes);tp.close();pg.close();doc.close()
  raw,boxes=pdfcache[key];pattern=r'\(\s*'+r'\s*'.join(re.escape(x)for x in tag[1:-1])+r'\s*\)';hits=list(re.finditer(pattern,raw))
  if len(hits)!=1:r['status']='UNKNOWN_SOURCE_PDF_EQTAG_NOT_UNIQUE';r['pdf_eqtag_occurrences']=len(hits);continue
  mm=hits[0];bb=[boxes[i]for i in range(mm.start(),mm.end())if i<len(boxes)];bbox=[min(b[0]for b in bb),min(b[1]for b in bb),max(b[2]for b in bb),max(b[3]for b in bb)]
  if j not in docs:docs[j]=(s.refs(read(base/j/'document.json')),s.refs(read(Path(inputs[j]['E1_folder'])/'document.json')))
  d0,d1=docs[j];found=[]
  for ref in inputs[j].get('actual_processed_refs',[]):
   t=d0.get(ref)
   if not t or t['label']!='formula'or pn not in s.pages(t)or not re.search(pattern,t.get('orig','')):continue
   for pr in t.get('prov',[]):
    if pr['page_no']!=pn:continue
    b=pr['bbox'];l,rgt=min(b['l'],b['r']),max(b['l'],b['r']);bt,top=min(b['b'],b['t']),max(b['b'],b['t']);cx=(bbox[0]+bbox[2])/2;cy=(bbox[1]+bbox[3])/2
    if b.get('coord_origin')=='BOTTOMLEFT'and l-2<=cx<=rgt+2 and bt-2<=cy<=top+2:found.append(ref);break
  if len(found)!=1:r['status']='UNKNOWN_EQTAG_NOT_UNIQUE_IN_ENRICHED_NATIVE_BOX';r['native_candidates']=found;continue
  ref=found[0];t=d0[ref];a=d1.get(ref);r.update(status='UNIQUE_SOURCE_EQTAG_PDF_BOX_TO_FIXED_E0',fixed_E0_refs=[ref],source_pdf_eqtag_bbox=bbox,native_prov=t.get('prov'),E0orig=t.get('orig',''),source_group_unit_ids=[x['unit_id']for x in bygroup[(j,group)]])
  if not a or a.get('orig')!=t.get('orig')or a.get('prov')!=t.get('prov'):r['E1']={'status':'UNKNOWN_ITEM_IDENTITY'};continue
  r['E1_active_text']=a.get('text','');parentunits=bygroup[(j,group)]
  if len(parentunits)!=1:r['E1']={'status':'MANY_TO_ONE_UNRESOLVED','reason':'Source eqgroup has multiple rows/continuations; tag identifies parent, not independent line text.'};continue
  r['E0orig_lexical']=s.bucket(u['latex'],t.get('orig',''));r['E1']={'status':'ACTUALLY_ENRICHED_SINGLE_SOURCE_EQGROUP','RAW':s.bucket(u['latex'],a.get('text','')),'MAPPED':s.bucket(u['latex'],a.get('text','')if a.get('text','').strip()else a.get('orig','')),'identity_not_by_E1_similarity':True}
 dump('per-formula.json',outs);summary={'preregistration_sha256':hashlib.sha256((O/'preregistration.json').read_bytes()).hexdigest(),'v1_not_modified':True,'source_gold_not_modified':True,'supplement_candidates':len(outs),'statuses':dict(collections.Counter(r['status']for r in outs)),'parent_identity_unique':sum(bool(r['fixed_E0_refs'])for r in outs),'new_independent_text_scored':sum((r['E1']or{}).get('status')=='ACTUALLY_ENRICHED_SINGLE_SOURCE_EQGROUP'for r in outs),'E1_statuses':dict(collections.Counter((r['E1']or{}).get('status','UNRESOLVED_IDENTITY')for r in outs)),'E1_RAW':dict(collections.Counter(r['E1']['RAW']['class']for r in outs if(r['E1']or{}).get('status')=='ACTUALLY_ENRICHED_SINGLE_SOURCE_EQGROUP')),'source_granularity_needs_manual_check':True};dump('summary-machine.json',summary);print(summary)
if __name__=='__main__':main()
