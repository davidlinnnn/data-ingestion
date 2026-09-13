"""READ ONLY evidence reassessment. No parser/model/OCR calls, no new recognition."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;N=R.parent/'native-2026-09-13';T=R.parent/'real-2026-09-13'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(t):return ''.join(t.split())
results={'mode':'Existing-artifact-only reassessment; proposed oracles are not user-approved or retroactively passing original probes.','original_plans':{'native':sha(N/'plan.json'),'tc':sha(T/'plan.json')},'pages':[]}
plan=load(N/'plan.json')
for case in plan['pages']:
 stem=f'{case["source_id"]}-{case["page"]}';p=N/'local'/f'{stem}.json';j=load(p)
 results['pages'].append({'source_id':case['source_id'],'physical_page':case['page'],'printed_page':case['printed'],'parsed_sha256':sha(p),'nonempty_body_items':len([x for x in j['texts'] if x['text'] and x.get('content_layer')=='body']),'typed_items':[{'ref':x['self_ref'],'type':x['label'],'pages':[p['page_no'] for p in x['prov']]} for x in j['texts'] if x['label'] in ['formula','code','footnote']]})
j=load(N/'local/08-86.json');code=next(x for x in j['texts'] if x['label']=='code')
# Newly explicit token-order oracle transcribed from the existing viewed source, not approved acceptance.
expected=['persistent','seq','state','goal','problem','state ← UPDATE-STATE','if seq is empty then','goal ← FORMULATE-GOAL','problem ← FORMULATE-PROBLEM','seq ← SEARCH','if seq = failure then return a null action','action ← FIRST','seq ← REST','return action']
start=0;observed=[]
for e in expected:
 pos=norm(code['text']).find(norm(e),start);observed.append({'expected':e,'found_in_order':pos>=0})
 if pos>=0:start=pos+len(norm(e))
results['code_proposed_oracle']={'ref':code['self_ref'],'status':'proposal_for_review_not_approved_acceptance','checks':observed,'caption_refs':code['captions'],'limitation':'Whitespace comparison verifies token order only; block indentation/branch association needs source-aware review, not an executable-code claim.'}
# Corrected paragraph is a separately named retrospective proposal, never replacement of frozen plan.
corrected='The preceding elements define a problem and can be gathered into a single data structure that is given as input to a problem-solving algorithm. A solution to a problem is an action sequence that leads from the initial state to a goal state. Solution quality is measured by the path cost function, and an optimal solution has the lowest path cost among all solutions.'
j=load(N/'local/08-87.json');found=[x['self_ref'] for x in j['texts'] if norm(x['text'])==norm(corrected)]
results['corrected_paragraph_proposal']={'source_id':'08','page':87,'status':'new_review_proposal_original_invalid_oracle_preserved','expected':corrected,'exact_existing_text_item_matches':found}
j=load(N/'local/08-104.json');results['footnotes_and_margin_notes']={'footnotes':[{'ref':x['self_ref'],'text':x['text'],'has_source_provenance':bool(x['prov'])} for x in j['texts'] if x['label']=='footnote'],'margin_note_refs':[x['self_ref'] for x in j['texts'] if x['text']=='DEPTH-FIRST SEARCH'],'native_text_order':'Margin note appears before body in export; not accepted as semantic reading order.','decision_pending':'Meaningful Greek/dash/superscript representation, footnote markers and margin-note association must be reviewed without silent normalization.'}
results['unchanged_structural_results']={'tables':[{'source_id':x['source_id'],'page':x['page'],'tables':x['tables']} for x in load(N/'scores.json') if x['tables']],'typed_relationships':load(N/'review.json')['typed_source_caption_links']}
results['tc_evidence']=load(T/'summary.json')
(R/'static-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print('Static reassessment complete:',len(results['pages']),'pages; code ordered probes',sum(x['found_in_order'] for x in observed),'/',len(observed),'corrected paragraph matches',found)
