"""Post-global-freeze E0 table assessment, derived outputs only; no conversion/inference."""
import collections,decimal,hashlib,html,importlib.util,json,pathlib,re,unicodedata

ROOT=pathlib.Path(__file__).resolve().parent
RESEARCH=ROOT.parent.parent
R3=RESEARCH/'pdf-core-w2-native-coverage-round3-2026-10-20'
R4=RESEARCH/'pdf-core-w2-native-coverage-round4-2026-10-20'


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


source=load_module('source_table_parser',ROOT/'build_source_oracle.py')
mapper=load_module('frozen_w2_mapper',R4/'mapper/map_documents.py')


def save(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def sha(data):return hashlib.sha256(data).hexdigest()
def labelnorm(text):return source.norm(text)
def ref(ref):return ref.get('$ref',ref.get('cref'))if isinstance(ref,dict)else ref
def words(text):return re.findall(r'[^\W_]+',unicodedata.normalize('NFKD',text).casefold())
def valuekey(text):
    text=unicodedata.normalize('NFKD',text).replace('−','-')
    return re.sub(r'\s+','',text)


def samevalue(left,right):
    a,b=valuekey(left),valuekey(right)
    if a==b:return True
    if re.fullmatch(r'[-+]?\d+(?:\.\d+)?%?',a)and re.fullmatch(r'[-+]?\d+(?:\.\d+)?%?',b)and a.endswith('%')==b.endswith('%'):
        return decimal.Decimal(a.rstrip('%'))==decimal.Decimal(b.rstrip('%'))
    return False


def caption_witness(gold,candidate):
    witnesses=[]
    for caption in gold['captions']:
        a=caption['text'];b=candidate['caption_text'];na,nb=labelnorm(a),labelnorm(b)
        if len(na)>=12 and na in nb:witnesses.append({'method':'normalized_full_caption','source':a,'native':b});continue
        wa,wb=words(a),words(b)
        for i in range(max(0,len(wa)-7)):
            gram=wa[i:i+8]
            if any(wb[j:j+8]==gram for j in range(max(0,len(wb)-7))):
                witnesses.append({'method':'exact_eight_word_caption_window','source_window':' '.join(gram),'native':b});break
    return witnesses


def covers(cell,row,col=None):
    good=cell.get('start_row_offset_idx',0)<=row<cell.get('start_row_offset_idx',0)+cell.get('row_span',1)
    return good and (col is None or cell.get('start_col_offset_idx',0)<=col<cell.get('start_col_offset_idx',0)+cell.get('col_span',1))


def label_matches(text,cells):
    n=labelnorm(text)
    return [c for c in cells if n and labelnorm(c.get('text',''))==n]


def row_label_matches(text,cells):
    exact=label_matches(text,cells)
    if exact:return exact
    # Retain an unambiguous row object even when numbers were wrongly packed into its row-header.
    prefix=words(text)
    return [c for c in cells if c.get('row_header')and prefix and words(c.get('text',''))[:len(prefix)]==prefix and source.NUM.findall(c.get('text',''))]


def align_point(point,grid,cells):
    scell=next(c for c in grid['cells']if c['id']==point['cell_id'])
    if point['status']!='TRUSTED':return {'status':'SOURCE_UNKNOWN','reasons':point['uncertainty_reasons']}
    if scell['row_span']!=1 or scell['col_span']!=1:
        return {'status':'SOURCE_UNKNOWN','reasons':['merged_numeric_cell_full_label_association_not_resolved_by_frozen_parser']}
    row_evidence=[];rows=None
    for label in point['row_labels']:
        hits=row_label_matches(label['text'],cells)
        possible={r for c in hits for r in range(c.get('start_row_offset_idx',0),c.get('end_row_offset_idx',c.get('start_row_offset_idx',0)+c.get('row_span',1)))}
        rows=possible if rows is None else rows&possible
        row_evidence.append({'source_label':label,'native_cells':[c['source_cell_ref']for c in hits]})
    col_evidence=[];cols=None
    for label in point['col_labels']:
        hits=label_matches(label['text'],cells)
        possible={col for c in hits for col in range(c.get('start_col_offset_idx',0),c.get('end_col_offset_idx',c.get('start_col_offset_idx',0)+c.get('col_span',1)))}
        cols=possible if cols is None else cols&possible
        col_evidence.append({'source_label':label,'native_cells':[c['source_cell_ref']for c in hits]})
    evidence={'source_row_labels':row_evidence,'source_col_labels':col_evidence,'candidate_rows':sorted(rows or[]),'candidate_cols':sorted(cols or[])}
    if not rows or not cols:return dict(evidence,status='LABEL_ALIGNMENT_UNKNOWN',reasons=['source_labels_not_found_exactly_in_native_cells'])
    hits=[c for c in cells if any(covers(c,r,c0)for r in rows for c0 in cols)]
    if len(rows)!=1 or len(cols)!=1 or len(hits)>1:return dict(evidence,status='ALIGNMENT_AMBIGUOUS',candidate_cells=hits)
    if not hits:
        row,col=next(iter(rows)),next(iter(cols))
        return dict(evidence,status='MISSING_VALUE_CANDIDATE',source_value=point['value_text'],native_value='',native_cell={'source_cell_ref':f'EMPTY_GRID_POSITION/row{row}/col{col}','text':'','start_row_offset_idx':row,'start_col_offset_idx':col,'synthetic_empty_position':True},row_labels_aligned=True,col_labels_aligned=True)
    native=hits[0]
    expected=source.NUM.findall(point['value_text']);actual=source.NUM.findall(native.get('text',''))
    extras=[]
    status='MATCH'if samevalue(point['value_text'],native.get('text',''))else'MISSING_VALUE_CANDIDATE'if not native.get('text','').strip()else'WRONG_VALUE_CANDIDATE'
    if len(expected)==1 and len(actual)>1 and sum(samevalue(expected[0],v)for v in actual)==1:
        status='MATCH_WITH_EXTRA_VALUES_CANDIDATE';extras=[v for v in actual if not samevalue(expected[0],v)]
    return dict(evidence,status=status,native_cell=native,source_value=point['value_text'],native_value=native.get('text',''),extra_value_candidates=extras,row_labels_aligned=True,col_labels_aligned=True)


def native_tables(doc):
    text={t['self_ref']:t for t in doc['texts']};result=[]
    for table in doc['tables']:
        captions=[]
        for r in [*table.get('captions',[]),*table.get('children',[])]:
            item=text.get(ref(r))
            if item and(item.get('label')=='caption'or r in table.get('captions',[]))and item['self_ref']not in [c['self_ref']for c in captions]:captions.append(item)
        cells=[dict(c,source_cell_ref=f"{table['self_ref']}/data/table_cells/{i}")for i,c in enumerate(table.get('data',{}).get('table_cells',[]))]
        result.append({'ref':table['self_ref'],'label':table.get('label'),'pages':[p['page_no']for p in table.get('prov',[])],'prov':table.get('prov',[]),'caption_refs':[c['self_ref']for c in captions],'caption_text':' '.join(c.get('text','')or c.get('orig','')for c in captions),'cells':cells,'rows':table.get('data',{}).get('num_rows'),'cols':table.get('data',{}).get('num_cols')})
    return result


def assess_table(gold,natives,manual_ref=None):
    result={'id':gold['id'],'job_id':gold['job_id'],'family':gold['family'],'complexity':gold['complexity'],'complexity_reasons':gold['complexity_reasons'],'source_scope':gold['scope'],'source_pages':gold['pages'],'source_status':gold['status'],'source_expected_cell_candidates':gold['required_numeric_point_candidates'],'source_trusted_points':gold['trusted_numeric_points'],'detection':'UNKNOWN','alignment':'UNKNOWN','native_candidates':[],'points':[],'structural':[],'visual_reviewed':False}
    if gold['scope']=='OUT_OF_SCOPE':return dict(result,verdict='OUT_OF_SCOPE',reason='source localized outside selected pages')
    if gold['scope']!='IN_SCOPE':return dict(result,verdict='UNKNOWN',reason='source page localization UNKNOWN; not evaluated as missed detection')
    candidates=[n for n in natives if set(n['pages'])&set(gold['pages'])]
    bycaption=[]
    for n in candidates:
        witness=caption_witness(gold,n)
        if witness:bycaption.append((n,witness))
    if manual_ref is not None:
        manual=[n for n in candidates if n['ref']==manual_ref]
        assert len(manual)==1
        bycaption=[(manual[0],[{'method':'manual_original_page_caption_grid_bbox_content_identity','native_ref':manual_ref}])]
    result['native_candidates']=[{'ref':n['ref'],'pages':n['pages'],'caption':n['caption_text']}for n in candidates]
    if len(bycaption)!=1:
        # Content alignment requires at least three independently labelled correct points,
        # never just one same-page candidate or shared numeric values.
        content=[]
        for n in candidates:
            aligned=[align_point(p,g,n['cells'])for g in gold['grids']for p in g['numeric_points']if p['status']=='TRUSTED']
            matches=[a for a in aligned if a['status']=='MATCH']
            labels={(tuple(a['candidate_rows']),tuple(a['candidate_cols']))for a in matches}
            if len(labels)>=3:content.append((n,[{'method':'three_or_more_unique_value_row_col_witnesses','matched_points':len(matches),'positions':sorted(labels)}]))
        if len(content)==1:bycaption=content
        else:return dict(result,verdict='UNKNOWN',reason='no unique caption or multi-point value+row/column source witness',caption_matched_refs=[n['ref']for n,w in bycaption],content_matched_refs=[n['ref']for n,w in content])
    native,witness=bycaption[0]
    result.update(detection='DETECTED',alignment='UNIQUE_SOURCE_WITNESS',native_ref=native['ref'],native_prov=native['prov'],native_label=native['label'],alignment_evidence=witness,native_caption=native['caption_text'])
    for grid in gold['grids']:
        headercells=[c for c in grid['cells']if c['is_header']and c['text']]
        headers=[]
        for h in headercells:
            hits=label_matches(h['text'],native['cells']);headers.append({'source_cell':h['id'],'text':h['text'],'matches':[{'ref':c['source_cell_ref'],'column_header':c.get('column_header'),'row_header':c.get('row_header')}for c in hits]})
        result['structural'].append({'grid':grid['id'],'source_rows':grid['rows'],'native_rows':native['rows'],'rows_equal':grid['rows']==native['rows'],'source_cols':grid['declared_cols'],'native_cols':native['cols'],'cols_equal':grid['declared_cols']==native['cols'],'source_header_status':grid['header_status'],'source_issues':grid['issues'],'header_evidence':headers,'header_roles_all_present':all(h['matches']and any(m['column_header']for m in h['matches'])for h in headers)if headers else None,'multi_grid_mapping':'UNKNOWN'if len(gold['grids'])>1 else'one_grid'})
        for point in grid['numeric_points']:
            result['points'].append({'id':point['id'],'source':point,'assessment':align_point(point,grid,native['cells'])})
    result['point_status_counts']=dict(collections.Counter(p['assessment']['status']for p in result['points']))
    result['source_full_denominator_known']=bool(result['points'])and gold['trusted_numeric_points']==len(result['points'])and not gold['source_uncertainty']and not any(g['issues']for g in gold['grids'])and not any(p['assessment']['status']=='SOURCE_UNKNOWN'for p in result['points'])
    result['known_numeric_error_candidates']=sum(p['assessment']['status']in ('WRONG_VALUE_CANDIDATE','MISSING_VALUE_CANDIDATE')or bool(p['assessment'].get('extra_value_candidates'))for p in result['points'])
    result['unknown_point_assessments']=sum(p['assessment']['status']not in ('MATCH','MATCH_WITH_EXTRA_VALUES_CANDIDATE','WRONG_VALUE_CANDIDATE','MISSING_VALUE_CANDIDATE')for p in result['points'])
    mapped_cellrefs={p['assessment']['native_cell']['source_cell_ref']for p in result['points']if p['assessment'].get('native_cell')}
    native_numeric=[c for c in native['cells']if source.NUM.findall(c.get('text',''))and not c.get('column_header')and not c.get('row_header')]
    result['extra_native_numeric_cell_candidates']=[c for c in native_numeric if c['source_cell_ref']not in mapped_cellrefs]if result['source_full_denominator_known']else[]
    # Neither candidate differences nor a partially trusted subset can become a final FAIL/PASS.
    result['verdict']='PENDING_VISUAL_REVIEW'if result['known_numeric_error_candidates']or result['extra_native_numeric_cell_candidates']else'PENDING_COMPLETE_DELIVERY_CHECK'if result['source_full_denominator_known']and not result['unknown_point_assessments']else'UNKNOWN'
    result['reason']='Native/label comparisons recorded. Final Q13 verdict requires complete denominator/delivery audit or visually confirmed ordinary partial-oracle counterexample.'
    return result


def selfcheck():
    assert samevalue('1.00','1')and not samevalue('1%','1')and not samevalue('-1','1')
    assert not samevalue('1 ms','1 s')
    assert caption_witness({'captions':[{'text':'A unique table caption sufficiently long for exact source identity'}]},{'caption_text':'Table 3: A unique table caption sufficiently long for exact source identity'})
    assert not caption_witness({'captions':[{'text':'Entirely different caption words'}]},{'caption_text':'Different native table'})
    return {'numeric_sign_units_percent_preserved':'PASS','caption_exact_window_witness':'PASS'}


def main():
    globalfreeze=ROOT.parent/'oracle-freeze.json'
    assert globalfreeze.exists(),'Root global seal required before output read'
    freeze=json.loads((ROOT/'freeze.json').read_text());assert freeze['oracle_sha256']==sha((ROOT/'oracle.json').read_bytes())
    oracle=json.loads((ROOT/'oracle.json').read_text());idx={p['id']:p for p in oracle['papers']};jobs=[];results=[]
    for jid in idx:
        path=R3/'runs/V3_B/jobs'/jid/'document.json';raw=path.read_bytes();doc=json.loads(raw)
        mdpath=path.with_name('document.md');md=mdpath.read_text()
        mapped=mapper.map_document(doc);mh,mmd=mapper.render(mapped)
        dest=ROOT/'E0-mapped'/jid;dest.mkdir(parents=True,exist_ok=True);save(dest/'mapped.json',mapped);(dest/'document.html').write_text(mh);(dest/'document.md').write_text(mmd)
        natives=native_tables(doc);paper_results=[assess_table(g,natives)for g in oracle['tables']if g['job_id']==jid]
        for row in paper_results:row['input']={'native_json':str(path),'sha256':sha(raw),'raw_markdown':str(mdpath),'raw_md_sha256':sha(md.encode()),'mapped_html':str(dest/'document.html'),'mapped_md':str(dest/'document.md')}
        save(ROOT/'E0-assessments'/f'{jid}.json',paper_results);results+=paper_results
        jobs.append({'id':jid,'native_tables':len(natives),'source_tables':len(paper_results),'detection':dict(collections.Counter(r['detection']for r in paper_results)),'verdict':dict(collections.Counter(r['verdict']for r in paper_results))})
    save(ROOT/'E0-preliminary.json',{'scope':'Post-global-seal only, no conversion. Native detection common to RAW/MAPPED; delivery-specific evaluation pending. No raw/native candidate is a confirmed Q13 error until evidence review.','oracle_sha256':freeze['oracle_sha256'],'selfchecks':selfcheck(),'jobs':jobs,'counts':{'tables':len(results),'detection':dict(collections.Counter(r['detection']for r in results)),'verdict':dict(collections.Counter(r['verdict']for r in results))},'tables':results})
    print(json.dumps({'tables':len(results),'detection':dict(collections.Counter(r['detection']for r in results)),'verdict':dict(collections.Counter(r['verdict']for r in results))}))


if __name__=='__main__':main()
