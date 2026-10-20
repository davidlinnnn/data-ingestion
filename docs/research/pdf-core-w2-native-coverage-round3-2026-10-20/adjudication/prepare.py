from pathlib import Path
import json,collections,hashlib
import pypdfium2 as pdfium
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parents[1]/'pdf-core-w2-native-coverage-round2-2026-10-20'
def main():
 jobs={j['id']:j for j in json.loads((OLD/'jobs.json').read_text())['jobs']};catalog=json.loads((ROOT/'catalog-baseline36.json').read_text())
 for jobid in jobs:
  cc=[c for c in catalog if c['job_id']==jobid];pages=sorted({p for c in cc for p in c.get('pages',[])})
  if not pages:continue
  folder=ROOT/'pages'/jobid;folder.mkdir(parents=True,exist_ok=True);doc=pdfium.PdfDocument(jobs[jobid]['pdf']);sheets=[]
  for pn in pages:
   dest=folder/f'p{pn:03d}.png'
   if not dest.exists():
    page=doc[pn-1];page.render(scale=1.5).to_pil().save(dest);page.close()
   im=Image.open(dest).convert('RGB');im.thumbnail((650,880));sheets.append((pn,im.copy()))
  doc.close()
  for k in range(0,len(sheets),4):
   batch=sheets[k:k+4];canvas=Image.new('RGB',(1300,1840),'#d8d8d8');draw=ImageDraw.Draw(canvas)
   for i,(pn,im) in enumerate(batch):
    x=(i%2)*650;y=(i//2)*920;draw.text((x+8,y+5),jobid+' p'+str(pn),fill='black');canvas.paste(im,(x,y+30))
   (ROOT/'sheets').mkdir(exist_ok=True);canvas.save(ROOT/'sheets'/f'{jobid}-{k//4+1:02d}.png')
  print(jobid,len(pages),flush=True)
if __name__=='__main__':main()
