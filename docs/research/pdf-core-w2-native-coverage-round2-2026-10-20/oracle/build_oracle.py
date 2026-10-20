"""Frozen LaTeX-first prose anchor oracle; never reads conversion outputs.
Only writes beneath this file's directory. No TeX execution or archive extraction.
"""
from pathlib import Path, PurePosixPath
import argparse, collections, gzip, hashlib, io, json, re, time, tarfile, unicodedata
import requests
import pypdfium2 as pdfium
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
OLD=REPO/'docs/research/pdf-core-w2-native-coverage-2026-10-20'
VERSION='latex-oracle-v1-20261020'
def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def sha(data): return hashlib.sha256(data).hexdigest()
def norm(s):
    s=unicodedata.normalize('NFKD',s).casefold()
    return ''.join(c for c in s if c.isalnum())
def uncomment(s): return re.sub(r'(?<!\\)%[^\n]*','',s)
def sources(data):
    out={}
    try:
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:*') as tar:
            for m in tar:
                pp=PurePosixPath(m.name)
                if m.isfile() and not pp.is_absolute() and '..' not in pp.parts and pp.suffix.lower() in ('.tex','.ltx') and m.size<=10_000_000:
                    out[str(pp)]=tar.extractfile(m).read().decode('utf-8',errors='replace')
    except tarfile.ReadError:
        try: data=gzip.decompress(data)
        except (OSError,EOFError): pass
        if b'\\documentclass' in data or b'\\begin{document}' in data:
            out['source.tex']=data.decode('utf-8',errors='replace')
    return out

def expand(files):
    candidates=[p for p,s in files.items() if re.search(r'\\begin\s*\{document\}',uncomment(s))]
    if not candidates: return '',[],{'error':'no_document_root','files':list(files)}
    # Prefer actual article to template/example; maximum included/body source size breaks ties.
    def weight(p):
        s=uncomment(files[p]); return (not bool(re.search('sample|example|template',p,re.I)),len(s)+sum(len(files.get(x+'.tex','')) for x in re.findall(r'\\input\{([^}]+)\}',s)))
    root=max(candidates,key=weight); seen=[]; issues=[]
    def read(p,chain):
        if p in chain: issues.append('include_cycle:'+p); return '',[]
        seen.append(p); s=uncomment(files[p]); chars=[]; refs=[]; at=0
        for m in re.finditer(r'\\(?:input|include)(?![A-Za-z@])\s*(?:\{([^}]+)\}|([^\s%{}]+))',s):
            chunk=s[at:m.start()]; chars.append(chunk); refs.extend((p,s.count('\n',0,at+i)+1) for i in range(len(chunk)))
            target=m.group(1) or m.group(2); base=str(PurePosixPath(p).parent/target)
            target=next((x for x in (base,base+'.tex',target,target+'.tex') if x in files),None)
            if target:
                sub,r=read(target,chain+[p]); chars.append(sub); refs.extend(r)
            else: issues.append('unresolved_input:'+m.group(0))
            at=m.end()
        chunk=s[at:]; chars.append(chunk); refs.extend((p,s.count('\n',0,at+i)+1) for i in range(len(chunk)))
        return ''.join(chars),refs
    s,refs=read(root,[])
    start=re.search(r'\\begin\s*\{document\}',s); end=s.find(r'\end{document}',start.end())
    if end<0:end=len(s)
    return s[start.end():end],refs[start.end():end],{'root':root,'root_candidates':candidates,'included_files':seen,'issues':issues}

SKIP_ENVS={'figure','figure*','table','table*','tabular','tabular*','tabularx','longtable','algorithm','algorithm*','algorithmic','algorithmic*','equation','equation*','align','align*','aligned','eqnarray','eqnarray*','gather','gather*','multline','multline*','displaymath','math','tikzpicture','verbatim','lstlisting','minted','thebibliography','comment','filecontents','filecontents*'}
DROP_ARGS={'cite','citep','citet','citealp','citealt','citenum','citeauthor','citeyear','ref','eqref','autoref','cref','Cref','label','url','includegraphics','bibliography','bibliographystyle','addbibresource','index','vspace','hspace','rule','setlength','definecolor','color','pagecolor'}
FORMAT={'textbf','textit','texttt','textrm','textnormal','textsf','emph','underline','mbox','MakeUppercase','MakeLowercase','protect','small','footnotesize','scriptsize','large','Large','LARGE','tiny','normalfont','bfseries','itshape','centering','raggedright','noindent','par','quad','qquad','newline','linebreak','allowbreak','xspace','ignorespaces','relax','hfill','vfill','item','appendix','maketitle','clearpage','newpage','onecolumn','twocolumn','sloppy','fussy','today','thanks'}
def parse(s,refs):
    anchors=[]; headings=[]; unknown=collections.Counter(); buf=[]; origin=0; heading=None; env=[]; i=0; conditional=0
    def skip():return any(e in SKIP_ENVS for e in env)
    def group(pos,op='{',cl='}'):
        while pos<len(s) and s[pos].isspace():pos+=1
        if pos>=len(s) or s[pos]!=op:return '',pos
        start=pos+1; depth=1; pos+=1
        while pos<len(s) and depth:
            if s[pos]=='\\':pos+=2;continue
            if s[pos]==op:depth+=1
            elif s[pos]==cl:depth-=1
            pos+=1
        return s[start:pos-1],pos
    def clean(t):
        t=re.sub(r'\$[^$]*\$',' ',t)
        t=re.sub(r'\\[A-Za-z@]+\*?(?:\[[^]]*\])?',' ',t)
        return re.sub(r'\s+',' ',t.translate(str.maketrans({'{':'','}':'','~':' ','&':' ','_':' '}))).strip()
    def emit(text,kind,pos):
        for m in re.finditer(r'.+?(?:[.!?](?=\s|$)|$)',text,re.S):
            t=clean(m.group()); n=norm(t)
            if len(re.findall(r"\b[A-Za-z]+(?:['’-][A-Za-z]+)*\b",t))>=8:
                f,l=refs[min(pos,len(refs)-1)] if refs else ('unknown',0)
                anchors.append({'kind':kind,'text':t,'raw':m.group().strip(),'normalized':n,'source_file':f,'source_line':l,'source_offset':pos,'heading':heading,'conditional_uncertain':conditional>0})
    def flush():
        nonlocal buf
        if buf:emit(''.join(buf),'prose',origin)
        buf=[]
    while i<len(s):
        if s.startswith('\\[',i) or s.startswith('\\(',i):
            if not skip():buf.append(' ')
            close='\\]' if s[i+1]=='[' else '\\)'; end=s.find(close,i+2);i=len(s) if end<0 else end+2;continue
        if s[i]=='$':
            delim='$$' if s.startswith('$$',i) else '$'; end=s.find(delim,i+len(delim));i=len(s) if end<0 else end+len(delim)
            if not skip():buf.append(' ')
            continue
        if s[i]=='\\':
            m=re.match(r'\\([A-Za-z@]+\*?|.)',s[i:],re.S)
            if not m:i+=1;continue
            cmd=m.group(1);base=cmd.rstrip('*');pos=i;i+=len(m.group())
            if base in ('begin','end'):
                name,i=group(i)
                flush()
                if base=='begin':env.append(name)
                elif name in env:env=env[:len(env)-1-env[::-1].index(name)]
                continue
            if base.startswith('if') and base not in ('ifthenelse','ifstrequal'):
                flush();conditional+=1;continue
            if base=='fi':flush();conditional=max(0,conditional-1);continue
            if base in ('else','or'):flush();continue
            if base in ('caption','footnote','footnotetext','captionof'):
                if i<len(s) and s[i]=='[':_,i=group(i,'[',']')
                if base=='captionof':_,i=group(i)
                value,i=group(i);emit(value,'caption' if base.startswith('caption') else 'footnote',pos)
                if not skip():buf.append(' ')
                continue
            if skip():continue
            if base in ('part','chapter','section','subsection','subsubsection','paragraph','subparagraph'):
                flush()
                if i<len(s) and s[i]=='[':_,i=group(i,'[',']')
                title,i=group(i);level=['part','chapter','section','subsection','subsubsection','paragraph','subparagraph'].index(base)-1
                heading={'title':clean(title),'level':max(1,level),'command':base,'starred':cmd.endswith('*')}
                f,l=refs[min(pos,len(refs)-1)];headings.append({**heading,'source_file':f,'source_line':l,'source_offset':pos});continue
            if base in DROP_ARGS:
                if i<len(s) and s[i]=='[':_,i=group(i,'[',']')
                _,i=group(i)
                buf.append(' ');continue
            if base=='href':_,i=group(i);continue
            if base in ('title','author','affiliation','address','institute','date','email','keywords','newcommand','renewcommand','providecommand','def','gdef','newenvironment','renewenvironment'):
                flush();_,i=group(i)
                if i<len(s) and s[i]=='[':_,i=group(i,'[',']')
                if i<len(s) and s[i]=='{':_,i=group(i)
                continue
            if base not in FORMAT and base.isalpha():unknown[base]+=1
            if base in ('%','&','#','_'):buf.append(base)
            elif base in ('LaTeX','TeX'):buf.append(base)
            elif base in ('ie','eg','etc'):buf.append({'ie':'i.e.','eg':'e.g.','etc':'etc.'}[base])
            else:buf.append(' ')
            continue
        if not skip():
            if not buf:origin=i
            if s.startswith('\n\n',i):flush()
            else:buf.append(s[i])
        i+=1
    flush()
    anchors.sort(key=lambda a:a['source_offset'])
    counts=collections.Counter(a['normalized'] for a in anchors)
    for idx,a in enumerate(anchors):
        a['order']=idx;a['id']=f'{a["kind"]}-{idx:05d}';a['unique_in_candidates']=sum(b['normalized'].count(a['normalized']) for b in anchors)==1
    return anchors,headings,dict(unknown)

def obtain(p,is_f):
    version=p['arxiv_version']; url='https://arxiv.org/src/'+version
    previous=Path(p['source_path']) if is_f else OLD/'oracle'/f'{version}.source'
    if previous.exists():
        data=previous.read_bytes();return data,{'url':url,'status':'REUSED_BYTES','reused_path':str(previous),'sha256':sha(data),'bytes':len(data)}
    target=ROOT/'sources'/f'{version}.source'
    if target.exists():return target.read_bytes(),json.loads(target.with_suffix('.json').read_text())
    info={'url':url,'requested_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    try:
        r=requests.get(url,timeout=100);info.update(http_status=r.status_code,resolved_url=r.url,content_type=r.headers.get('Content-Type'),sha256=sha(r.content),bytes=len(r.content))
        dump(target.with_suffix('.json'),info)
        if r.status_code==200:
            target.write_bytes(r.content);return r.content,info
    except requests.RequestException as exc:info['error']=str(exc);dump(target.with_suffix('.json'),info)
    return b'',info

def main():
    assert norm('ﬁne-tune\nalpha')=='finetunealpha'
    a,h,u=parse('One two three four five six seven eight. \\begin{figure}Hidden one two three four five six seven eight. \\caption{Caption one two three four five six seven eight.}\\end{figure} Last one two three four five six seven eight.', [('test',1)]*1000)
    assert [x['kind'] for x in a]==['prose','caption','prose'] and not any('Hidden' in x['text'] for x in a)
    assert parse('\\section{A}'+ 'One two three four five six seven eight.', [('test',1)]*1000)[1][0]['level']==1
    ex,_,audit=expand({'main.tex':r'\begin{document}\includegraphics{x}\input{body}\end{document}','body.tex':'A body text.'})
    assert r'\includegraphics{x}' in ex and 'A body text.' in ex and not audit['issues']
    f=json.loads((OLD/'corpus/manifest.json').read_text())['papers'];p=json.loads((OLD/'set-p.json').read_text())['papers']
    rows=[]
    for is_f,paper in [(True,x) for x in f]+[(False,x) for x in p]:
        ident=paper['id'] if is_f else 'p'+str(paper['index']).zfill(2);out=ROOT/ident
        if (out/'oracle.json').exists():
            obj=json.loads((out/'oracle.json').read_text());rows.append(obj['summary']);continue
        print('START',ident,flush=True)
        data,source=obtain(paper,is_f);files=sources(data)
        s,refs,audit=expand(files);anchors,headings,unknown=parse(s,refs)
        pdfpath=Path(paper['pdf_path'] if is_f else paper['path']); pdf=pdfium.PdfDocument(pdfpath)
        texts=[]
        for page in pdf:
            tp=page.get_textpage();texts.append(tp.get_text_range());tp.close();page.close()
        pdf.close();nt=[norm(t) for t in texts];whole=''.join(nt);bounds=[];off=0
        for page,t in enumerate(nt,1):bounds.append((off,off+len(t),page));off+=len(t)
        selected=paper['pages_selected'][-1] if is_f else len(texts)
        fallback=is_f and paper['id']=='iclr_adam'
        if fallback and not anchors:
            for page,text in enumerate(texts,1):
                for m in re.finditer(r'.+?(?:[.!?](?=\s|$)|$)',re.sub(r'\s+',' ',text)):
                    t=m.group().strip()
                    if len(t.split())>=8:anchors.append({'id':f'textlayer-{len(anchors):05d}','kind':'prose','text':t,'raw':t,'normalized':norm(t),'order':len(anchors),'source_file':'PDF_TEXT_LAYER','source_line':None,'source_offset':m.start(),'heading':None,'conditional_uncertain':False,'unique_in_candidates':True})
        for a in anchors:
            n=a['normalized'];hits=[m.start() for m in re.finditer(re.escape(n),whole)] if n else []
            a['pdf_occurrences']=len(hits);a['pdf_pages']=[]
            if len(hits)==1:
                a['pdf_pages']=[pg for b,e,pg in bounds if b<hits[0]+len(n) and e>hits[0]]
                a['pdf_normalized_offset']=hits[0]
            a['status']='TRUSTED' if len(hits)==1 and a['unique_in_candidates'] and not a['conditional_uncertain'] else 'ORACLE_UNCERTAIN'
            if a['status']=='TRUSTED' and max(a['pdf_pages'])>selected:a['status']='OUT_OF_SCOPE'
        summary={'id':ident,'set':'F' if is_f else 'P','pages':selected,'source_files':len(files),'source_download_status':source.get('http_status',source.get('status')),'anchors':len(anchors),'counts':dict(collections.Counter((a['kind']+':'+a['status']) for a in anchors)),'headings':len(headings),'root':audit.get('root'),'oracle':'textlayer_fallback' if fallback else 'latex'}
        obj={'version':VERSION,'summary':summary,'source':source,'source_audit':audit,'unknown_commands':unknown,'anchors':anchors,'headings':headings,'pdf_text_pages':len(texts),'pdf_sha256':sha(pdfpath.read_bytes()),'selected_last_page':selected}
        dump(out/'oracle.json',obj);dump(out/'source-files.json',{'files':{k:sha(v.encode()) for k,v in files.items()}});dump(out/'pdf-text.json',texts);rows.append(summary)
        dump(ROOT/'summary.json',rows);print('DONE',summary,flush=True)
    dump(ROOT/'summary.json',rows)
if __name__=='__main__':main()
