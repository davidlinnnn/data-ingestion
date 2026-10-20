"""Source/PDF-only structured units. Never imports or reads Docling artifacts."""
from pathlib import Path,PurePosixPath
import json,re,hashlib,collections,tarfile,io,gzip,bisect,unicodedata,time
import pypdfium2 as pdfium
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
OLD=REPO/'docs/research/pdf-core-w2-native-coverage-round2-2026-10-20/oracle'
JOBS=REPO/'docs/research/pdf-core-w2-native-coverage-round4-2026-10-20/jobs.json'
SEED='W3-formula-code-source-v1-20261020'
FORM={'equation','equation*','align','align*','gather','gather*','multline','multline*','eqnarray','eqnarray*','displaymath'}
CODE={'lstlisting','verbatim','verbatim*','Verbatim','minted','tcblisting'}
PROMPT={'tracebox','promptbox','codebox','code','python'}
ALGO={'algorithm','algorithm*','algorithmic','algorithmic*','algorithm2e'}
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s).casefold() if c.isalnum())
def unescape(s):
 s=re.sub(r'\\(?:textbf|textit|texttt|emph|textrm|textnormal)\s*\{([^{}]*)\}',r'\1',s)
 s=s.replace(r'\\','\n')
 for a,b in [(r'\_','_'),(r'\%','%'),(r'\{','{'),(r'\}','}'),(r'\&','&'),(r'\$','$'),('~',' ')]:s=s.replace(a,b)
 return s

def load_archive(data):
 files={}
 try:
  with tarfile.open(fileobj=io.BytesIO(data),mode='r:*')as tar:
   for m in tar:
    pp=PurePosixPath(m.name)
    if m.isfile()and not pp.is_absolute()and'..'not in pp.parts and m.size<=10_000_000 and pp.suffix.lower()in{'.tex','.ltx','.txt','.py','.json','.xml','.yaml','.yml','.sh','.r','.c','.cpp','.jl','.java','.aux'}:
     b=tar.extractfile(m).read()
     if b'\x00'not in b:files[str(pp)]=b.decode('utf8',errors='replace')
 except tarfile.ReadError:
  try:data=gzip.decompress(data)
  except(OSError,EOFError):pass
  if b'\\documentclass'in data:files['source.tex']=data.decode('utf8',errors='replace')
 return files

def env_spans(s):
 stack=[];out=[];issues=[]
 # Literal environments are consumed opaquely; fake TeX/comments inside code cannot alter the stack.
 token=re.compile(r'\\(begin|end)\s*\{([^{}]+)\}')
 pos=0
 while(m:=token.search(s,pos)):
  typ,name=m.groups();pos=m.end()
  if typ=='begin'and name in CODE:
   end=re.search(r'\\end\s*\{'+re.escape(name)+r'\}',s[pos:])
   if not end:issues.append('unclosed_literal:'+name);continue
   e0=pos+end.start();e1=pos+end.end();out.append({'env':name,'start':m.start(),'body_start':m.end(),'body_end':e0,'end':e1,'ancestors':[x[0]for x in stack]});pos=e1;continue
  if typ=='begin':stack.append((name,m.start(),m.end()))
  elif stack and stack[-1][0]==name:
   n,a,b=stack.pop();out.append({'env':n,'start':a,'body_start':b,'body_end':m.start(),'end':m.end(),'ancestors':[x[0]for x in stack]})
  else:issues.append('unmatched_end:'+name)
 issues += ['unclosed_environment:'+x[0]for x in stack]
 return sorted(out,key=lambda x:x['start']),issues

def mask_comments(s):
 spans,_=env_spans(s);literal=[(x['body_start'],x['body_end'])for x in spans if x['env']in CODE];chars=list(s)
 for m in re.finditer(r'(?<!\\)%[^\n]*',s):
  if any(a<=m.start()<b for a,b in literal):continue
  chars[m.start():m.end()]=' '*(m.end()-m.start())
 return ''.join(chars)

def expand(files,root):
 seen=[];issues=[]
 def rd(name,chain):
  if name in chain:issues.append('cycle:'+name);return '',[]
  seen.append(name);s=mask_comments(files[name]);chunks=[];refs=[];at=0
  spans,_=env_spans(s);literal=[(x['start'],x['end'])for x in spans if x['env']in CODE]
  for m in re.finditer(r'\\(?:input|include)(?![A-Za-z@])\s*(?:\{([^}]+)\}|([^\s%{}]+))',s):
   if any(a<=m.start()<b for a,b in literal):continue
   chunks.append(s[at:m.start()]);refs.extend((name,i)for i in range(at,m.start()));target=m.group(1)or m.group(2);base=str(PurePosixPath(name).parent/target);target=next((x for x in[base,base+'.tex',target,target+'.tex']if x in files),None)
   if target:
    ss,rr=rd(target,chain+[name]);chunks.append(ss);refs.extend(rr)
   else:issues.append('unresolved_input:'+m.group());chunks.append(s[m.start():m.end()]);refs.extend((name,i)for i in range(m.start(),m.end()))
   at=m.end()
  chunks.append(s[at:]);refs.extend((name,i)for i in range(at,len(s)));return ''.join(chunks),refs
 s,refs=rd(root,[]);b=re.search(r'\\begin\s*\{document\}',s)
 if not b:return '',[],{'root':root,'issues':['no_document_body']}
 e=s.find(r'\end{document}',b.end());e=len(s)if e<0 else e
 return s[b.end():e],refs[b.end():e],{'root':root,'included_files':seen,'issues':issues}

def split_rows(s):
 rows=[];start=0;depth=0;env=0;i=0
 while i<len(s):
  if s.startswith(r'\begin{',i):env+=1
  if s.startswith(r'\end{',i):env=max(0,env-1)
  if s[i]=='\\':
   if s.startswith(r'\\',i)and depth==0 and env==0:rows.append((start,i,s[start:i]));start=i+2;i+=2;continue
   i+=2;continue
  if s[i]=='{':depth+=1
  elif s[i]=='}':depth=max(0,depth-1)
  i+=1
 if s[start:].strip():rows.append((start,len(s),s[start:]))
 return rows

def scan(s):
 spans,issues=env_spans(s);units=[];inline=[]
 for e in spans:
  name=e['env'];anc=e['ancestors'];kind='formula'if name in FORM else'code'if name in CODE|PROMPT else'algorithm'if name in ALGO else None
  if not kind:continue
  if kind=='formula'and any(x in FORM|CODE|ALGO for x in anc):continue
  if kind=='algorithm'and any(x in ALGO for x in anc):continue
  if kind=='code'and name in PROMPT and any(c['env']in CODE and e['body_start']<=c['start']<e['body_end']for c in spans):continue
  if kind=='formula'and any(x in PROMPT for x in anc):continue
  raw=s[e['body_start']:e['body_end']];e=dict(e,kind=kind,raw=raw)
  if kind=='formula':e['rows']=[{'row_index':i+1,'raw':t,'relative_offset':a}for i,(a,b,t)in enumerate(split_rows(raw))if t.strip()]
  if kind=='algorithm':
   # Preserve command identities and original order; only normalize TeX whitespace, never expand unknown macros.
   chunks=re.split(r'(?=\\(?:STATE|State|IF|If|ELSE|Else|ELSIF|ElsIf|FOR|For|WHILE|While|RETURN|Return|Require|Ensure|KwIn|KwOut|Fn|ForEach|uIf|uElseIf|tcp|tcc)\b)|(?<=\\;)\s*|\n',raw)
   e['normalized_lines']=[{'line_index':i+1,'text':re.sub(r'\s+',' ',t).strip()}for i,t in enumerate(chunks)if t.strip()]
   e['unexpanded_macro_commands']=sorted(set(re.findall(r'\\([A-Za-z@]+)',raw)))
  units.append(e)
 # Delimited display/inline math, excluding code, algorithm and existing display environments.
 excluded=[(e['start'],e['end'])for e in spans if e['env']in FORM|CODE|PROMPT|ALGO]
 i=0
 while i<len(s):
  ex=next((b for a,b in excluded if a<=i<b),None)
  if ex is not None:i=ex;continue
  delim='$$'if s.startswith('$$',i)else r'\['if s.startswith(r'\[',i)else'$'if s[i]=='$'and(i==0 or s[i-1]!='\\')else r'\('if s.startswith(r'\(',i)else None
  if not delim:i+=1;continue
  close={r'\[':r'\]',r'\(':r'\)'}.get(delim,delim);m=re.search(r'(?<!\\)'+re.escape(close),s[i+len(delim):])if close in{'$','$$'}else re.search(re.escape(close),s[i+len(delim):])
  if not m:issues.append('unclosed_math_delimiter:'+delim);i+=len(delim);continue
  b=i+len(delim)+m.start();end=i+len(delim)+m.end();e={'kind':'formula'if delim in{'$$',r'\['}else'inline_math','env':delim,'start':i,'body_start':i+len(delim),'body_end':b,'end':end,'ancestors':[],'raw':s[i+len(delim):b]}
  if e['kind']=='formula':e['rows']=[{'row_index':1,'raw':e['raw'],'relative_offset':0}];units.append(e)
  else:inline.append(e)
  i=end
 return sorted(units,key=lambda e:e['start']),inline,issues

def selfcheck():
 s=r'\begin{align}a&=b\\ c&=\begin{matrix}1\\2\end{matrix}\end{align} $x$ \[y=2\] $$z=3$$ \begin{verbatim}a%literal $notmath$\end{verbatim}'
 u,ii,_=scan(s);assert len([e for e in u if e['kind']=='formula'])==3 and len(ii)==1
 assert len(u[0]['rows'])==2 and '%literal'in u[-1]['raw']
 fs={'m.tex':r'\begin{document}\includegraphics{x}\input{a}\end{document}','a.tex':'$x$'};ss,rr,a=expand(fs,'m.tex');assert r'\includegraphics'in ss and '$x$'in ss and not a['issues']
 assert mask_comments('a%z\nb')=='a  \nb'

def locate(e,refs,files,oldanchors,pdfnorm):
 f,off=refs[min(e['start'],len(refs)-1)];ef,eo=refs[min(e['end']-1,len(refs)-1)];line=files[f].count('\n',0,off)+1;endline=files[ef].count('\n',0,eo)+1
 e.update(source_file=f,source_offset=off,source_line=line,end_source_file=ef,end_source_offset=eo+1,end_source_line=endline,source_file_sha256=sha(files[f].encode()),expanded_offset=e['start'])
 aa=[a for a in oldanchors if a.get('source_file')==f and a.get('oracle_status')=='TRUSTED']
 # Actual old schema status is status (checked below), retain no Docling-derived coordinates.
 if not aa:aa=[a for a in oldanchors if a.get('source_file')==f and a.get('status')=='TRUSTED']
 before=sorted([a for a in aa if a.get('source_line',0)<line and line-a.get('source_line',0)<=80],key=lambda a:a['source_line'],reverse=True)[:4]
 after=sorted([a for a in aa if a.get('source_line',0)>endline and a.get('source_line',0)-endline<=80],key=lambda a:a['source_line'])[:4]
 within=[a for a in aa if line<=a.get('source_line',0)<=endline]
 e['surrounding_body_anchors']=[{'id':a.get('id'),'text':a['text'],'source_line':a['source_line'],'pages':a.get('pdf_pages',[]),'kind':a['kind']}for a in before[:2]+after[:2]]
 candidates=sorted({p for a in before[:2]+after[:2]+within for p in a.get('pdf_pages',[])})
 hits=[]
 if e['kind']in{'code','algorithm'}:
  clean=unescape(e['raw']);clean=re.sub(r'\\[A-Za-z@]+\*?(?:\[[^]]*\])?',' ',clean);words=re.findall(r'[A-Za-z0-9_]+',clean)
  for k in sorted(set([0,max(0,len(words)//2-6),max(0,len(words)-12)])):
   text=' '.join(words[k:k+12]);n=norm(text)
   if len(n)<32:continue
   pages=[p+1 for p,t in enumerate(pdfnorm)if n in t]
   if len(pages)==1:hits.append({'text':text,'page':pages[0]})
 e['direct_pdf_text_anchors']=hits
 pages=sorted({h['page']for h in hits});e['page']=None;e['pages']=[];e['page_status']='UNKNOWN';e['page_candidates']=sorted(set(candidates+pages))
 if pages:
  e['pages']=list(range(min(pages),max(pages)+1));e['page']=pages[0]if len(pages)==1 else None;e['page_status']='DIRECT_TEXT_ANCHORS'if len(pages)==1 else'DIRECT_TEXT_ANCHORS_MULTIPAGE_RANGE'
 elif e['kind']=='formula'and not any(a in{'figure','figure*','table','table*'}for a in e['ancestors'])and before and after:
  bp=before[0].get('pdf_pages',[]);ap=after[0].get('pdf_pages',[])
  if len(bp)==len(ap)==1 and bp==ap:e['page']=bp[0];e['pages']=bp;e['page_status']='NONFLOAT_SURROUNDING_ANCHORS_SAME_PAGE'
 e['parser_status']='SOURCE_UNIT_EXACT_MACROS_UNEXPANDED';e['raw_sha256']=sha(e['raw'].encode())
 e['unknown_reasons']=[]
 if e['page_status']=='UNKNOWN':e['unknown_reasons'].append('No unique direct text anchor or same-page nonfloat body bracket; candidates are not page assignments.')
 if any(x in e['raw']for x in[r'\if',r'\else',r'\fi']):e['unknown_reasons'].append('Conditional TeX remains unexecuted.')
 return e

def main():
 selfcheck();jobs=json.loads(JOBS.read_text())['jobs'];index=json.loads((OLD/'job-index.json').read_text());allunits=[];allinline=[];audits=[];counts=[]
 for job in jobs:
  old=json.loads(Path(index[job['id']]).read_text());source=old['source'];path=Path(source.get('reused_path',OLD/'sources'/(job['arxiv_version']+'.source')))
  if not path.is_absolute():path=REPO/path
  audit={'job_id':job['id'],'source_path':str(path),'expected_source_sha256':source.get('sha256'),'oracle_reference':index[job['id']]}
  if old['summary'].get('oracle')=='textlayer_fallback':audit.update(status='UNKNOWN_NO_BODY_LATEX',reason='Adam source is an includepdf wrapper; never use saved conversion to invent formula/code ground truth.');audits.append(audit);counts.append({'job_id':job['id'],'status':audit['status'],'formula':0,'code':0,'algorithm':0,'inline_math':0});continue
  data=path.read_bytes();assert sha(data)==source['sha256'];files=load_archive(data);root=old['source_audit']['root'];s,refs,ea=expand(files,root);uu,ii,issues=scan(s);audit.update(source_sha256=sha(data),source_files_sha256={f:sha(t.encode())for f,t in files.items()},expansion=ea,parser_issues=issues,status='SOURCE_PARSED')
  pdf=pdfium.PdfDocument(job['pdf']);pdfnorm=[]
  for page in pdf:
   t=page.get_textpage();pdfnorm.append(norm(t.get_text_range()));t.close();page.close()
  pdf.close()
  for k,e in enumerate(uu,1):
   e=locate(e,refs,files,old['anchors'],pdfnorm);e.update(job_id=job['id'],set=job['set'],family=old['summary'].get('family',job['family']),id=job['id']+':'+e['kind']+':'+str(k).zfill(5),source_archive_sha256=sha(data),selected_last_page=job['last']);e['scope']='OUT_OF_SCOPE'if e['pages']and min(e['pages'])>job['last']else'IN_SCOPE'if e['pages']and max(e['pages'])<=job['last']else'UNKNOWN_PAGE_SCOPE';e['sample_hash']=sha((SEED+'|'+e['id']+'|'+e['raw_sha256']).encode());allunits.append(e)
  for k,e in enumerate(ii,1):
   f,off=refs[e['start']];allinline.append({'id':job['id']+':inline:'+str(k).zfill(5),'job_id':job['id'],'source_file':f,'source_offset':off,'source_line':files[f].count('\n',0,off)+1,'expanded_offset':e['start'],'raw':e['raw'],'delimiter':e['env'],'source_file_sha256':sha(files[f].encode()),'page_status':'UNKNOWN_NOT_LOCATED','not_a_flattening_loss_judgment':True})
  audits.append(audit);cc=collections.Counter(e['kind']for e in uu);counts.append({'job_id':job['id'],'status':'SOURCE_PARSED','formula':cc['formula'],'code':cc['code'],'algorithm':cc['algorithm'],'inline_math':len(ii),'page_status_counts':dict(collections.Counter(e['page_status']for e in allunits if e['job_id']==job['id']))});print(job['id'],dict(cc),len(ii),flush=True)
 # Sample source-only by fixed family/hash; UNKNOWN page units stay listed and are not silently substituted.
 formula_sample=[]
 for family in sorted({e['family']for e in allunits}):formula_sample.extend(sorted([e for e in allunits if e['family']==family and e['kind']=='formula'and e['scope']!='OUT_OF_SCOPE'],key=lambda e:e['sample_hash'])[:40])
 code_sample=[e for e in allunits if e['kind']in{'code','algorithm'}and e['scope']!='OUT_OF_SCOPE']
 oracle={'version':SEED,'source_only':True,'jobs':counts,'units':allunits,'inline_math':allinline,'source_audit':audits,'sampling':{'seed':SEED,'hash':'SHA256(seed|unit_id|raw_sha256)','formula_if_cost_over_2hours':[e['id']for e in formula_sample],'all_code_algorithm':[e['id']for e in code_sample],'unknown_page_units_retained_not_assigned_or_replaced':True,'E1_preflight_jobs':['F-ieee_crnn','P-07-2504.15228v2'],'adjudication50_rule':'After frozen E1 scoring, classify candidates into formula/code/algorithm x missing/near/exact strata using frozen matching rules. Take up to 20 formula-near/error, 15 code-near/error, 15 algorithm-near/error by SHA256(seed|audit50|unit_id). A stratum with insufficient units transfers unfilled slots to the other near/error strata in formula,code,algorithm round-robin hash order. Never handpick; retain all UNKNOWNs and explain insufficient denominator. No exact substitutions until all near/error candidates exhausted.'}}
 dump(ROOT/'oracle.json',oracle);dump(ROOT/'sample-plan.json',oracle['sampling']);dump(ROOT/'summary.json',{'jobs':counts,'totals':dict(collections.Counter(e['kind']for e in allunits)),'units':len(allunits),'inline_math':len(allinline),'sample_formula_units':len(formula_sample),'sample_code_algorithm_units':len(code_sample),'page_status_counts':dict(collections.Counter(e['page_status']for e in allunits))})
 dump(ROOT/'freeze.json',{'version':SEED,'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'source_only':True,'no_conversion_artifacts_read':True,'files_sha256':{f:sha((ROOT/f).read_bytes())for f in['build_oracle.py','oracle.json','sample-plan.json','summary.json','method.md']}})
if __name__=='__main__':main()
