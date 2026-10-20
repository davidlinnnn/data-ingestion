from pathlib import Path
import collections,json,sys
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parents[1]/'pdf-core-w2-native-coverage-round2-2026-10-20'
sys.path.insert(0,str(OLD));from analyze_full import collect,norm
cat=json.loads((ROOT/'catalog-baseline36.json').read_text());jobmap=json.loads((ROOT.parent/'baseline-inputs.json').read_text());jobs=json.loads((OLD/'jobs.json').read_text())['jobs']
for job in jobs:
 cc=[c for c in cat if c['job_id']==job['id'] and c['kind']!='furniture_in_body']
 if not cc:continue
 data=json.loads((Path(jobmap[job['id']])/'document.json').read_text());items=collect(data);ar={a['anchor_id']:a for a in json.loads((ROOT.parent/'analysis/baseline'/job['id']/'anchors.json').read_text())};groups=collections.defaultdict(list)
 for c in cc:groups[tuple(c.get('anchor_ids',[])) or (c.get('itemref',c['id']),)].append(c)
 lines=['# '+job['id'],'']
 for key,cs in groups.items():
  pages=sorted({p for c in cs for p in c.get('pages',[])})
  lines+=['## '+str(key)+' p'+str(pages),'; '.join(c['id'] for c in cs),'Kinds: '+', '.join(c['kind'] for c in cs)]
  for a_id in key:
   if a_id in ar:
    a=ar[a_id];lines+=['SOURCE: '+a['text'],'SOURCE POS: '+str((a['source_file'],a['source_line'],a['source_offset'])),'MD offsets: '+str(a['markdown_offsets'])]
    refs=set(ref for occ in a['native_all_layers'] for ref in occ['itemrefs'])
    for item in items:
     if item['ref'] in refs:lines+=['NATIVE '+item['ref']+' '+item['label']+' '+item['layer']+' ancestor '+str(item['ancestor_refs'])+': '+item['text']]
  for c in cs:
   if 'text' in c:lines.append('CANDIDATE TEXT: '+c['text'])
 lines+=['','## Full native items on candidate pages']
 pages=sorted({p for c in cc for p in c.get('pages',[])})
 for page in pages:
  lines+=['','### p'+str(page)]
  for item in items:
   if any(p['page_no']==page for p in item['prov']):lines.append(item['ref']+' '+item['label']+' '+item['layer']+' ancestor='+str(item['ancestor_refs'])+': '+item['text'])
 dest=ROOT/'packets';dest.mkdir(exist_ok=True);(dest/(job['id']+'.md')).write_text('\n\n'.join(lines)+'\n')
