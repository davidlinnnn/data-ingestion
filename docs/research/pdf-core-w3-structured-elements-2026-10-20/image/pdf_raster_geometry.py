"""Original PDF raster-object geometry only, no rendering or conversion output reads."""
import pathlib,json,hashlib,collections,datetime
import pypdfium2 as pdfium
from pypdfium2 import raw
ROOT=pathlib.Path(__file__).resolve().parent
JOBS=ROOT.parents[3]/'docs/research/pdf-core-w2-native-coverage-round4-2026-10-20/jobs.json'

def compose(A,B):
 a,b,c,d,e,f=A;g,h,i,j,k,l=B
 return (a*g+c*h,b*g+d*h,a*i+c*j,b*i+d*j,a*k+c*l+e,b*k+d*l+f)
def point(M,q):
 a,b,c,d,e,f=M;x,y=q;return (a*x+c*y+e,b*x+d*y+f)
def clip_count(obj):
 cp=raw.FPDFPageObj_GetClipPath(obj)
 return raw.FPDFClipPath_CountPaths(cp) if cp else 0

def page_objects(page):
 objects=[];errors=[]
 def walk(container=None,anc=(1,0,0,1,0,0),path=(),parent_clips=0,depth=0):
  if depth>24:errors.append({'path':path,'error':'FORM_DEPTH_LIMIT'});return
  count=raw.FPDFFormObj_CountObjects(container) if container else raw.FPDFPage_CountObjects(page)
  for i in range(count):
   rawobj=raw.FPDFFormObj_GetObject(container,i) if container else raw.FPDFPage_GetObject(page,i)
   obj=pdfium.PdfObject(rawobj,page=page,pdf=page.pdf,container=container,level=depth);typ=obj.type;p=path+(i,)
   try:clips=clip_count(obj)
   except Exception:clips=-1
   if typ==raw.FPDF_PAGEOBJ_FORM:
    try:M=obj.get_matrix();matrix=(M.a,M.b,M.c,M.d,M.e,M.f);walk(rawobj,compose(anc,matrix),p,parent_clips+max(0,clips),depth+1)
    except Exception as e:errors.append({'path':p,'error':str(e)})
   elif typ==raw.FPDF_PAGEOBJ_IMAGE:
    try:
     q=[point(anc,pt) for pt in obj.get_quad_points()];xs=[pt[0] for pt in q];ys=[pt[1] for pt in q];box=[min(xs),min(ys),max(xs),max(ys)];w,h=obj.get_px_size();pw,ph=page.get_size();inter=[max(0,box[0]),max(0,box[1]),min(pw,box[2]),min(ph,box[3])];area=max(0,box[2]-box[0])*max(0,box[3]-box[1]);ia=max(0,inter[2]-inter[0])*max(0,inter[3]-inter[1]);objects.append({'id':'image-'+'.'.join(map(str,p)),'object_path':p,'form_depth':depth,'bbox_bottomleft':box,'quad_bottomleft':q,'pixel_size':[w,h],'ancestor_matrix':anc,'clip_path_count':clips,'ancestor_clip_path_count':parent_clips,'bbox_area':area,'page_intersection_area':ia,'page_intersection_fraction':ia/area if area else None,'source_visibility':'OUTSIDE_PAGE' if not ia else 'UNKNOWN_CLIP_OR_OCCLUSION' if clips or parent_clips else 'RASTER_GEOMETRY_ON_PAGE_NO_KNOWN_CLIP','geometry_method':'FPDFPageObj_GetRotatedBounds then compose containing Form XObject matrices; original PDF, no render'})
    except Exception as e:errors.append({'path':p,'error':str(e)})
 walk();return objects,errors

def main():
 jobs=json.loads(JOBS.read_text())['jobs'];papers=[]
 for j in jobs:
  pdf=pdfium.PdfDocument(j['pdf']);pages=[]
  for no in range(j['first'],j['last']+1):
   page=pdf[no-1];objs,errors=page_objects(page);pages.append({'page':no,'dimensions':list(page.get_size()),'raster_objects':objs,'errors':errors});page.close()
  pdf.close();papers.append({'job_id':j['id'],'family':j['family'],'pdf':j['pdf'],'pdf_sha256':hashlib.sha256(pathlib.Path(j['pdf']).read_bytes()).hexdigest(),'pages':pages});print(j['id'],sum(len(p['raster_objects']) for p in pages),flush=True)
 out={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_only':True,'no_render':True,'no_conversion_output_reads':True,'papers':papers,'summary':{'papers':len(papers),'pages':sum(len(p['pages']) for p in papers),'raster_objects':sum(len(pg['raster_objects']) for p in papers for pg in p['pages']),'errors':sum(len(pg['errors']) for p in papers for pg in p['pages'])}}
 (ROOT/'pdf-raster-geometry.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(out['summary'])
if __name__=='__main__':main()
