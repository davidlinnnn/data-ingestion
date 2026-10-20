"""Source-only metadata supplements; no conversion imports/read access."""
import collections,json,re,hashlib
from pathlib import Path
from build_oracle import ROOT,OLD,dump,norm,sources,expand,sha

def main():
 jobs=json.loads((ROOT.parent/'jobs.json').read_text())['jobs']; fs={x['id']:x for x in json.loads((OLD/'corpus/manifest.json').read_text())['papers']};ps={x['index']:x for x in json.loads((OLD/'set-p.json').read_text())['papers']}
 index={};summaries=[];manifest=[]
 for job in jobs:
  ident=job['id'][2:] if job['set']=='F' else 'p'+job['id'][2:4];path=ROOT/ident/'oracle.json'
  if not path.exists():continue
  obj=json.loads(path.read_text());index[job['id']]=str(path.resolve());source=obj['source']
  if job['set']=='F':
   source['expected_sha256']=fs[ident]['source_sha256'];source['expected_sha256_matches']=source['sha256']==source['expected_sha256'];source['http_status']='not_requested_reused_frozen_bytes'
  elif source.get('status')=='REUSED_BYTES':
   headers=OLD/'oracle'/(Path(source['reused_path']).stem+'.headers');raw=headers.read_text() if headers.exists() else '';status=re.findall(r'HTTP/\S+\s+(\d+)',raw)
   source['http_status']='not_requested_reused_bytes';source['prior_http_status']=int(status[-1]) if status else None;source['prior_headers_path']=str(headers)
  manifest.append({'job_id':job['id'],**source})
  if job['set']=='F':data=Path(fs[ident]['source_path']).read_bytes()
  else:
   version=job['arxiv_version'];sp=ROOT/'sources'/f'{version}.source'
   if not sp.exists():sp=OLD/'oracle'/f'{version}.source'
   data=sp.read_bytes() if sp.exists() else b''
  files=sources(data);s,refs,audit=expand(files);texts=json.loads((path.parent/'pdf-text.json').read_text());np=[norm(t) for t in texts]
  full='\n'.join(files.values());evidence=[]
  for fn,tx in files.items():
   for lineno,line in enumerate(tx.splitlines(),1):
    if re.search(r'\\(?:documentclass|usepackage)',line) and not line.lstrip().startswith('%'):evidence.append({'file':fn,'line':lineno,'text':line.strip()})
  template=' '.join(x['text'] for x in evidence).lower();family='Pilot-other/unknown'
  for token,fam in [('acl','ACL/EMNLP'),('emnlp','ACL/EMNLP'),('naacl','ACL/EMNLP'),('ieeetran','IEEE conference'),('sigconf','ACM sigconf'),('cvpr','CVPR/AAAI'),('aaai','CVPR/AAAI'),('icml','ICML'),('neurips','NeurIPS/ICLR'),('nips','NeurIPS/ICLR'),('iclr','NeurIPS/ICLR'),('llncs','Springer LNCS')]:
   if token in template:family=fam;break
  if family=='Pilot-other/unknown' and re.search(r'\\documentclass(?:\[[^]]*\])?\{article\}',template) and not any(t in template for t in ('conference','iclr','nips','neurips','acl','icml')):family='general arXiv (article; template uncertain)'
  obj['template']={'family':job['family'] if job['set']=='F' else family,'evidence':evidence}
  maths=[]
  for match in re.finditer(r'(?<![\\$])\$(?!\$)(.*?)(?<!\\)\$(?!\$)|\\\((.*?)\\\)',s,re.S):
   before=re.sub(r'\\[a-zA-Z]+(?:\{[^}]*\})?',' ',s[max(0,match.start()-180):match.start()]);after=re.sub(r'\\[a-zA-Z]+(?:\{[^}]*\})?',' ',s[match.end():match.end()+180])
   words_before=re.findall(r'[A-Za-z]+',before)[-8:];words_after=re.findall(r'[A-Za-z]+',after)[:8]
   contexts=[' '.join(words_before),' '.join(words_after)];hits=[]
   for context in contexts:
    if len(context.split())>=5:
     n=norm(context);pgs=[i+1 for i,t in enumerate(np) if n in t]
     if len(pgs)==1:hits.append(pgs[0])
   page=hits[0] if hits and len(set(hits))==1 else None;fn,line=refs[match.start()] if refs else ('unknown',None)
   maths.append({'source_file':fn,'source_line':line,'source_offset':match.start(),'raw':match.group(),'context_before':contexts[0],'context_after':contexts[1],'pdf_page':page,'status':'SOURCE_CANDIDATE_ONLY','scope':'IN_SCOPE' if page and page<=job['last'] else 'OUT_OF_SCOPE' if page else 'UNKNOWN'})
  for h in obj['headings']:
   n=norm(h['title']);hits=[i+1 for i,t in enumerate(np) if n and n in t]
   h['pdf_pages']=hits;h['scope']='IN_SCOPE' if len(hits)==1 and hits[0]<=job['last'] else 'OUT_OF_SCOPE' if len(hits)==1 else 'UNKNOWN'
  front=re.search(r'\\begin\s*\{abstract\}|\\abstract\s*\{|\\section(?:\*|\s)*\{',s)
  # Check substring uniqueness against all emitted candidate text, including other classes.
  for a in obj['anchors']:
   reasons=[]
   if front and a.get('source_file')!='PDF_TEXT_LAYER' and a['source_offset']<front.start():reasons.append('frontmatter_before_abstract_or_section')
   if len(a['text'].split())<8:reasons.append('fewer_than_8_whitespace_words')
   a['unique_in_candidates']=sum(b['normalized'].count(a['normalized']) for b in obj['anchors'])==1
   if not a['unique_in_candidates']:reasons.append('source_candidate_substring_not_unique')
   if a['pdf_occurrences']==0:reasons.append('PDF_exact_match_absent_macro_citation_math_or_interleaving_possible')
   if a['pdf_occurrences']>1:reasons.append('PDF_match_not_unique')
   if a.get('conditional_uncertain'):reasons.append('unknown_TeX_conditional')
   a['uncertainty_reasons']=reasons
   if reasons:a['status']='ORACLE_UNCERTAIN'
  obj['oracle_uncertainty_reasons']=dict(collections.Counter(reason for a in obj['anchors'] for reason in a['uncertainty_reasons']))
  obj['inline_math_source_candidates']=maths
  obj['source_line_semantics']='source_file/source_line locate the original paragraph start (caption/footnote command for those classes); source_offset is expanded-source position. No TeX was executed.'
  obj['summary']['counts']=dict(collections.Counter(a['kind']+':'+a['status'] for a in obj['anchors']));obj['summary']['inline_math_source_candidates']=len(maths);obj['summary']['family']=obj['template']['family'];obj['summary']['source_coverage_note']='Only PDF-unique exact normalized sentence matches are trusted; citation/math/macros, conditionals, non-prose source and PDF interleaving often remain uncertain. This is a sparse anchor oracle, not all-sentence coverage.'
  dump(path,obj);summaries.append(obj['summary'])
 dump(ROOT/'job-index.json',index);dump(ROOT/'summary.json',summaries);dump(ROOT/'source-manifest.json',manifest)
if __name__=='__main__':main()
