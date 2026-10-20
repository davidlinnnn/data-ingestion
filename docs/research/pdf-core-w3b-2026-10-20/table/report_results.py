"""Summarize immutable source + corrected semantic-table assessment outputs."""
import collections
import hashlib
import json
import pathlib
import statistics

P = pathlib.Path(__file__).resolve().parent
R = P / 'results'


def counts(rows, channel):
    return dict(collections.Counter(r['channel_results'][channel]['verdict'] for r in rows))


def interval(row):
    lo, hi = row.get('error_rate_lower'), row.get('error_rate_upper')
    if lo is None:
        return 'SOURCE N UNKNOWN'
    return f'[{lo:.3%}, {hi:.3%}]' if hi is not None else f'[{lo:.3%}, unresolved upper]'


def main():
    datasets = {name: json.loads((R / f'{name}-v4.json').read_text()) for name in ['E0', 'cellFalse']}
    source = json.loads((P / 'oracle.json').read_text())
    output = {'version': 'v4-qa-corrected-final', 'oracle_sha256': hashlib.sha256((P/'oracle.json').read_bytes()).hexdigest(),
              'inputs': {name: {'path': str(R/f'{name}-v4.json'), 'sha256': hashlib.sha256((R/f'{name}-v4.json').read_bytes()).hexdigest()} for name in datasets},
              'source_counts': source['counts'], 'primary_unit': 'semantic table/caption group, not leaf',
              'variants': {}, 'comparison': {}, 'qa': json.loads((P/'target-audit.json').read_text())}
    for name, data in datasets.items():
        rows = [r for r in data['semantic_tables'] if r['scope'] == 'IN_SCOPE']
        groups = {}
        for channel in ['RAW','MAPPED']:
            cr = [r['channel_results'][channel] for r in rows]
            groups[channel] = {'counts': counts(rows,channel),
                               'family': {family: counts([r for r in rows if r['family']==family],channel) for family in sorted({r['family'] for r in rows})},
                               'Q13': {q:counts([r for r in rows if r['Q13']==q],channel) for q in ['ordinary','complex']},
                               'exact_rate_distribution': {}, 'source_unknown_points': sum(r.get('source_unknown_points',0) for r in cr),
                               'target_unknown_points': sum(r.get('target_unknown_points',0) for r in cr),
                               'unknown_causes': dict(collections.Counter({cause:sum(r.get('unknown_causes',{}).get(cause,0) for r in cr) for cause in {c for r in cr for c in r.get('unknown_causes',{})}}))}
            for q in ['ordinary','complex']:
                exact = [r['error_rate_lower'] for r in cr if r['Q13']==q and r.get('error_rate_lower') is not None and r.get('error_rate_upper')==r['error_rate_lower']]
                groups[channel]['exact_rate_distribution'][q] = {'table_count':len(exact),'p50':statistics.median(exact) if exact else None,'max':max(exact) if exact else None,'values':exact,
                                                              'note':'Only exact known table rates; unknown/lower-bound rates are not inserted as 0 or 1.'}
        output['variants'][name] = {'documents':len(data['documents']), 'papers':data['summary']['papers_loaded'],'channels':groups}
    before={r['id']:r for r in datasets['E0']['semantic_tables']}
    for channel in ['RAW','MAPPED']:
        rows=[]
        for after in datasets['cellFalse']['semantic_tables']:
            if after['scope']!='IN_SCOPE':continue
            b,a=before[after['id']]['channel_results'][channel],after['channel_results'][channel]
            rows.append({'id':after['id'],'job_id':after['job_id'],'family':after['family'],'Q13':after['Q13'],'pages':after['pages'],
                         'before':b['verdict'],'after':a['verdict'],'before_errors':b.get('confirmed_errors'),'after_errors':a.get('confirmed_errors'),
                         'N':after['N'],'before_interval':interval(b),'after_interval':interval(a),
                         'classification':'CONFIRMED_FIXED' if b['verdict']=='FAIL' and a['verdict']=='PASS' else 'CONFIRMED_NEW_BAD' if b['verdict']=='PASS' and a['verdict']=='FAIL' else 'UNKNOWN_TRANSITION' if b['verdict']!=a['verdict'] and 'UNKNOWN' in [b['verdict'],a['verdict']] else 'NO_BINARY_VERDICT_CHANGE'})
        output['comparison'][channel]={'transition_counts':dict(collections.Counter(f"{r['before']}->{r['after']}" for r in rows)),
                                      'confirmed_fixed':[r for r in rows if r['classification']=='CONFIRMED_FIXED'],
                                      'confirmed_new_bad':[r for r in rows if r['classification']=='CONFIRMED_NEW_BAD'],
                                      'unknown_transitions':[r for r in rows if r['classification']=='UNKNOWN_TRANSITION'],
                                      'rows':rows}
    # Contract/regression checks target the discovered failure mechanisms.
    e0=before
    cell={r['id']:r for r in datasets['cellFalse']['semantic_tables']}
    checks={'frozen_source_unchanged':True,
            'p13_packed_header_no_false_extra':e0['P-13-2601.01885v3:html-semantic-table:S4.T5']['confirmed_extra']==0 and e0['P-13-2601.01885v3:html-semantic-table:S4.T5']['verdict']=='UNKNOWN',
            'p19_packed_label_not_claimed_missing_word':e0['P-19-2511.10395v1:html-semantic-table:S7.T6']['verdict']=='UNKNOWN',
            'p19_multiline_raw_header_unknown_mapped_pass':cell['P-19-2511.10395v1:html-semantic-table:S7.T6']['channel_results']['RAW']['verdict']=='UNKNOWN' and cell['P-19-2511.10395v1:html-semantic-table:S7.T6']['channel_results']['MAPPED']['verdict']=='PASS',
            'multi_subtable_native_union':len(e0['P-06-2606.14239v2:html-semantic-table:A6.T12']['native_tables'])==2,
            'all_246_semantic_groups_each_variant':all(len(d['semantic_tables'])==246 for d in datasets.values()),
            'all_183_in_scope_each_variant':all(sum(r['scope']=='IN_SCOPE' for r in d['semantic_tables'])==183 for d in datasets.values())}
    freeze=json.loads((P/'freeze.json').read_text())
    checks['frozen_source_unchanged']=all(hashlib.sha256((P/f).read_bytes()).hexdigest()==h for f,h in freeze['files'].items())
    assert all(checks.values()),checks
    output['selfchecks']=checks
    (P/'summary.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    (P/'selfchecks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    # A full per-table CSV remains easy to consume without reading huge evidence JSON.
    import csv
    with (P/'per-table.csv').open('w') as f:
        writer=csv.writer(f);writer.writerow(['variant','channel','source_id','job','family','Q13','scope','pages','N','source_denominator_status','correct','wrong','missing_tuple','extra_tuple','source_unknown','target_unknown','rate_lower','rate_upper','verdict'])
        for name,data in datasets.items():
            for r in data['semantic_tables']:
                for channel in ['RAW','MAPPED']:
                    x=r['channel_results'][channel];c=x.get('counts',{})
                    writer.writerow([name,channel,r['id'],r['job_id'],r['family'],r['Q13'],r['scope'],','.join(map(str,r['pages'])),r['N'],x.get('denominator_status'),c.get('CORRECT',0),c.get('WRONG',0),c.get('MISSING',0),x.get('confirmed_extra',0),x.get('source_unknown_points',0),x.get('target_unknown_points',0),x.get('error_rate_lower'),x.get('error_rate_upper'),x['verdict']])
    md=['# W3b stage2：表格官方 cell-matching 單變量比較','',
        '來源已先封存；兩版使用同一份246 semantic-table oracle（267 leaf）。183 IN_SCOPE、3 OUT_OF_SCOPE、60來源定位UNKNOWN；IN_SCOPE共7484 numeric components。Adam來源只PDF wrapper，ANSWER_UNAVAILABLE，沒有被當0表。',
        '', 'E0用36篇已保存輸出；cellFalse為root成功的34篇／84interval／175原PDF頁。RAW以實際保存Markdown、官方table export與 markdown_it commonmark+table 真正render檢查；MAPPED使用原三規則mapper的實際HTML／Markdown／JSON，沒有新增表格重建規則。',
        '', '| 版本／出口 | PASS | FAIL | UNKNOWN |','|---|---:|---:|---:|']
    for name in datasets:
        for channel in ['RAW','MAPPED']:
            c=output['variants'][name]['channels'][channel]['counts'];md.append(f"| {name} {channel} | {c.get('PASS',0)} | {c.get('FAIL',0)} | {c.get('UNKNOWN',0)} |")
    md+=['', '這是每張表的Q13判定數量，沒有自創整體通過率。ordinary零錯；complex錯率不超過5%，未裁定或未排除多生不能假作通過。','', '## 按 family 與複雜度','', '| Family | E0 RAW P/F/U | cellFalse RAW P/F/U | cellFalse MAPPED P/F/U |','|---|---|---|---|']
    def pfu(c):return '/'.join(str(c.get(k,0)) for k in ['PASS','FAIL','UNKNOWN'])
    for family in output['variants']['E0']['channels']['RAW']['family']:
        md.append('| '+family+' | '+pfu(output['variants']['E0']['channels']['RAW']['family'][family])+' | '+pfu(output['variants']['cellFalse']['channels']['RAW']['family'][family])+' | '+pfu(output['variants']['cellFalse']['channels']['MAPPED']['family'][family])+' |')
    md+=['','| Q13 | E0 RAW P/F/U | cellFalse RAW P/F/U | cellFalse MAPPED P/F/U |','|---|---|---|---|']
    for q in ['ordinary','complex']:
        md.append('| '+q+' | '+pfu(output['variants']['E0']['channels']['RAW']['Q13'][q])+' | '+pfu(output['variants']['cellFalse']['channels']['RAW']['Q13'][q])+' | '+pfu(output['variants']['cellFalse']['channels']['MAPPED']['Q13'][q])+' |')
    md+=['','## 修好、新壞與 UNKNOWN 遷移','',
         'RAW／MAPPED各確認3張 FAIL→PASS：P11 p8 Table2（B1/F1 tuple）；P13 p9 Table4、p26 Table6（TC數值落入MQ欄的 tuple錯配）。0張 PASS→FAIL。這不等於已證全量零退化：8張原 UNKNOWN→FAIL，前版不能判定，列為新確認阻擋／風險，不能計成已證新壞；FAIL→UNKNOWN也不是已證修好。',
         '', 'P13 p9 Table5 的v2「15 extra」是packed header對齊誤報，v4已UNKNOWN；cellFalse PASS屬UNKNOWN→PASS。P19 p25 Table6 的E0兩個值在Baseline label cell，關係未明，v4亦UNKNOWN；cellFalse MAPPED PASS，RAW父header AppWorld/BFCL變表外段落而UNKNOWN。兩案原QA抽樣固定、不拿新案例替換。',
         '', 'RAW另有P06 p7 Table2同類多行header loss，MAPPED保留標籤且PASS。它是輸出結構的可確認差異；人讀可能推斷，未據此自稱Q4語義阻擋。',
         '', '## 錯率與來源／對齊界線','',
         '逐表確證 wrong/missing/extra tuple、可信來源N、來源未知點、target未知點、錯率下界／上界在per-table.csv及results/*-v4.json。未知extra的上界保留unresolved，不硬塞100%；可超100%的extra計數不截斷。來源分母不可信時不報精確比率。精確錯率分布只納入來源分母可信、所有tuple及extra完整可判的表；未確定的表不塞0或1，分family/Q13機器摘要另列。',
         '', 'MISSING tuple不等於數值字詞漏失；source數值在別的明確metric欄仍可形成錯配／多出tuple，machine記numeric_text_present與lexical_omission_claimed。數值只在packed row-label/header時關係不唯一，UNKNOWN，不把整串依gold zip回多欄算正確，也不全算漏。source caption只定位caption頁；來源physical extent或native text證據不全的absent值保留UNKNOWN，不憑該頁缺值宣稱跨頁漏。相同caption多subgrid可映多native item聯集，不能只取一半就報漏。',
         '', '## QA與定位','',
         '獨立固定seed QA核了原9樣本全部201 numeric components：實際native均保義；RAW有1個header UNKNOWN，MAPPED9個正確。QA指出的packed-header false-extra與多行Markdown header loss已全量修scorer，v1/v2/v3保存，來源gold未變。新增解析修正以明確source/native header完整等同優先，避免MR和MRPC子字串混淆；沒有按文件例外。',
         '', 'cellFalse對照頁rawlayout全部相同（root page-scope-control），觀察到的native cell/grid差異定位table structure/cell matching至組裝階段；RAW父header丟失定位serializer／Markdown表格語法。只定位，不改模型／pipeline。不在本輪實作自訂數列重建。',
         '', '## 產物與限制','',
         'results/E0-v4.json、cellFalse-v4.json含逐semantic table、逐point及兩出口完整證據；delivery/<variant>/<job>/<interval>/保存RAW table片段與實際rendered HTML、mapper三出口與delivery-audit。summary.json保留所有family/Q13、前後可判比較及UNKNOWN遷移；selfchecks.json含source hash、packed-header、multi-native union、RAW/MAPPED分歧等回歸檢查。',
         '', '官方do_cell_matching=False有3張確證整表修好、更多UNKNOWN→PASS，但仍8 FAIL與大量UNKNOWN；可列官方候選，不能據此直接推薦無條件全開或宣稱36篇完整Q4已修好。圖內噪訊、公式和演算法不由此表格結果推論。']
    (P/'report.md').write_text('\n'.join(md)+'\n')
    changelog='''# 分析器修正記錄（source gold未改）

- v1-native：第一輪候選，未驗出口；保留原檔。
- v2-native：共同caption多native union、source/native figure/table身份衝突守門、兩來源row壓成一native row不得當唯一row；保留原檔。
- v3-rendered：加入RAW片段實際保存存在性與MAPPED單次cell交付；此版仍未實際解讀多行Markdown header，保留原檔。
- v4：依獨立QA，短header與packed header全局消歧；優先完整header相等避免MR/MRPC誤碰；packed row-label數值不當必然漏；source physical extent未知不判absent為漏；真正Markdown render後父header不在thead則RAW UNKNOWN。來源cells/points/Q13/定位完全不動。

所有source freeze hashes驗證通過。固定9個QA樣本不因修分析器替換；UNKNOWN→PASS與FAIL→UNKNOWN不冒充已確認阻擋修好。
'''
    (P/'change-log.md').write_text(changelog)
    print(json.dumps({k:v['channels'] for k,v in output['variants'].items()},ensure_ascii=False)[:400])


if __name__=='__main__':main()
