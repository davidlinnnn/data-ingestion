"""Summarize frozen probes; explicitly flag confounds without changing anchors."""
import json
from pathlib import Path
r=Path(__file__).resolve().parent
rows=json.loads((r/'scores.json').read_text());crops=json.loads((r/'crop-scores.json').read_text()); summary={}
for profile in ['native','mixed','scanned']:
 selected=[x for x in rows if x['profile']==profile and x['category']!='historical_scan_supplement']
 native={(x['source_id'],x['page']):x for x in rows if x['profile']=='native'}
 eligible=[];confounded=[];invalid=[]
 for x in selected:
  control=native[(x['source_id'],x['page'])]
  native_found={z['anchor'] for z in control['screenshots'] if z['found']}
  for z in x['screenshots']:
   obj=dict(source_id=x['source_id'],page=x['page'],**z)
   (invalid if x['source_id']=='03' and x['page']==4 and z['anchor']=='機關代碼' else confounded if z['anchor'] in native_found else eligible).append(obj)
 summary[profile]=dict(modern_content_anchors_found=sum(z['found'] for x in selected for z in x['content']),modern_content_anchors_total=sum(len(x['content']) for x in selected),screenshot_anchors_not_in_native_control=eligible,screenshot_anchors_confounded_by_native_prose=confounded,invalid_transcription_anchors=invalid)
summary['crop_diagnostics']=dict(found=sum(z['found'] for x in crops for z in x['anchors']),total=sum(len(x['anchors']) for x in crops),scope='Manual 3x page-render crops; not production-selected components or complete image transcription.')
summary['valid_crop_subset']={'found':11,'total':11,'excluded':'03 page4 機關代碼 was a transcription error; source visually says 機關代號. Preserve original 11/12 result, exclude invalid anchor without substituting a passing ground truth after recognition.'}
summary['invalid_probes']=[{'source_id':'03','page':4,'probe':'reading_order','reason':'說明 is a substring of earlier 操作說明; first-occurrence matching creates an invalid order failure. Excluded rather than changing ground truth after recognition.'},{'source_id':'05','page':1,'probe':'reading_order','reason':'No ordered anchors were specified; vacuous True is not a measured historical reading-order pass.'}]
summary['unavailable_metric']='Discarded zero-valued experimental raw-cell introspection; intermediate parser cells were not validly observed by this runner. No attribution of missing text to OCR vs layout is made. All reported recognition-content scores use per-page public Docling export or independent crop OCR.'
(r/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps({k:(v.get('modern_content_anchors_found'),v.get('modern_content_anchors_total')) for k,v in summary.items() if k in ['native','mixed','scanned']}))
