"""Summarize Stage4 diagnostics; does not alter any source or earlier stage."""
import collections
import csv
import hashlib
import json
import random
import re
import statistics
from pathlib import Path

from metrics import levenshtein, selfcheck

P=Path(__file__).resolve().parent
W3=P.parents[1]/'pdf-core-w3-structured-elements-2026-10-20/formula-code'


def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def main():
    records=json.loads((P/'per-unit.json').read_text());summary=json.loads((P/'summary.json').read_text())
    check=selfcheck()
    def dp(a,b):
        row=list(range(len(b)+1))
        for i,x in enumerate(a,1):
            nxt=[i]
            for j,y in enumerate(b,1):nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(x!=y)))
            row=nxt
        return row[-1]
    rng=random.Random(20261020)
    for _ in range(300):
        a=''.join(rng.choices('abc①≤ \n',k=rng.randrange(30)));b=''.join(rng.choices('abc①≤ \n',k=rng.randrange(30)))
        assert levenshtein(a,b)==dp(a,b)
    check['myers_crosschecked_against_independent_DP']=300
    check['all_source_units_retained']=len(records)==99
    check['four_alignment_errors_excluded']=summary['four_alignment_errors_not_primary']
    check['target_data_read_by_synthetic_selfcheck']=check.pop('target_data_read')
    check['assessment_reads_saved_targets']=True
    assert check['all_source_units_retained'] and check['four_alignment_errors_excluded']
    common=[r for r in records if r['tri_source_comparable']]
    common_stats={}
    for c in ['native','E0_RAW','E0_MAPPED','E1_RAW','E1_MAPPED']:
        ms=[r['channels'][c]['metrics'] for r in common]
        common_stats[c]={'units':len(ms),'raw_CER_p50':statistics.median(m['raw']['CER'] for m in ms),
                         'raw_CER_max':max(m['raw']['CER'] for m in ms),
                         'no_whitespace_CER_p50':statistics.median(m['whitespace_removed_diagnostic']['CER'] for m in ms),
                         'operator_sequence_exact_units':sum(m['operator_sequences']['exact'] for m in ms),
                         'number_sequence_exact_units':sum(m['number_sequences']['exact'] for m in ms),
                         'paired_lines':sum(sum(x['operation']=='PAIR' for x in m['line_alignment']) for m in ms),
                         'unpaired_source_lines':sum(sum(x['operation']=='DELETE' for x in m['line_alignment']) for m in ms),
                         'unpaired_target_lines':sum(sum(x['operation']=='INSERT' for x in m['line_alignment']) for m in ms),
                         'not_confirmed_semantic_errors':True}
    summary.pop('common_17_same_denominator',None)
    summary['common_fixed_boundary_same_denominator']=common_stats
    summary['native_reconstruction']={'regions':sum('native_evidence'in r for r in records),
        'space_unit_methods':dict(collections.Counter(r['native_evidence']['space_unit_method'] or 'UNKNOWN_VISUAL_HIERARCHY' for r in records if 'native_evidence'in r)),
        'geometry_draft_correction':'Loose font boxes group ascender/descender glyphs; original tight glyph boxes retained. v1 geometric draft retained, not final.'}
    summary['actual_E1_source_units_with_processed_refs']=sum(bool(r['actual_E1_processed_refs']) for r in records)
    summary['actual_E1_unique_job_refs']=len({(r['job_id'],ref) for r in records for ref in r['actual_E1_processed_refs']})
    summary['family_kind_inventory']=dict(collections.Counter(r['family']+' / '+r['kind'] for r in records))
    summary['version']='stage4-v3-extent-guarded'
    summary['boundary_guard_counts']={channel:dict(collections.Counter(r['channels'][channel]['status'] for r in records)) for channel in ['native','E0_RAW','E0_MAPPED','E1_RAW','E1_MAPPED']}
    dump(P/'summary.json',summary)
    dump(P/'inventory.json',{'source_inventory_count':99,'source_oracle_sha256':summary['inputs']['oracle']['sha256'],
                           'units':[{k:v for k,v in r.items() if k not in ['channels','gold_diagnostic']} for r in records]})
    dump(P/'selfchecks.json',check)
    with (P/'per-unit.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['unit_id','kind','scope','identity','gold_representation','manual21','channel','status','source_chars','target_chars','CER','operator_exact','number_exact'])
        for r in records:
            for c,t in r['channels'].items():
                m=t.get('metrics',{});w.writerow([r['unit_id'],r['kind'],r['scope'],r['identity_status'],r['gold_representation'],r['manual_21_subset'],c,t['status'],t['source_chars'],t['target_chars'],m.get('raw',{}).get('CER'),m.get('operator_sequences',{}).get('exact'),m.get('number_sequences',{}).get('exact')])
    old=json.loads((W3/'audit/algorithm-role-review.json').read_text())['records'][0]
    mapping={'in':'∈','notin':'∉','geq':'≥','ge':'≥','leq':'≤','le':'≤','neq':'≠','leftarrow':'←','gets':'←',
             'State':'STATE','If':'IF','Else':'ELSE','EndIf':'END IF','For':'FOR','EndFor':'END FOR','Return':'RETURN','Require':'REQUIRE','Ensure':'ENSURE'}
    mapped=[]
    for i,line in enumerate(old['source_latex'].splitlines(),1):
        original=line
        for command,value in mapping.items():line=re.sub(r'\\'+command+r'\b',lambda _:value,line)
        mapped.append({'source_line_in_block':i,'source_latex':original,'operator_keyword_mapped':line,
                       'remaining_unexpanded_commands':re.findall(r'\\([A-Za-z]+)',line)})
    algo={'unit_id':old['unit_id'],'page':22,'source_image':old['source_image'],
          'fixed_manual_refs':old['manually_verified_refs'],'source_numbered_rows':38,
          'source_rows_present_native_in_order':old['numbered_native_rows_present_in_order'],
          'fixed_command_mapping':mapping,'mapped_source_lines':mapped,
          'primary_CER':'UNKNOWN_UNSUPPORTED_MATH_AND_STYLE_MACROS',
          'critical_manual_comparison':old['E1']['evidence'],
          'E1_refs':old['E1']['manual_matched_processed_refs'],
          'E1_Q33_static_algorithm_logic':old['E1']['Q33_static_algorithm_logic'],
          'RAW_corruption_delivered':old['E1']['RAW_corrupt_active425_delivered'],
          'MAPPED_corruption_delivered':old['E1']['MAPPED_corrupt_active425_delivered'],
          'runtime_execution_verified':False,'gold_or_frozen_alignment_changed':False,
          'scope':'Supplement to known manual identity; does not backfill 19 unknown-scope algorithms.'}
    dump(P/'algorithm-operator-supplement.json',algo)
    lines=['# Stage4：原生 code／E0／E1 三源評估','','所有運算均為既存輸出及 PDF text layer 的零推論分析。LaTeX listing／algorithm 是共同 gold；三種輸出是 native、E0、E1。E0 和 E1 的 RAW／MAPPED 分別列示。',
           '', '## 分母與可比範圍','',
           '凍結 inventory 99 單位全數保留：78 code（70 IN_SCOPE／8 UNKNOWN），21 algorithm（2 IN_SCOPE／19 UNKNOWN）。67 個固定區域已擷取原 PDF 字元，65 個可估空白單位，2 個 algorithm 僅有 x 階層。',
           '', '主要 literal code 字元比較 native／E0 各 13 單位，E1 為 8；三源共同可比為相同的 8 個人工 code。17 個來源身分可核不等於17個獨立字元邊界可比；共同ref／shared superset／E1鄰框混入退出主CER與逐行錯誤分母，整item值另存whole_item_diagnostic_metrics。原人工 21 個均保留，4 個已知跨頁／錯區塊 alignment error 為 UNKNOWN，不算模型漏失。其餘未 E1 enrichment 單位標 NOT_PROCESSED。固定對齊的非人工個案仍是 alignment candidate，不能把 CER 當成獨立人工語意金標。',
           '', '16 個已定位 code 含未展開 LaTeX style macro、2 個已定位 algorithm 含未展開數學表示，主要 CER 不可比較；所有原文、逐行與 token 診斷仍留存。算法沒有泛刪 State／If／For 控制指令。',
           '', '## 相同 8 個獨立邊界共同單位的字元診斷','',
           '| 輸出 | raw CER p50 | raw CER max | 去空白 CER p50（僅診斷） | operator sequence 相同 | number sequence 相同 |',
           '|---|---:|---:|---:|---:|---:|']
    for c,m in common_stats.items():lines.append(f"| {c} | {m['raw_CER_p50']:.4f} | {m['raw_CER_max']:.4f} | {m['no_whitespace_CER_p50']:.4f} | {m['operator_sequence_exact_units']}/{len(common)} | {m['number_sequence_exact_units']}/{len(common)} |")
    lines += ['', 'CER 使用真正 Levenshtein，沒有通過閾值，也不是語意錯率。>1 可由大量鄰框／跨單位內容及行排列差異造成，不能把 source identity／extent 未證的字元多生直接稱為模型幻覺。每單位均保存配對行、未配對行、literal indentation、operator／number 序列；行 edit alignment 亦不能自動判定漏行。',
              '', '## Native 縮排重建與限制','',
              '擷取來自原 PDF glyph bbox，而非 E0.orig；glyph raw index、緊 bbox、loose font bbox 均保存。以 loose font bbox 分行，避免 g、底線、標點因字形高度不同被拆列。單格空白優先使用定位 space bbox；本批可估的 65 區域均由近等寬字型的相鄰 x advance 推導，非 LaTeX 補空白。輸出保存空白單位、x_left、縮排量化殘差、可讀 .txt。估計不是精確原空格證明；無可證單位的 2 algorithm 用 x-level rank 的四格縮排供展示，明確不是原始空格數。',
              '', '初版 tight-bbox 幾何草稿因 ascender／descender 拆列而不適用，已另存 *.v1-geometric-draft.json；最終結果重新評算，不改任何 source、E0 或 E1。這項分析器修正不涉及 conversion。',
              '', '## 算法與語意界線','',
              'P04 p22 Algorithm 1 的手工已知區域另列 algorithm-operator-supplement.json：38/38 原始編號行內容可見。固定映射保留 \\in→∈、\\geq→≥、State／If／For 關鍵字；其他未支援宏仍列 UNKNOWN。原來源及 E0 第14行為 membership ∈，E1 改成 =；第29、33行 e≥2 改成 e>2；else 分支也被改寫。這是已有來源頁圖證實的 static Q33 邏輯變動，RAW／MAPPED 都交付了變動內容，runtime 未執行。沒有因此把另外19個未知 algorithm 算成漏失。',
              '', '原 21 人工 code 的語意判定沿用既有證據：9 preserved、6 Q4 blocking、4 alignment error、2 UNKNOWN。SICA 兩個 printed log 的身分／數值改動是 Q4 忠實交付問題，不能當可執行 Q33 證據；prompt literal 與檔名／條件詞變動也與 runtime 正確性分開。沒有以 CER 自動重判語意。',
              '', '全99個source均套相同extent guard：source↔ref反向索引辨認many-to-one；未有人工作獨立邊界確認的candidate不入主CER，不依source字串切target或補模型。P16 code00003整diff、P08兩code共用ref、P04 code00012共享prompt均標MANY_TO_ONE_BOUNDARY_UNRESOLVED；human原labels維持不動。', '', '主要產物：inventory.json、per-unit.json／csv、summary.json、native-evidence/*.json／txt、selfchecks.json。300 組隨機小字串以獨立 DP 驗證 Myers bit-vector Levenshtein，全部一致。']
    (P/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'common':common_stats,'native':summary['native_reconstruction'],'checks':check},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
