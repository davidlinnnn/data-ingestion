"""Official layout-postprocessor replay from frozen raw clusters; no model/backend/conversion."""
import pathlib,json,hashlib
from docling.datamodel.base_models import Page,Cluster
from docling.datamodel.pipeline_options import LayoutPostprocessorOptions
from docling.utils.layout_postprocessor import LayoutPostprocessor
ROOT=pathlib.Path(__file__).resolve().parent;W3=ROOT.parent

def snapshot(cs):return [{'id':c.id,'label':str(c.label),'confidence':c.confidence,'bbox':c.bbox.model_dump(mode='json'),'children':[x.id for x in c.children]} for c in cs]
class Tracked(LayoutPostprocessor):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.calls=[]
 def _remove_overlapping_clusters(self,clusters,cluster_type,*args,**kw):
  before=snapshot(clusters);out=super()._remove_overlapping_clusters(clusters,cluster_type,*args,**kw);self.calls.append({'stage':'_remove_overlapping_clusters','cluster_type':cluster_type,'before':before,'after':snapshot(out)});return out
 def _handle_cross_type_overlaps(self,cs):
  before=snapshot(cs);out=super()._handle_cross_type_overlaps(cs);self.calls.append({'stage':'_handle_cross_type_overlaps','before':before,'after':snapshot(out)});return out

def main():
 idx={i['job_id']:i for i in json.loads((W3/'E0-inputs.json').read_text())['jobs']};cases=[('P-13-2601.01885v3',8),('F-nips_attention',4),('F-arxiv_gradientdescent',4),('F-icml_imagetransformer',5),('P-20-2505.03335v1',28)];results=[]
 for jid,no in cases:
  p=pathlib.Path(idx[jid]['original_conversion_directory']);resultpath=p/'result.json';rawpath=p/'layout-raw.json';obj=json.loads(resultpath.read_text());saved=obj['pages'][no-1];page=Page.model_validate(saved);raw=json.loads(rawpath.read_text())[str(no)]['clusters'];clusters=[Cluster.model_validate(x) for x in raw];optsource=p.parent.parent/'effective-options.json';effective=json.loads(optsource.read_text());opts=LayoutPostprocessorOptions(**{k:effective['layout_options'][k] for k in ['keep_empty_clusters','skip_cell_assignment','create_orphan_clusters']});proc=Tracked(page,clusters,opts);out=proc.postprocess();expected=page.predictions.layout.clusters
  def byid(cs):return {c.id:c.model_dump(mode='json') for c in cs}
  beforeExpected=byid(expected);actual=byid(out);geom=lambda cs:{c.id:{'label':str(c.label),'bbox':c.bbox.model_dump(mode='json'),'children':sorted(x.id for x in c.children)} for c in cs}
  results.append({'job_id':jid,'page':no,'source_result_sha256':hashlib.sha256(resultpath.read_bytes()).hexdigest(),'source_layout_raw_sha256':hashlib.sha256(rawpath.read_bytes()).hexdigest(),'effective_options':opts.model_dump(mode='json'),'raw':snapshot(clusters),'output':snapshot(out),'saved':snapshot(expected),'full_clusters_equal_ignoring_order':actual==beforeExpected,'geometry_label_children_equal_ignoring_order':geom(out)==geom(expected),'calls':proc.calls,'new_model_inferences':0,'new_backend_calls':0})
  print(jid,no,results[-1]['full_clusters_equal_ignoring_order'],results[-1]['geometry_label_children_equal_ignoring_order'],flush=True)
 (ROOT/'layout-zero-inference-replay.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
