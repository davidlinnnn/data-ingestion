"""Static review of typed source/caption links; does not run inference."""
from pathlib import Path
import json
R=Path(__file__).resolve().parent;plan=json.loads((R/'plan.json').read_text());out=[]
for e in plan['figures']:
 j=json.loads((R/'local'/f'{e["source_id"]}-{e["page"]}.json').read_text());byref={x['self_ref']:x for k in ['texts','pictures','tables'] for x in j.get(k,[])};height=j['pages'][str(e['page'])]['size']['height'];matches=[]
 for item in list(j['pictures'])+[x for x in j['texts'] if x['label']=='code']:
  captions=[byref[x['$ref']]['text'] for x in item.get('captions',[])];norm=lambda t:''.join(t.split())
  if not any(norm(e['caption']) in norm(c) for c in captions):continue
  b=item['prov'][0]['bbox'];actual=[b['l'],height-b['t'],b['r'],height-b['b']] if b['coord_origin']=='BOTTOMLEFT' else [b['l'],b['t'],b['r'],b['b']];a=e['bbox'];inter=max(0,min(a[2],actual[2])-max(a[0],actual[0]))*max(0,min(a[3],actual[3])-max(a[1],actual[1]));area=lambda q:(q[2]-q[0])*(q[3]-q[1]);matches.append(dict(ref=item['self_ref'],type=item['label'],caption_references=item['captions'],page=item['prov'][0]['page_no'],actual_top_left_bbox=actual,source_region_iou=inter/(area(a)+area(actual)-inter)))
 out.append(dict(source_id=e['source_id'],page=e['page'],expected_caption=e['caption'],expected_bbox=e['bbox'],matches=matches))
summary=dict(typed_source_caption_links=out,oracle_review=[dict(source_id='08',page=87,status='Invalid hand transcription; excluded, not retroactively passed',reason='Predeclared paragraph incorrectly says elements of a problem; magnified source and native text both say elements define a problem and. No evidence of faulty source layer from this mismatch.'),dict(source_id='08',page=104,status='Exact character check fails; semantic completeness not adjudicated',reason='Parser uses hyphen instead of em dash, retains footnote marker6 and variant epsilonϵ vs handwrittenε. These differences are preserved; no normalization-based pass substituted.'),dict(source_id='07',page=5,status='Order anchor is ambiguous',reason='Figure3 also appears in body cross-reference; first-occurrence pass does not establish caption position. Typed caption relationship is checked independently.')],adoption='Inconclusive pending reviewed completeness/representation criteria and PPT sample; no current v1 blocker inferred from deferred scanned/faulty-layer scopes.')
(R/'review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print([(x['source_id'],x['page'],[(m['type'],round(m['source_region_iou'],3)) for m in x['matches']]) for x in out])
