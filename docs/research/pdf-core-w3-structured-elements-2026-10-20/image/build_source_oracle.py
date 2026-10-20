"""W3 phase-1 source-only image oracle. No conversion output input paths."""
import pathlib,json,re,hashlib,importlib.util,tarfile,io,gzip,collections,datetime,unicodedata
import pypdfium2 as pdfium
ROOT=pathlib.Path(__file__).resolve().parent
REPO=ROOT.parents[3]
R2=REPO/'docs/research/pdf-core-w2-native-coverage-round2-2026-10-20'
JOBS=REPO/'docs/research/pdf-core-w2-native-coverage-round4-2026-10-20/jobs.json'
SPEC=importlib.util.spec_from_file_location('source_only_r2',R2/'oracle/build_oracle.py');M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
sha=lambda b:hashlib.sha256(b).hexdigest()
norm=M.norm

def uncomment_same_length(s):
 return re.sub(r'(?<!\\)%[^\n]*',lambda m:' '*len(m.group()),s)

def arg(s,i,op='{',cl='}'):
 while i<len(s) and s[i].isspace():i+=1
 if i>=len(s) or s[i]!=op:return None,i
 start=i;i+=1;depth=1
 while i<len(s) and depth:
  if s[i]=='\\':i+=2;continue
  if s[i]==op:depth+=1
  elif s[i]==cl:depth-=1
  i+=1
 return (s[start+1:i-1],start,i),i

def expand(files,root):
 issues=[];visited=[]
 def read(path,chain):
  if path in chain:issues.append('include_cycle:'+path);return '',[]
  visited.append(path);s=uncomment_same_length(files[path]);parts=[];refs=[];at=0
  for m in re.finditer(r'\\(?:input|include)(?![A-Za-z@])\s*(?:\{([^}]+)\}|([^\s%{}]+))',s):
   parts.append(s[at:m.start()]);refs.extend((path,k) for k in range(at,m.start()))
   name=m.group(1) or m.group(2);base=str(pathlib.PurePosixPath(path).parent/name)
   target=next((x for x in [base,base+'.tex',name,name+'.tex'] if x in files),None)
   if target:t,r=read(target,chain+[path]);parts.append(t);refs.extend(r)
   else:issues.append('unresolved_input:'+m.group());parts.append(s[m.start():m.end()]);refs.extend((path,k) for k in range(m.start(),m.end()))
   at=m.end()
  parts.append(s[at:]);refs.extend((path,k) for k in range(at,len(s)))
  return ''.join(parts),refs
 s,refs=read(root,[]);b=re.search(r'\\begin\s*\{document\}',s)
 if not b:return '',[],{'root':root,'issues':issues+['no_document_body'],'included_files':visited}
 e=s.find(r'\end{document}',b.end());e=len(s) if e<0 else e
 return s[b.end():e],refs[b.end():e],{'root':root,'issues':issues,'included_files':visited}

def clean_tex(s):
 s=re.sub(r'\\(?:label|cite\w*|ref|eqref|url)\s*\{[^{}]*\}',' ',s)
 s=re.sub(r'\$[^$]*\$',' ',s)
 s=re.sub(r'\\(?:[A-Za-z@]+\*?|.)',' ',s)
 return re.sub(r'\s+',' ',s.translate(str.maketrans({'{':'','}':'','~':' ','_':' '}))).strip()

def extract(s,refs,files):
 records=[];graphics=[];captions=[];issues=[];stack=[]
 skipranges=[];skipstack=[]
 for m in re.finditer(r'\\(begin|end)\s*\{([^}]+)\}',s):
  typ,env=m.groups()
  if env in ['verbatim','verbatim*','lstlisting','minted','comment','filecontents','filecontents*']:
   if typ=='begin':skipstack.append((env,m.start()))
   elif skipstack:
    ev,start=skipstack.pop();skipranges.append((start,m.end()))
 def skipped(i):return any(a<=i<b for a,b in skipranges)
 def loc(i):
  if not refs:return None
  f,o=refs[min(i,len(refs)-1)];return {'source_file':f,'source_line':files[f].count('\n',0,o)+1,'source_offset':o,'expanded_offset':i,'source_file_sha256':sha(files[f].encode())}
 for m in re.finditer(r'\\(begin|end)\s*\{([^}]+)\}',s):
  if skipped(m.start()):continue
  typ,env=m.groups()
  if typ=='begin':stack.append((env,m.start(),m.end()))
  else:
   found=next((k for k in range(len(stack)-1,-1,-1) if stack[k][0]==env),None)
   if found is None:continue
   ev,start,opening=stack[found];stack=stack[:found]
   if env in ['figure','figure*','subfigure','subfigure*','table','table*']:
    if env.startswith('table') and not re.search(r'\\includegraphics\*?(?![A-Za-z@])',s[start:m.end()]):continue
    records.append({'kind':env,'start':start,'end':m.end(),'source':loc(start),'raw_latex':s[start:m.end()],'conditional_uncertain':bool(re.search(r'\\(?:if\w*|else|fi)\b',s[max(0,start-200):m.end()]))})
 for m in re.finditer(r'\\(subfloat|subfigure)(?![A-Za-z@])',s):
  if skipped(m.start()):continue
  i=m.end();opts=[]
  for k in range(2):
   a,ni=arg(s,i,'[',']')
   if a is None:break
   opts.append(a[0]);i=ni
  body,end=arg(s,i)
  if body is not None:records.append({'kind':m.group(1)+'_command','start':m.start(),'end':end,'source':loc(m.start()),'raw_latex':s[m.start():end],'optional_caption':opts[-1] if opts else None,'conditional_uncertain':False})
 records.sort(key=lambda r:(r['start'],-r['end']))
 for i,r in enumerate(records):
  r['id']='figure-%04d'%i
  r['image_table_float']=r['kind'] in ['table','table*']
 def parent(i,exclude=None):
  rs=[r for r in records if r['id']!=exclude and r['start']<=i<r['end']]
  return min(rs,key=lambda r:r['end']-r['start']) if rs else None
 for r in records:
  par=parent(r['start'],r['id']);r['parent_id']=par['id'] if par else None
 for m in re.finditer(r'\\(?:caption\*?|subcaption\*?|captionof)(?![A-Za-z@])',s):
  if skipped(m.start()):continue
  i=m.end();cmd=m.group();captionof=None
  if cmd==r'\captionof':a,i=arg(s,i);captionof=a[0] if a else None
  a,ni=arg(s,i,'[',']')
  if a:i=ni
  body,end=arg(s,i)
  if body is None:continue
  par=parent(m.start())
  if not par:continue
  captions.append({'id':'caption-%04d'%len(captions),'parent_id':par['id'],'raw_latex':body[0],'text':clean_tex(body[0]),'source':loc(m.start()),'source_end':loc(max(m.start(),end-1)),'start':m.start(),'end':end})
 for r in records:
  if r.get('optional_caption') is not None:captions.append({'id':'caption-%04d'%len(captions),'parent_id':r['id'],'raw_latex':r['optional_caption'],'text':clean_tex(r['optional_caption']),'source':r['source'],'source_end':r['source'],'start':r['start'],'end':r['start']})
 for m in re.finditer(r'\\includegraphics\*?(?![A-Za-z@])',s):
  if skipped(m.start()):continue
  i=m.end();opts=[]
  for k in range(2):
   a,ni=arg(s,i,'[',']')
   if a is None:break
   opts.append(a[0]);i=ni
  body,end=arg(s,i)
  if body is None:issues.append('includegraphics_without_literal_arg');continue
  par=parent(m.start());graphics.append({'id':'graphic-%04d'%len(graphics),'parent_id':par['id'] if par else None,'path_latex':body[0],'options':opts,'source':loc(m.start()),'start':m.start(),'end':end})
 for r in records:
  r['caption_ids']=[c['id'] for c in captions if c['parent_id']==r['id']]
  r['direct_includegraphics_ids']=[g['id'] for g in graphics if g['parent_id']==r['id']]
  r['includegraphics_ids']=[g['id'] for g in graphics if r['start']<=g['start']<r['end']]
  r['child_ids']=[q['id'] for q in records if q['parent_id']==r['id']]
 return records,graphics,captions,issues

def archive_info(data):
 out={}
 try:
  with tarfile.open(fileobj=io.BytesIO(data),mode='r:*') as t:
   for m in t:
    if m.isfile() and not pathlib.PurePosixPath(m.name).is_absolute() and '..' not in pathlib.PurePosixPath(m.name).parts:
     out[str(pathlib.PurePosixPath(m.name))]={'bytes':m.size}
 except tarfile.ReadError:pass
 return out

def archive_sha(data,targets):
 out={}
 try:
  with tarfile.open(fileobj=io.BytesIO(data),mode='r:*') as t:
   for m in t:
    name=str(pathlib.PurePosixPath(m.name))
    if m.isfile() and name in targets:out[name]=sha(t.extractfile(m).read())
 except tarfile.ReadError:pass
 return out

def selfcheck():
 files={'m.tex':'\\begin{document}\n% \\begin{figure}ignored\\end{figure}\n\\begin{figure*}\\subfloat[A sub caption]{\\includegraphics[width=1cm]{a.pdf}}\\caption{A sufficiently long caption one two three four five six seven.}\\end{figure*}\\end{document}'}
 s,refs,audit=expand(files,'m.tex');rs,gs,cs,issues=extract(s,refs,files)
 assert [r['kind'] for r in rs]==['figure*','subfloat_command']
 assert len(gs)==1 and len(cs)==2 and gs[0]['parent_id']==rs[1]['id']
 assert rs[0]['includegraphics_ids']==['graphic-0000']
 loc=rs[0]['source'];assert files[loc['source_file']][loc['source_offset']:].startswith(r'\begin{figure*}')
 assert 'ignored' not in ''.join(r['raw_latex'] for r in rs)
 return {'nested_figure_subfloat':True,'comments_excluded':True,'exact_original_offset':True,'includegraphics_parent':True}

def main():
 check=selfcheck();jobs=json.loads(JOBS.read_text())['jobs'];indexpath=R2/'oracle/job-index.json';index=json.loads(indexpath.read_text());papers=[]
 for job in jobs:
  jid=job['id'];oldpath=pathlib.Path(index[jid]);prior=json.loads(oldpath.read_text());src=prior['source'];candidate=job.get('source_archive') or src.get('reused_path');path=pathlib.Path(candidate) if candidate else R2/'oracle/sources'/(job['arxiv_version']+'.source')
  if not path.exists():path=R2/'oracle/sources'/(job['arxiv_version']+'.source')
  data=path.read_bytes() if path.exists() else b'';files=M.sources(data);audit=prior['source_audit'];record={'job_id':jid,'family':job['family'],'selected_pages':[job['first'],job['last']],'pdf':job['pdf'],'pdf_sha256':sha(pathlib.Path(job['pdf']).read_bytes()),'source_archive':str(path.resolve()),'source_archive_sha256':sha(data),'source_url':src.get('url'),'source_sha_matches_W2':sha(data)==src.get('sha256'),'source_files_sha256':{k:sha(v.encode()) for k,v in files.items()},'source_audit':audit,'figures':[],'includegraphics':[],'captions':[],'issues':[]}
  if jid=='F-iclr_adam' or prior['summary'].get('oracle')=='textlayer_fallback' or not files or audit.get('root') not in files:
   record.update(status='UNKNOWN_SOURCE',reason='No trustworthy article LaTeX: Adam wrapper/textlayer fallback is not article source; no invented zero figure count.');papers.append(record);print(jid,'UNKNOWN_SOURCE',flush=True);continue
  s,refs,expanded_audit=expand(files,audit['root']);rs,gs,cs,issues=extract(s,refs,files);record['expanded_source_sha256']=sha(s.encode());record['expanded_source_audit']=expanded_audit
  pdf=pdfium.PdfDocument(job['pdf']);pdftexts=[]
  for page in pdf:
   tp=page.get_textpage();pdftexts.append(norm(tp.get_text_range()));tp.close();page.close()
  pdf.close();anchors=[a for a in prior['anchors'] if a['kind']=='caption'];bodyanchors=[a for a in prior['anchors'] if a['kind']=='prose']
  for c in cs:
   loc=c['source'];end=c['source_end'];matches=[a for a in anchors if a.get('source_file')==loc['source_file'] and loc['source_line']<=a.get('source_line',0)<=end['source_line'] and len(a.get('normalized',''))>=30 and a['normalized'] in norm(c['text'])];evidence=[]
   for a in matches:
    pages=[i+1 for i,t in enumerate(pdftexts) if a['normalized'] in t]
    if len(pages)==1:evidence.append({'anchor_id':a['id'],'text':a['text'],'normalized':a['normalized'],'pages':pages,'method':'source-file-line-associated-caption-anchor exact normalized PDF text; unique page (duplicate occurrences on same page allowed)'})
   if not evidence:
    full=norm(c['text']);pg=[i+1 for i,t in enumerate(pdftexts) if full and full in t]
    if len(full)>=12 and len(c['text'].split())>=3 and len(pg)==1:evidence.append({'text':c['text'],'normalized':full,'pages':pg,'method':'full caption exact normalized PDF text, >=3 words and >=12 alnum, unique page'})
   if not evidence:
    words=c['text'].split();seen=set()
    for at in range(max(0,len(words)-9)):
     n=norm(' '.join(words[at:at+10]));pg=[i+1 for i,t in enumerate(pdftexts) if n in t]
     if len(n)>=45 and len(pg)==1 and (tuple(pg),n) not in seen:evidence.append({'text':' '.join(words[at:at+10]),'normalized':n,'pages':pg,'method':'10-word caption window exact normalized PDF text, unique page'});seen.add((tuple(pg),n))
   pages=sorted({p for e in evidence for p in e['pages']});c['pdf_pages']=pages;c['page_evidence']=evidence[:12];c['page_status']='CONFIRMED_PAGE' if len(pages)==1 else 'UNKNOWN' if not pages else 'MULTI_PAGE_EVIDENCE';c['selected_scope']='IN_SCOPE' if pages and all(job['first']<=p<=job['last'] for p in pages) else 'OUT_OF_SCOPE' if pages and all(p>job['last'] or p<job['first'] for p in pages) else 'UNKNOWN'
  for r in rs:
   caps=[c for c in cs if c['parent_id']==r['id']];pages=sorted({p for c in caps for p in c['pdf_pages']});r['pdf_pages']=pages;r['page_status']='CONFIRMED_PAGE' if len(pages)==1 else 'UNKNOWN' if not pages else 'MULTI_PAGE_EVIDENCE';r['selected_scope']='IN_SCOPE' if pages and all(job['first']<=p<=job['last'] for p in pages) else 'OUT_OF_SCOPE' if pages and all(p>job['last'] for p in pages) else 'UNKNOWN'
   nearest=[]
   for a in bodyanchors:
    if a.get('source_file')==r['source']['source_file'] and abs(a.get('source_line',-999)-r['source']['source_line'])<=8 and a.get('pdf_pages'):nearest.append({'anchor_id':a['id'],'text':a['text'],'pdf_pages':a['pdf_pages'],'source_line':a['source_line'],'use':'context only; floats can move, never assigns figure page'})
   r['nearby_body_anchor_context']=nearest[:4]
  # A subfigure without its own exact caption may inherit an independently located containing float.
  for r in rs:
   if not r['pdf_pages'] and r['parent_id']:
    par=next(q for q in rs if q['id']==r['parent_id'])
    if par['page_status']=='CONFIRMED_PAGE':r.update(pdf_pages=par['pdf_pages'],page_status='INHERITED_PARENT_CONFIRMED_PAGE',selected_scope=par['selected_scope'],page_method='containing source float caption exact unique PDF page')
  names=archive_info(data)
  for g in gs:
   raw=g['path_latex'];base=str(pathlib.PurePosixPath(g['source']['source_file']).parent/raw);candidates=[]
   for name in [raw,base]:
    for ext in ['','.pdf','.png','.jpg','.jpeg','.eps','.ps']:
     if name+ext in names:candidates.append(name+ext)
   if not candidates:candidates=[name for name in names if pathlib.PurePosixPath(name).name==pathlib.PurePosixPath(raw).name or pathlib.PurePosixPath(name).stem==pathlib.PurePosixPath(raw).name]
   candidates=sorted(set(candidates));g['archive_path_candidates']=candidates;g['archive_resolution']='UNIQUE' if len(candidates)==1 else 'UNKNOWN';par=next((r for r in rs if r['id']==g['parent_id']),None);g['pdf_pages']=par['pdf_pages'] if par else [];g['page_status']=par['page_status'] if par else 'UNKNOWN';g['page_method']='inherited containing LaTeX figure caption page; not inferred from conversion output'
  hashes=archive_sha(data,{p for g in gs for p in g['archive_path_candidates']})
  for g in gs:g['archive_sha256']={p:hashes.get(p) for p in g['archive_path_candidates']}
  record.update(status='SOURCE_PARSED',figures=rs,includegraphics=gs,captions=cs,issues=issues+expanded_audit['issues'],summary={'figure_environments':sum(r['kind'] in ['figure','figure*'] for r in rs),'image_table_floats':sum(r['kind'] in ['table','table*'] for r in rs),'subfigure_or_subfloat':sum(r['kind'] not in ['figure','figure*','table','table*'] for r in rs),'includegraphics_commands':len(gs),'caption_commands':len(cs),'page_confirmed_figures':sum(r['page_status']=='CONFIRMED_PAGE' for r in rs),'page_unknown_figures':sum(r['page_status']=='UNKNOWN' for r in rs),'all_source_figures_including_outside_selected_pages':True})
  papers.append(record);print(jid,record['summary'],flush=True)
 out={'version':'W3-image-source-only-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':'PHASE1_SOURCE_ONLY','prohibited_inputs_read':False,'inputs':{'jobs':str(JOBS),'jobs_sha256':sha(JOBS.read_bytes()),'source_oracle_index':str(indexpath),'source_oracle_index_sha256':sha(indexpath.read_bytes())},'selfcheck':check,'papers':papers}
 (ROOT/'oracle.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 (ROOT/'selfcheck.json').write_text(json.dumps({'synthetic':check,'papers':len(papers),'source_parsed':sum(p['status']=='SOURCE_PARSED' for p in papers),'unknown_source':[p['job_id'] for p in papers if p['status']!='SOURCE_PARSED'],'archive_sha_mismatch':[p['job_id'] for p in papers if not p['source_sha_matches_W2']],'all_caption_evidence_source_only':True},indent=2)+'\n')
if __name__=='__main__':main()
