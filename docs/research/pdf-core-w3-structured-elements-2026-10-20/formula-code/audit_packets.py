from pathlib import Path
import json,hashlib,importlib.util
import pypdfium2 as pf
ROOT=Path(__file__).resolve().parent;W3=ROOT.parent;REPO=ROOT.parents[3]
def load(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 units={u['id']:u for u in load(ROOT/'oracle.json')['units']};e0={r['unit_id']:r for r in load(ROOT/'e0-scores.json')};e1={r['unit_id']:r for r in load(ROOT/'e1-scores.json')};sel=load(ROOT/'audit50-current-selection.json')['selection'];jobs={j['id']:j for j in load(REPO/'docs/research/pdf-core-w2-native-coverage-round4-2026-10-20/jobs.json')['jobs']};base=ROOT/'audit';base.mkdir(exist_ok=True);(base/'source-pages').mkdir(exist_ok=True);(base/'packets').mkdir(exist_ok=True);manifest=[]
 extra=[{'unit_id':r['unit_id'],'hash':hashlib.sha256(r['unit_id'].encode()).hexdigest(),'stratum':r['channels']['MAPPED']['status']}for r in e1.values()if r['kind']!='formula'and r['actual_processed_refs']]
 for c in sel+extra:
  uid=c['unit_id'];u=units[uid];a=e0[uid];b=e1[uid];jid=u['job_id'];key=uid.replace(':','__');images=[];doc=None
  for pn in u['pages']:
   path=base/'source-pages'/f'{jid}-p{pn:03d}.png'
   if not path.exists():
    if doc is None:doc=pf.PdfDocument(jobs[jid]['pdf'])
    doc[pn-1].render(scale=1.6).to_pil().save(path)
   images.append({'page':pn,'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
  if doc:doc.close()
  packet={'unit_id':uid,'audit_hash':c['hash'],'current_stratum':c['stratum'],'job_id':jid,'kind':u['kind'],'family':u['family'],'source_file':u['source_file'],'source_line':u['source_line'],'source_raw_latex':u['raw'],'source_rows':u.get('rows',[]),'source_pages':u['pages'],'source_page_status':u['page_status'],'surrounding_body_anchors':u.get('surrounding_body_anchors'),'source_images':images,'fixed_E0_refs':a['matched_refs'],'E0_items':a['native_items'],'E0_channels':a['channels'],'actual_E1_processed_refs':b['actual_processed_refs'],'E1_items':b['native_items'],'E1_channels':b['channels'],'E1_delivery_modes':b['delivery_modes'],'E1_alignment_integrity':b['alignment_integrity_issues'],'verdict_instruction':'First verify source-unit to fixed native input identity on page image. Wrong equation/row is ORACLE_ALIGNMENT_ERROR, not model error. Then compare E1 active model text to source symbols/terms/signs/indices/powers/conditions. orig is evidence only when nonempty active model text is wrong. Meaning-preserved formatting is acceptable; change/loss of necessary content is CONFIRMED_BLOCKING. If incomplete context cannot decide, UNKNOWN. Independent processing and matching flags are not Q4 verdicts.'};dump(base/'packets'/(key+'.json'),packet);manifest.append({'unit_id':uid,'audit_hash':c['hash'],'job_id':jid,'stratum':c['stratum'],'source_pages':u['pages'],'packet':str((base/'packets'/(key+'.json')).resolve())})
 dump(base/'current-manifest.json',[r for r in manifest if units[r['unit_id']]['kind']=='formula']);dump(base/'code-manifest.json',[r for r in manifest if units[r['unit_id']]['kind']!='formula']);print(len(manifest))
if __name__=='__main__':main()
