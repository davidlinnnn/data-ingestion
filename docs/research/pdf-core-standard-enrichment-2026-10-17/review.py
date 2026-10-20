"""Source adjudication of the fixed E1 run; never repairs outputs."""
import collections
import hashlib
import json
from pathlib import Path

H=Path(__file__).resolve().parent
P=H.parent/"pdf-core-native-round-2026-10-17"
ROOT=H.parents[2]
contract=json.loads((ROOT/"docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json").read_text())
assert hashlib.sha256((ROOT/"docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json").read_bytes()).hexdigest()=="22ee81e79db28cf07d14ddd1f53269aada08d8b6480633ef67046a3e955777f2"
prior=[r for r in json.loads((P/"unit-review.json").read_text())["units"] if r['profile']=='S0']
assert len(prior)==41
changes={
 'controls/code_item--texts-12':('pass','Comment is once on its own source-faithful line, combined with body in the permitted full-page code block. Body indentation is assessed separately.'),
 'controls/code_item--texts-13':('material','All six statements, <=, +=, quoted ok/skip and relative nesting are recovered. Raw has a common4space offset; official cleanup/language extraction trims only the first comment line. Delivered body indents4/8/8/12/4/8 versus frozen0/4/4/8/0/4. Do not call it a changed else binding or impose executability; exact frozen indentation delivery is still unmet.'),
 'controls/code_item--texts-14':('material','Inline expression gains leading colon from crop, items [ i ] spacing and HTML language tag; remains detached code. Added colon and changed source context prevent full delivery, not a requirement for a particular native label.'),
 'dgm/code_item--texts-646':('material','Identifier/default literals improve, but source f-string \n=== becomes \n== and :.2f becomes ::2f. Context indentation is distorted, and raw includes the adjacent section title plus opening prose; stock writeback duplicates them in the whole document. Source diff is not to be executed or repaired.'),
 'dgm/ordinary_paragraph--texts-648':('material','Original paragraph item with all5inline tokens and23.3%/40.5% bindings is unchanged. However, its opening fragment is duplicated inside the preceding enriched code. Original narrow E04 token/binding positive survives; whole-target source fidelity fails the original no-duplication rule.'),
 'dgm/ordinary_paragraph--texts-649':('material','The ordinary Feature suggestion to obtain node6 label is unchanged, but native expanded code crop/model output repeats it inside the following code block. Source label now appears twice in distinct roles.'),
 'dgm/code_item--texts-650':('material','Both source instruction paragraphs and exact tools/edit.py/edit/str_replace/old_str/new_str literals recovered. Source wrap-arrow reflow is allowed. Added Feature suggestion label from expanded crop duplicates adjacent ordinary label; full source role/boundary delivery fails.'),
 'dgm/code_item--texts-652':('accepted_minor','Complete instruction words and exact quoted editor restored. Angle glyphs occur only at original discretionary printer-wrap locations in instruction prose; treated as meaning-preserving wrap typography under the frozen instruction-prose ambiguity, not source program operators. No output normalization or repair applied. XML language metadata is misleading but not an extra product criterion.'),
 'seal/formula--texts-33':('material','Source inner SE~LM becomes mathbbS in LM, and reward argument SE becomes mathbbS; original equation number1 absent. Real mathematical identifier/operator change exists in raw, not parser-only.'),
 'seal/formula--texts-48':('pass','Both cases1/0, condition, SE/tau/theta_t arguments and equation2 retained as usable native LaTeX in main Markdown. Superscript2 remains after condition text performance and same-page footnote2 body is unchanged; read as visible note reference, not reward square. No new typed hyperlink requirement or assumption that model saw footnote body.'),
 'seal/formula--texts-50':('material','Gradient, -1/NM, i/j sums, r_ij and conditional SE_ij|C_i faithfully reconstructed as usable LaTeX. Required original equation number3 is absent; core math recovery is distinct from complete target delivery.'),
 'seal/formula--texts-51':('material','Negative factor, all3sums, autoregressive history y_<s and conditional distribution faithfully reconstructed. Required original equation number4 absent; no nested-delimiter parser defect here. Core math recovered, full target incomplete.')
}
docs={j:json.loads((H/"E1"/j/"document.json").read_text()) for j in ['controls','wikiskill','seal','dgm']}
pre={j:json.loads((H/"E1"/j/"pre-enrichment.json").read_text()) for j in docs}
rows=[]
for r in prior:
    row=dict(r)
    row['profile']='E1'
    row['historical_S0_delivery_status']=r['delivery_status']
    source=r['source'];refs=r['matched_item_refs']
    indexes=[int(ref.rsplit('/',1)[1]) for ref in refs]
    before=[pre[source]['texts'][i] for i in indexes]
    after=[docs[source]['texts'][i] for i in indexes]
    row['pre_enrichment_text']=[x['text'] for x in before]
    row['matched_text']=[x['text'] for x in after]
    row['own_items_unchanged']=before==after
    row['enriched_item_refs']=[x['self_ref'] for x,y in zip(after,before) if x!=y]
    row['raw_source_fidelity_status']=None
    if r['unit_id'] in changes:
        status,finding=changes[r['unit_id']]
        row['delivery_status']=status;row['findings']=[finding]
    else:
        assert before==after,r['unit_id']
        row['findings']=r['findings']+['Exact selected items unchanged in same-run before/after snapshots; no new capability claimed.']
    rows.append(row)
assert len(rows)==41
# Assertions guard adjudicated evidence, not a token-presence accuracy metric.
code=docs['dgm']['texts'][0]['text']
assert "'N/A')::2f" in code and '== Attempt' in code
assert code.count('D    Similar Target Functionality')==1
assert docs['dgm']['texts'][2]==pre['dgm']['texts'][2]
assert 'Feature suggestion to obtain node 6:' in docs['dgm']['texts'][4]['text']
assert docs['seal']['texts'][101]==pre['seal']['texts'][101]
assert 'Otherwise' in docs['seal']['texts'][95]['text'] and '( 2 )' in docs['seal']['texts'][95]['text']
assert '< s' in docs['seal']['texts'][98]['text']
counts=dict(collections.Counter(r['delivery_status'] for r in rows))
joins=[('wikiskill',5),('wikiskill',16),('seal',69),('seal',78)]
for source,i in joins:
    item=docs[source]['texts'][i]
    assert item==pre[source]['texts'][i] and len(item['prov'])==2
for j in docs:
    assert pre[j]['texts']==json.loads((P/'S0'/j/'document.json').read_text())['texts']
    assert all(pre[j][k]==docs[j][k] for k in pre[j] if k!='texts')
summary=dict(delivery_status_counts=counts,units=41,display_equations=dict(units=4,complete=1,core_math_preserved=3,equations_missing_labels=[1,3,4]),
    recovered_full_delivery_units=['controls/code_item--texts-12','dgm/code_item--texts-652','seal/formula--texts-48'],
    new_duplicate_source_units=['dgm/ordinary_paragraph--texts-648','dgm/ordinary_paragraph--texts-649'],
    four_native_crosspage_joins_preserved=True,untouched_original_anchor_items_preserved=True,
    original_E04_tokens_bindings_preserved=True,full_E04_source_unit_has_new_duplicate_prefix=True,
    candidate_adopted=False,G2_passed=False,output_repairs=0,holdout_reads=0)
(H/'unit-review.json').write_text(json.dumps(dict(method='Original41sourcecontract; manual raw/typed/mainMarkdown inspection of changed targets, exact unchanged-item comparisons to previous source-reviewed S0; no ad-hoc repairs. Narrow original anchor checks separated from full-document duplication.',summary=summary,units=rows),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
