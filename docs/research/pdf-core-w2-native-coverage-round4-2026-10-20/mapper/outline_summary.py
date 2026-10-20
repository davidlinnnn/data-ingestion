"""Summarize frozen R3 heading assessments by actual S0 PDFium outline availability."""
import collections
import json
import pathlib

ROOT=pathlib.Path(__file__).resolve().parent.parent
SOURCE=ROOT.parent/'pdf-core-w2-native-coverage-round3-2026-10-20/heading'
STATUS=['correct','level_error','missing','role_error','ambiguous']


def main():
    source=json.loads((SOURCE/'pdfium-integration/summary.json').read_text())
    result={'scope':'Frozen IN_SCOPE section/subsection/subsubsection headings only; run-in paragraphs excluded. Missing is strict normalized unique title/page match failure, not confirmed content omission. Level error does not itself establish Q4 meaning change.','source':str(SOURCE/'pdfium-integration/summary.json'),'groups':[],'jobs':[]}
    for has_outline in [True,False]:
        jobs=[j for j in source['jobs']if bool(j['outline_pdfium_count'])==has_outline]
        before=collections.Counter();after=collections.Counter();papers=collections.Counter();any_error=0;scored=0
        for j in jobs:
            base=json.loads((SOURCE/'jobs'/j['id']/'summary.json').read_text())['b0-n0-s0']['structural_counts']
            before.update(base);after.update(j['structural_counts'])
            papers.update({k:1 for k,v in j['structural_counts'].items()if v})
            errors=any(v for k,v in j['structural_counts'].items()if k!='correct')
            any_error+=errors;scored+=bool(sum(j['structural_counts'].values()))
            result['jobs'].append({'id':j['id'],'family':j['family'],'has_outline':has_outline,'outline_nodes':j['outline_pdfium_count'],'baseline_structural_counts':base,'B_only_structural_counts':j['structural_counts'],'fixed':j['versus_baseline']['fixed'],'new_bad':j['versus_baseline']['new_bad'],'has_any_structural_match_or_level_error':errors,'semantic_Q4':'NOT_INFERRED_FROM_HEADING_STATUS'})
        result['groups'].append({'has_outline':has_outline,'documents':len(jobs),'documents_with_scored_structural_heading':scored,'documents_without_scored_structural_heading':len(jobs)-scored,'baseline':dict(before),'B_only':dict(after),'B_only_documents_with_status':dict(papers),'B_only_documents_with_any_error':any_error,'fixed':sum(j['versus_baseline']['fixed']for j in jobs),'new_bad':sum(j['versus_baseline']['new_bad']for j in jobs)})
    assert sum(g['documents']for g in result['groups'])==36
    assert sum(g['B_only'].get('level_error',0)for g in result['groups'])==79
    assert sum(g['B_only'].get('missing',0)for g in result['groups'])==33
    (ROOT/'heading-outline.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# R3 B-only：有／無 PDF outline 的範圍與殘留標題錯誤','', '只讀 R3 已保存的官方 PDFium outline／評分，未跑 conversion、後處理或模型。`outline_pdfium_count > 0` 定義「有 outline」；這是 PDF 文件本身可由 S0 backend 取得的 bookmark，不是有 LaTeX 原始檔。','', '|組別|篇數（可評／無可評標題）|baseline 正確／層級錯|B-only 正確／層級錯|strict missing／role／ambiguous|修好／新壞|', '|---|---:|---:|---:|---:|---:|']
    for g in result['groups']:
        a=g['B_only'];b=g['baseline'];lines.append(f"|{'有 outline' if g['has_outline']else'無 outline'}|{g['documents']}（{g['documents_with_scored_structural_heading']}／{g['documents_without_scored_structural_heading']}）|{b.get('correct',0)}／{b.get('level_error',0)}|{a.get('correct',0)}／{a.get('level_error',0)}|{a.get('missing',0)}／{a.get('role_error',0)}／{a.get('ambiguous',0)}|{g['fixed']}／{g['new_bad']}|")
    lines.extend(['','|B-only 殘留狀態的篇數（可重疊）|有 outline|無 outline|','|---|---:|---:|'])
    for k in ['level_error','missing','role_error','ambiguous']:
        lines.append(f"|{k}|{result['groups'][0]['B_only_documents_with_status'].get(k,0)}|{result['groups'][1]['B_only_documents_with_status'].get(k,0)}|")
    lines.extend(['',f"有任一上述狀態的篇數：有 outline {result['groups'][0]['B_only_documents_with_any_error']} 篇，無 outline {result['groups'][1]['B_only_documents_with_any_error']} 篇。篇數不能把各狀態列直接相加。",'', '結案口徑：467 個可評結構標題，baseline 正確177／level error254／strict missing33／role1／ambiguous2；B-only 正確352／level error79／strict missing33／role1／ambiguous2。175 個轉正確、0 個由正確轉錯，全來自有 outline 組。無 outline 組沒有規則輸入，因此保留 baseline。Adam 與 Matrix Calculus 沒有本 oracle 可評結構標題，各分屬無／有 outline；不能當標題全對。','', '`level_error` 是和凍結 LaTeX 層級不符，含可能的全篇一致層級偏移；未逐案證明對象／條件／從屬改義，不自動等同 Q4 阻擋。`strict missing` 是正規化標題＋唯一匹配＋頁交叉沒有嚴格對上，也不自動等同內容真漏；role／ambiguous 同樣須另外核對。此表不能當 F01/F02 的新增阻擋事件或整篇通過率。','', '來源：[R3 PDFium integration summary](../pdf-core-w2-native-coverage-round3-2026-10-20/heading/pdfium-integration/summary.json)、[R3 各篇 baseline / B-only 原始評分](../pdf-core-w2-native-coverage-round3-2026-10-20/heading/jobs/)、[凍結評分器](../pdf-core-w2-native-coverage-round2-2026-10-20/heading/assess_headings.py)。逐篇數值與完整有／無 outline 清單見 [heading-outline.json](heading-outline.json)。'])
    (ROOT/'heading-outline.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':main()
