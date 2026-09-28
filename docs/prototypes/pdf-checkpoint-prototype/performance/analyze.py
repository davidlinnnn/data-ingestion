"""Summarize actual measurements, keeping overlapping spans out of wall attribution."""
import json
import statistics as s
from pathlib import Path
ROOT=Path(__file__).resolve().parent
E=ROOT/'evidence'
M=E/'matrix'
def union(spans):
    total=0;end=-1
    for a,b in sorted(spans):
        total+=max(0,b-max(a,end));end=max(end,b)
    return total
def dist(values):
    return {'n':len(values),'median':s.median(values),'min':min(values),'max':max(values)}
index=json.loads((M/'index.json').read_text())
rows=[]
for item in index:
    variant=item.get('variant',Path(item['out']).name.rsplit('-',1)[1])
    folder=M/Path(item['out']).name
    if variant=='whole':
        children=[{'metrics.json':json.loads((folder/'metrics.json').read_text()),'perf.json':json.loads((folder/'perf.json').read_text())}]
    else:children=json.loads((folder/'child-diagnostics.json').read_text())
    row={'fixture':item['fixture'],'variant':variant,'repetition':item['repetition'],'wall_s':item['wall_s'],'warmup_s':item.get('warmup_s',0),'launcher_wall_s':item.get('launcher_wall_s',item['wall_s']),'stage_sums_not_wall':{}}
    for child in children:
        p=child['perf.json'];m=child['metrics.json'];warm=p['session']
        for key,value in {'call_wall_s':p['call_wall_s'],'import_s':0 if warm else p['module_import_once_s'],**p['timing']}.items():row[key]=row.get(key,0)+value
        row['peak_child_rss_bytes']=max(row.get('peak_child_rss_bytes',0),m['peak_rss_bytes']*1024)
        for key,value in m['stage_seconds_sum_not_wall'].items():row['stage_sums_not_wall'][key]=row['stage_sums_not_wall'].get(key,0)+value
        spans=[(x['start'],x['end']) for x in p['stage_spans'] if x['stage'] not in ('model_initialization',)]
        row['stage_union_s']=row.get('stage_union_s',0)+union(spans)
        model_spans=[(x['start'],x['end']) for x in p['stage_spans'] if x['stage'] in ('LayoutModel','TableStructureModel')]
        row['layout_table_union_s']=row.get('layout_table_union_s',0)+union(model_spans)
        row['layout_table_overlap_s']=row.get('layout_table_overlap_s',0)+sum(b-a for a,b in model_spans)-union(model_spans)
        if 'convert_seconds' in m:row['conversion_s']=row.get('conversion_s',0)+m['convert_seconds']
        if m['mode']=='restore':row['assembly_call_s']=p['call_wall_s']
    row['outside_call_and_import_s']=row['wall_s']-row['call_wall_s']-row['import_s']
    if 'io' in item:row['partial_s3_request_s']=item['io']['get_seconds']+item['io']['put_seconds']
    rows.append(row)
summary={}
for fixture in ('scan','native'):
    summary[fixture]={}
    for variant in ('whole','direct','temporal','warm'):
        selected=[r for r in rows if r['fixture']==fixture and r['variant']==variant]
        summary[fixture][variant]={key:dist([r[key] for r in selected]) for key in selected[0] if isinstance(selected[0][key],(float,int)) and key!='repetition'}
        summary[fixture][variant]['stage_sums_not_wall']={key:dist([r['stage_sums_not_wall'].get(key,0) for r in selected]) for key in set().union(*(r['stage_sums_not_wall'] for r in selected))}
result={'trials':rows,'summary':summary}
(E/'analysis.json').write_text(json.dumps(result,indent=2))
for f,variants in summary.items():
    for v,metrics in variants.items():print(f,v,json.dumps({k:round(metrics[k]['median'],3) for k in ('wall_s','warmup_s','import_s','call_wall_s','conversion_s','outside_call_and_import_s','stage_union_s','method_fingerprint_s')}))
