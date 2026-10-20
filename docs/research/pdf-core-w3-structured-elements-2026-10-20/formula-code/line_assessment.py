"""Derived automatic source-line diagnostics; no Q33 verdict inferred."""
from pathlib import Path
import json,importlib.util,difflib,collections
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('s',P/'scoring.py');s=importlib.util.module_from_spec(sp);sp.loader.exec_module(s)
def read(n):return json.loads((P/n).read_text())
def evaluate(u,r):
 source=s.text_source(u);literal=u['env']in {'verbatim','verbatim*','Verbatim','lstlisting','minted','tcblisting'}
 out={}
 for mode in ['RAW','MAPPED']:
  text=r['channels'][mode]['delivered_text'];src=source.splitlines();dst=text.splitlines();ds=[s.code_tokens(x)for x in dst];lines=[];last=-1;inversions=0
  for ix,line in enumerate(src):
   tok=s.code_tokens(line)
   if not tok:continue
   matches=[(s.ratio(tok,t),j)for j,t in enumerate(ds)if t];best=max(matches,default=(0,None),key=lambda x:(x[0],-x[1]));sim,j=best
   exact=bool(j is not None and tok==ds[j]);indent=None
   if literal and exact:indent=(len(line)-len(line.lstrip())==len(dst[j])-len(dst[j].lstrip()))
   if j is not None and sim>=.75:
    if j<last:inversions+=1
    last=j
   lines.append({'source_line_index':ix+1,'source_line':line,'output_line_index':j+1 if j is not None else None,'best_line_similarity':sim,'token_exact':exact,'literal_character_exact':bool(j is not None and line==dst[j]),'literal_indentation_preserved':indent,'candidate_only':True})
  out[mode]={'source_nonempty_lines':len(lines),'source_lines_with_exact_output_line':sum(x['token_exact']for x in lines),'candidate_line_order_inversions':inversions,'lines':lines,'whole_literal_character_exact':source==text if literal else None,'Unicode_normalization':'NONE','rendered_line_wrap_can_create_false_candidates':True}
 return {'unit_id':u['id'],'kind':u['kind'],'env':u['env'],'job_id':u['job_id'],'family':u['family'],'known_gold_denominator':r['known_gold_denominator'],'actual_processed_refs':r.get('actual_processed_refs',[]),'fixed_refs':r['matched_refs'],'literal_environment':literal,'source_macros_unexpanded_not_guessed':not literal,'channels':out,'Q33':'UNADJUDICATED_AUTOMATIC_CANDIDATE'}
def main():
 units={u['id']:u for u in read('oracle.json')['units']};records=[]
 for variant,name in [('E0','e0-delivery-scores.json'),('E1','e1-scores.json')]:
  for r in read(name):
   if r['kind']in {'code','algorithm'}:x=evaluate(units[r['unit_id']],r);x['variant']=variant;records.append(x)
 s.dump(P/'code-line-assessment.json',{'policy':'All source code/algorithm units retained; unknown source scope or unmatched output is UNKNOWN. Exact line, similarity, inversion and indentation are diagnostics only; prose wrapping and source macros preclude automatic semantic verdict. Unicode literal characters preserved. Native delivery order follows body tree, not source lines or texts-array.','records':records,'source_code_algorithm_units':99})
 print(collections.Counter(x['variant']for x in records))
if __name__=='__main__':main()
