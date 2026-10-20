"""PHASE1 SOURCE ONLY: LaTeX table inventory/grid oracle; never reads conversion outputs."""
import bisect,collections,datetime,gzip,hashlib,io,json,pathlib,re,tarfile,unicodedata

ROOT=pathlib.Path(__file__).resolve().parent
RESEARCH=ROOT.parent.parent
R2=RESEARCH/'pdf-core-w2-native-coverage-round2-2026-10-20/oracle'
JOBS=RESEARCH/'pdf-core-w2-native-coverage-round4-2026-10-20/jobs.json'
GRIDS={'tabular','tabular*','tabularx','longtable','longtable*','tabulary','tabu','supertabular','xltabular','tblr','longtblr'}
FLOATS={'table','table*','sidewaystable','sidewaystable*','wraptable'}
FORMAT={'textbf','textit','texttt','textrm','textnormal','textsf','emph','underline','mbox','makecell','shortstack','multirow','multicolumn','ensuremath','mathbf','mathrm','mathit','mathsf','bm','boldsymbol','text','substack','uline','underline','smash','vphantom','phantom','colorbox','fcolorbox'}
SWITCH={'bf','it','em','rm','tt','sf','bfseries','itshape','normalfont','scriptsize','footnotesize','small','tiny','large','Large','centering','raggedright','raggedleft','arraybackslash','protect','relax','hfill','hspace','vspace','rule','strut','noindent','displaystyle','scriptstyle'}
SYMBOL={'%':'%','&':'&','_':'_','#':'#','pm':'±','mp':'∓','times':'×','cdot':'·','leq':'≤','le':'≤','geq':'≥','ge':'≥','approx':'≈','infty':'∞','top':'top','downarrow':'↓','uparrow':'↑','checkmark':'✓','cmark':'✓','xmark':'✗','textbackslash':'\\','textasciitilde':'~','textless':'<','textgreater':'>','dag':'†','dagger':'†','ddagger':'‡','quad':' ','qquad':' ','enspace':' ','thinspace':' '}
NUM=re.compile(r'(?<![A-Za-z\d])[-+−]?(?:\d+(?:[.,]\d+)*|\.\d+)(?:[eE][-+]?\d+)?(?:\s*[%‰])?')


def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def sha(data):return hashlib.sha256(data).hexdigest()
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s).casefold()if c.isalnum())
def uncomment(s):return re.sub(r'(?<!\\)%[^\n]*',lambda m:' '*len(m.group()),s)
def group(s,p,op='{',cl='}'):
    while p<len(s)and s[p].isspace():p+=1
    if p>=len(s)or s[p]!=op:return None,p
    start=p+1;depth=1;p+=1
    while p<len(s)and depth:
        if s[p]=='\\':p+=2;continue
        if s[p]==op:depth+=1
        elif s[p]==cl:depth-=1
        p+=1
    return s[start:p-1]if depth==0 else None,p


def files_from(data):
    files={}
    try:
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:*')as tar:
            for entry in tar:
                p=pathlib.PurePosixPath(entry.name)
                if entry.isfile()and not p.is_absolute()and '..'not in p.parts and p.suffix.lower()in ('.tex','.ltx')and entry.size<=10_000_000:
                    files[str(p)]=tar.extractfile(entry).read().decode('utf-8',errors='replace')
    except tarfile.ReadError:
        try:data=gzip.decompress(data)
        except (OSError,EOFError):pass
        if b'\\documentclass'in data:files['source.tex']=data.decode('utf-8',errors='replace')
    return files


def expanded(files,root):
    chunks=[];segments=[];issues=[];included=[];length=0
    def append(value,file,offset):
        nonlocal length
        if value:segments.append((length,file,offset));chunks.append(value);length+=len(value)
    def read(file,chain):
        if file in chain:issues.append('include_cycle:'+file);return
        if len(included)>1000 or length>30_000_000:raise ValueError('source expansion limit')
        included.append(file);s=uncomment(files[file]);at=0
        for m in re.finditer(r'\\(?:input|include)(?![A-Za-z@])\s*(?:\{([^}]+)\}|([^\s%{}]+))',s):
            append(s[at:m.start()],file,at)
            target=m.group(1)or m.group(2);base=str(pathlib.PurePosixPath(file).parent/target)
            target=next((p for p in [base,base+'.tex',target,target+'.tex']if p in files),None)
            if target:read(target,chain+[file])
            else:issues.append('unresolved_input:'+m.group())
            at=m.end()
        append(s[at:],file,at)
    if root not in files:return '',[],['root_unavailable'],[]
    read(root,[])
    return ''.join(chunks),segments,issues,included


def clean(raw):
    unknown=[]
    def rec(s):
        out=[];i=0
        while i<len(s):
            if s[i]=='\\':
                m=re.match(r'\\([A-Za-z@]+\*?|.)',s[i:],re.S)
                if not m:i+=1;continue
                cmd=m.group(1).rstrip('*');i+=len(m.group())
                if cmd in SYMBOL:out.append(SYMBOL[cmd]);continue
                if cmd in FORMAT:
                    if i<len(s)and s[i]=='[':_,i=group(s,i,'[',']')
                    nargs=3 if cmd in ('multirow','multicolumn')else 1
                    args=[]
                    for _ in range(nargs):
                        value,end=group(s,i)
                        if value is None:break
                        args.append(value);i=end
                    if args:out.append(rec(args[-1]))
                    else:unknown.append(cmd)
                    continue
                if cmd in ('cite','citep','citet','ref','eqref','label','cellcolor','rowcolor','color','hspace','vspace','rule'):
                    if i<len(s)and s[i]=='[':_,i=group(s,i,'[',']')
                    _,i=group(s,i)
                    continue
                if cmd in SWITCH or cmd in ('toprule','midrule','bottomrule','hline','cline','cmidrule','addlinespace','specialrule'):
                    continue
                if cmd in ('\\',',',';','!',' ','newline','linebreak'):out.append(' ');continue
                unknown.append(cmd);out.append(' '+cmd+' ')
                continue
            if s[i]not in '{}$':out.append(' 'if s[i]=='~'else s[i])
            i+=1
        return ''.join(out)
    value=re.sub(r'\s+',' ',rec(raw)).strip()
    return value,sorted(set(unknown))


def colcount(spec):
    cols=0;i=0;unknown=[]
    while i<len(spec):
        c=spec[i]
        if c in 'lcrXS':cols+=1;i+=1
        elif c in 'pmb':
            cols+=1;_,i=group(spec,i+1)
        elif c in '@!><':_,i=group(spec,i+1)
        elif c=='*':
            n,i=group(spec,i+1);sub,i=group(spec,i)
            if n and n.isdigit()and sub is not None:
                ncols,u=colcount(sub);cols+=int(n)*ncols;unknown+=u
            else:unknown.append('column_repeat')
        elif c.isspace()or c in '|:':i+=1
        else:unknown.append(c);i+=1
    return cols,unknown


def splitrows(body):
    rows=[];cells=[];buf=[];depth=0;i=0;separators=[]
    def cell():cells.append(''.join(buf).strip());buf.clear()
    def row():
        cell()
        if any(x.strip()for x in cells):rows.append(cells.copy())
        cells.clear()
    while i<len(body):
        if body[i]=='\\':
            m=re.match(r'\\([A-Za-z@]+|.)',body[i:],re.S)
            cmd=m.group(1)
            if depth==0 and cmd in ('\\','tabularnewline','cr'):
                row();i+=len(m.group())
                if i<len(body)and body[i]=='*':i+=1
                if i<len(body)and body[i]=='[':_,i=group(body,i,'[',']')
                continue
            if depth==0 and cmd in ('toprule','midrule','bottomrule','hline','cline','cmidrule','addlinespace','specialrule'):
                if cmd in ('midrule','hline'):separators.append({'command':cmd,'after_completed_rows':len(rows)})
                i+=len(m.group())
                if i<len(body)and body[i]=='[':_,i=group(body,i,'[',']')
                if i<len(body)and body[i]=='(':_,i=group(body,i,'(',')')
                if cmd in ('cline','cmidrule','specialrule'):
                    for _ in range(3 if cmd=='specialrule'else 1):
                        value,end=group(body,i)
                        if value is None:break
                        i=end
                continue
            buf.append(m.group());i+=len(m.group());continue
        if body[i]=='{':depth+=1
        elif body[i]=='}':depth-=1
        if body[i]=='&'and depth==0:cell()
        else:buf.append(body[i])
        i+=1
    row()
    return rows,separators


def parsegrid(source,env):
    i=env['open_end'];name=env['name'];issues=[]
    if source[i:i+1]=='[':_,i=group(source,i,'[',']')
    if name in ('tabular*','tabularx','tabulary','xltabular'):_,i=group(source,i)
    spec,i=group(source,i)
    ncols,uc=colcount(spec or '')
    if spec is None or uc:issues.append('unresolved_column_spec:'+str(uc))
    if name in ('tabu','tblr','longtblr'):issues.append('unsupported_grid_dialect')
    body=source[i:env['end_start']]
    if re.search(r'\\begin\s*\{(?:tabular\*?|tabularx|array|aligned|split|matrix|smallmatrix)\}',body):issues.append('nested_grid_or_math_alignment')
    if re.search(r'\\(?:if\w*|else|fi)\b',body):issues.append('conditional_in_grid')
    rows,separators=splitrows(body);cells=[];carry={};point_candidates=[];layout_issues=[]
    for ri,row in enumerate(rows):
        ci=0
        for raw in row:
            # Explicit empty entries advance over a multirow continuation; nonempty skip carries.
            if raw.strip():
                while carry.get((ri,ci)):ci+=1
            rs=cs=1
            for command in ('multicolumn','multirow'):
                mt=re.search(r'\\'+command+r'\s*',raw)
                if mt:
                    at=mt.end()
                    if raw[at:at+1]=='[':_,at=group(raw,at,'[',']')
                    value,at=group(raw,at)
                    if value and re.fullmatch(r'\d+',value):
                        if command=='multicolumn':cs=int(value)
                        else:rs=int(value)
                    else:issues.append('unresolved_'+command+'_span')
            value,unknown=clean(raw)
            cell={'row':ri,'col':ci,'row_span':rs,'col_span':cs,'raw':raw,'text':value,'unknown_macros':unknown,'numeric_tokens':NUM.findall(value),'is_explicit_empty':not bool(raw.strip())}
            cells.append(cell)
            for yy in range(ri+1,ri+rs):
                for xx in range(ci,ci+cs):carry[yy,xx]=True
            ci+=cs
        if ncols and ci>ncols:layout_issues.append({'row':ri,'effective_columns':ci,'declared_columns':ncols})
    if layout_issues:issues.append('row_width_exceeds_declared_columns')
    # Header boundary is accepted only when explicitly separated by booktabs midrule.
    boundaries=[x['after_completed_rows']for x in separators if x['command']=='midrule'and x['after_completed_rows']>0]
    header_rows=list(range(boundaries[0]))if boundaries else []
    header_known=bool(header_rows)
    if not header_known:issues.append('header_boundary_not_explicit')
    for ci,cell in enumerate(cells):
        cell['id']=f'cell-{ci:04d}';cell['is_header']=cell['row']in header_rows if header_known else None
    for cell in cells:
        if not cell['numeric_tokens']or cell['row']in header_rows:continue
        row_labels=[x for x in cells if x['row']<=cell['row']<x['row']+x['row_span']and x['col']<cell['col']and x['text']and not x['numeric_tokens']]
        col_labels=[x for x in cells if x['row']in header_rows and x['col']<=cell['col']<x['col']+x['col_span']and x['text']]
        local=[]
        if not header_known:local.append('unknown_header_boundary')
        if not row_labels:local.append('unknown_row_label')
        if not col_labels:local.append('unknown_col_label')
        if cell['unknown_macros']or any(x['unknown_macros']for x in row_labels+col_labels):local.append('unresolved_value_or_label_macro')
        if len(cell['numeric_tokens'])!=1:local.append('multiple_values_in_cell')
        # Any structural uncertainty disables trusted data points in this grid.
        structural=[x for x in issues if x!='header_boundary_not_explicit']
        local+=structural
        point_candidates.append({'id':f'point-{len(point_candidates):04d}','cell_id':cell['id'],'row':cell['row'],'col':cell['col'],'value_text':cell['text'],'numeric_tokens':cell['numeric_tokens'],'row_labels':[{'cell_id':x['id'],'text':x['text']}for x in row_labels],'col_labels':[{'cell_id':x['id'],'text':x['text']}for x in col_labels],'status':'UNKNOWN'if local else'TRUSTED','uncertainty_reasons':sorted(set(local))})
    return {'environment':name,'column_spec':spec,'declared_cols':ncols,'rows':len(rows),'cells':cells,'header_rows':header_rows,'header_status':'EXPLICIT_MIDRULE'if header_known else'UNKNOWN','rules':separators,'numeric_points':point_candidates,'issues':sorted(set(issues)),'layout_issues':layout_issues,'source_start':env['start'],'source_end':env['end']}


def environments(source):
    stack=[];found=[];cond=0
    for match in re.finditer(r'\\(?:(begin|end)\s*\{([^}]+)\}|(if[A-Za-z@]*|else|fi)\b)',source):
        if match.group(3):
            cmd=match.group(3)
            if cmd=='fi':cond=max(0,cond-1)
            elif cmd!='else':cond+=1
            continue
        kind,name=match.group(1),match.group(2)
        if kind=='begin':stack.append({'name':name,'start':match.start(),'open_end':match.end(),'conditional_depth':cond})
        else:
            pos=next((i for i in range(len(stack)-1,-1,-1)if stack[i]['name']==name),None)
            if pos is not None:
                env=stack[pos];stack=stack[:pos];env.update(end_start=match.start(),end=match.end());found.append(env)
    return sorted(found,key=lambda x:x['start'])


def captions(source,start,end):
    result=[]
    for mt in re.finditer(r'\\caption(?:of)?\*?\s*',source[start:end]):
        p=start+mt.end()
        if source[p:p+1]=='[':_,p=group(source,p,'[',']')
        if 'captionof'in mt.group():_,p=group(source,p)
        raw,p=group(source,p)
        if raw is not None:
            text,unknown=clean(raw);result.append({'raw':raw,'text':text,'unknown_macros':unknown,'source_offset':start+mt.start()})
    return result


def selfcheck():
    source=r'\begin{table}\caption{A clear table.}\begin{tabular}{lcc}\toprule Method & A & B \\ \midrule X & 1.2 & 3 \\ Y & \multicolumn{2}{c}{4.5} \\ \bottomrule\end{tabular}\end{table}'
    env=next(x for x in environments(source)if x['name']=='tabular');g=parsegrid(source,env)
    assert g['declared_cols']==3 and g['rows']==3 and len(g['cells'])==8
    assert g['cells'][-1]['col_span']==2 and g['cells'][-1]['text']=='4.5'
    assert sum(p['status']=='TRUSTED'for p in g['numeric_points'])==3
    assert splitrows(r'a\&b & {c&d} \\ x & y')[0]==[[r'a\&b','{c&d}'],['x','y']]
    assert colcount(r'@{}l*{2}{cr}p{2cm}@{}')[0]==6
    assert clean(r'\unknownscore{1.2}')[1]==['unknownscore']
    return {'balanced_cells_escaped_ampersand_merged_column_numeric_labels':'PASS','column_spec_repeat_width':'PASS','unknown_macros_retained_not_guessed':'PASS'}


def main():
    checks=selfcheck();jobs=json.loads(JOBS.read_text())['jobs'];idx=json.loads((R2/'job-index.json').read_text());papers=[];tables=[]
    for job in jobs:
        oldpath=pathlib.Path(idx[job['id']]);old=json.loads(oldpath.read_text());info=old['source'];candidates=[pathlib.Path(info['reused_path'])]if info.get('reused_path')else[]
        if job.get('source_archive'):candidates.append(pathlib.Path(job['source_archive']))
        candidates += [R2/'sources'/f"{job['arxiv_version']}.source"]
        archive=next((p for p in candidates if p.exists()),None)
        data=archive.read_bytes()if archive else b'';files=files_from(data);root=old.get('source_audit',{}).get('root')
        source,segments,issues,included=expanded(files,root);starts=[x[0]for x in segments]
        root_unknown=len(old.get('source_audit',{}).get('root_candidates',[]))!=1
        def origin(pos):
            if not segments:return {'file':None,'line':None}
            at=max(0,bisect.bisect_right(starts,pos)-1);offset,file,base=segments[at]
            return {'file':file,'line':files[file].count('\n',0,base+pos-offset)+1,'file_sha256':sha(files[file].encode())}
        document_start=re.search(r'\\begin\s*\{document\}',source)
        document_end=source.find(r'\end{document}',document_start.end())if document_start else -1
        scan_source=source
        if document_start:
            scan_source=' '*document_start.end()+source[document_start.end():]
        if document_end>=0:scan_source=scan_source[:document_end]+' '*(len(source)-document_end)
        envs=environments(scan_source);grids=[x for x in envs if x['name']in GRIDS];floats=[x for x in envs if x['name']in FLOATS]
        groups=collections.defaultdict(list);containers={}
        for grid in grids:
            parents=[x for x in floats if x['start']<grid['start']and x['end']>grid['end']]
            parent=min(parents,key=lambda x:x['end']-x['start'])if parents else grid
            # Inner tabular/makecell grid belongs to outer grid, recorded as an uncertainty there.
            if any(x['start']<grid['start']and x['end']>grid['end']for x in grids):continue
            key=(parent['start'],parent['end']);groups[key].append(grid);containers[key]=parent
        pages=json.loads((oldpath.parent/'pdf-text.json').read_text());npages=[norm(x)for x in pages]
        unhandled_generators=sorted(set(re.findall(r'\\(pgfplotstabletypeset|csvreader|csvautotabular|csvautolongtable|DTLdisplaydb|inputtable)\b',scan_source)))
        body_unavailable=old.get('summary',{}).get('oracle')=='textlayer_fallback' or bool(re.search(r'\\includepdf\b',scan_source))
        inventory_issues=(['ambiguous_root']if root_unknown else[])+(['latex_body_unavailable_or_pdf_wrapper']if body_unavailable else[])+issues+['unhandled_table_generator:'+x for x in unhandled_generators]
        paper={'id':job['id'],'family':old.get('template',{}).get('family',job['family']),'pdf':job['pdf'],'pdf_sha256':job['pdf_sha256'],'selected_pages':[job['first'],job['last']],'source_archive':str(archive)if archive else None,'source_archive_sha256':sha(data),'source_expected_sha256':info.get('sha256'),'source_hash_matches':sha(data)==info.get('sha256'),'root':root,'root_candidates':old.get('source_audit',{}).get('root_candidates',[]),'source_root_status':'UNKNOWN'if root_unknown or not files else'KNOWN','inventory_status':'UNKNOWN'if inventory_issues else'EXPLICIT_ENVIRONMENTS_PARSED','inventory_uncertainty':inventory_issues,'expansion_issues':issues,'included_files':included,'files':{f:sha(s.encode())for f,s in files.items()},'tables':[]}
        for key,ge in sorted(groups.items()):
            container=containers[key];caps=captions(source,*key);parsed=[parsegrid(source,g)for g in ge];reasons=[]
            if len(ge)>1:reasons.append('multiple_subtables')
            if any(g['environment'].startswith(('long','xltabular','supertabular'))for g in parsed):reasons.append('cross_page_capable_environment')
            if any(c['row_span']>1 or c['col_span']>1 for g in parsed for c in g['cells']):reasons.append('merged_cells')
            if any(len(g['header_rows'])>1 for g in parsed):reasons.append('multi_level_header')
            if any(len(c['numeric_tokens'])>1 for g in parsed for c in g['cells']if c.get('is_header')is not True):reasons.append('multiple_numeric_values_in_cell')
            matches=[];method='UNKNOWN'
            for cap in caps:
                nc=norm(cap['text'])
                if len(nc)>=12:
                    hits=[i+1 for i,p in enumerate(npages)if nc in p]
                    if len(hits)==1:matches+=hits;method='exact_unique_caption'
                    else:
                        oldcap=[a for a in old.get('anchors',[])if a.get('kind')=='caption'and a.get('pdf_pages')and (a.get('source_file')==origin(cap['source_offset'])['file'])and abs((a.get('source_line')or 0)-origin(cap['source_offset'])['line'])<=4]
                        anchored={p for a in oldcap for p in a['pdf_pages']}
                        if len(anchored)==1:matches+=list(anchored);method='frozen_source_caption_anchor'
            matches=sorted(set(matches))
            scope='UNKNOWN'if len(matches)!=1 else'IN_SCOPE'if job['first']<=matches[0]<=job['last']else'OUT_OF_SCOPE'
            uncertainty=[]
            if root_unknown:uncertainty.append('ambiguous_document_root')
            if container['conditional_depth']:uncertainty.append('conditional_table')
            if not caps:uncertainty.append('caption_absent')
            if scope=='UNKNOWN':uncertainty.append('page_localization_unknown')
            if any(g['environment'].startswith(('long','xltabular','supertabular'))for g in parsed):uncertainty.append('cross_page_extent_unverified')
            for gi,g in enumerate(parsed):
                g['id']=f'grid-{gi:02d}';g['source']=origin(g['source_start'])
                if any(c['unknown_macros']for c in g['cells']):g['issues'].append('unresolved_cell_macros_present')
                for point in g['numeric_points']:
                    point['id']=g['id']+'-'+point['id']
                    if uncertainty:point['status']='UNKNOWN';point['uncertainty_reasons']+=uncertainty
            table={'id':job['id']+f':table-{len(paper["tables"]):03d}','job_id':job['id'],'family':paper['family'],'source':origin(container['start']),'source_offset':container['start'],'source_raw_sha256':sha(source[key[0]:key[1]].encode()),'environment':container['name'],'captions':caps,'pages':matches,'page_method':method,'scope':scope,'complexity':'complex'if reasons else'ordinary','complexity_reasons':reasons,'source_uncertainty':uncertainty,'grids':parsed,'required_numeric_point_candidates':sum(len(g['numeric_points'])for g in parsed),'trusted_numeric_points':sum(p['status']=='TRUSTED'for g in parsed for p in g['numeric_points']),'status':'UNKNOWN'if uncertainty or any(g['issues']for g in parsed)else'PARSED_SOURCE','ordinary_requirement':'all required points/labels/structure correct','complex_requirement':'error proportion <=0.05 per source table; unknown is not pass'}
            tables.append(table);paper['tables'].append(table['id'])
        papers.append(paper)
    obj={'version':'w3-table-source-oracle-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':'SOURCE_ONLY_NO_CONVERSION_OR_MAPPER_READ','denominator':'Source numeric-bearing cell candidates with row/column label mapping; one candidate may contain multiple values, which remain UNKNOWN without component semantics. Trusted subset explicitly distinguished. UNKNOWN source/structure/localization never counted as pass.','jobs_source':str(JOBS),'jobs_sha256':sha(JOBS.read_bytes()),'selfchecks':checks,'papers':papers,'tables':tables,'counts':{'papers':len(papers),'tables':len(tables),'table_scope':dict(collections.Counter(t['scope']for t in tables)),'complexity':dict(collections.Counter(t['complexity']for t in tables)),'trusted_numeric_points':sum(t['trusted_numeric_points']for t in tables),'numeric_point_candidates':sum(t['required_numeric_point_candidates']for t in tables),'source_inventory_unknown_papers':sum(p['inventory_status']=='UNKNOWN'for p in papers)}}
    save(ROOT/'oracle.json',obj)
    freeze={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'FROZEN_SOURCE_ONLY','oracle_sha256':sha((ROOT/'oracle.json').read_bytes()),'parser_sha256':sha(pathlib.Path(__file__).read_bytes()),'jobs_sha256':obj['jobs_sha256'],'source_manifest':[{'id':p['id'],'source_sha256':p['source_archive_sha256'],'expected_matches':p['source_hash_matches'],'pdf_sha256':p['pdf_sha256']}for p in papers],'counts':obj['counts'],'no_output_reads':True,'source_only_inputs':['W2R4 jobs.json','R2 oracle job-index.json, source/prose oracle, pdf-text.json','frozen LaTeX source archives']}
    save(ROOT/'freeze.json',freeze);print(json.dumps(obj['counts']))


if __name__=='__main__':main()
