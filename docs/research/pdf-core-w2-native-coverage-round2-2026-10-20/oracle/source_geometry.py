"""PDF text geometry only, two sampled body pages; no OCR/inference."""
import collections,json
from pathlib import Path
import pypdfium2 as pdfium
from build_oracle import ROOT,dump

def main():
 jobs=json.loads((ROOT.parent/'jobs.json').read_text())['jobs'];idx=json.loads((ROOT/'job-index.json').read_text());rows=[]
 for job in jobs:
  p=Path(idx[job['id']]);o=json.loads(p.read_text());doc=pdfium.PdfDocument(job['pdf']);samples=[]
  for pn in range(2,min(4,len(doc))+1):
   page=doc[pn-1];tp=page.get_textpage();w,h=page.get_size();lines=collections.defaultdict(list)
   stream_lines=[];boxes=[]
   for i in range(tp.count_chars()):
    ch=tp.get_text_range(i,1)
    if ch in ('\r','\n'):
     if boxes:stream_lines.append(boxes);boxes=[]
     continue
    if not ch.strip():continue
    l,b,r,t=tp.get_charbox(i)
    if b<50 or t>h-45:continue
    boxes.append((l,r))
   if boxes:stream_lines.append(boxes)
   left=right=span=0
   for boxes in stream_lines:
    l=min(x[0] for x in boxes);r=max(x[1] for x in boxes)
    if r-l<40:continue
    if r<w*.54:left+=1
    elif l>w*.46:right+=1
    else:span+=1
   samples.append({'page':pn,'left_lines':left,'right_lines':right,'spanning_lines':span});tp.close();page.close()
  doc.close();left=sum(x['left_lines'] for x in samples);right=sum(x['right_lines'] for x in samples);span=sum(x['spanning_lines'] for x in samples)
  kind='two-column-likely' if left>10 and right>10 and left+right>span*1.5 else 'single-column-likely' if span>left+right else 'mixed/uncertain'
  o['template']['geometry_samples']=samples;o['template']['geometry_class']=kind;dump(p,o);rows.append({'job_id':job['id'],**o['template']})
 dump(ROOT/'family-geometry.json',rows)
if __name__=='__main__':main()
