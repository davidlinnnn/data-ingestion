"""Independent source-coordinate table audit; NO model or OCR invocation."""
from pathlib import Path
import json,hashlib
import pypdfium2 as pdfium
R=Path(__file__).resolve().parent;BASE=R.parent/'native-2026-09-13';SRC=Path('/Users/david/work/data-ingestion/docs/fixtures/pdf-s2-candidates-2026-09-13/user-selected')
def norm(x):return ''.join(x.split())
rows=[]
for source,file,page in [('06','2608.27454v1.pdf',8),('07','2509.25164v5.pdf',3)]:
 doc=pdfium.PdfDocument(SRC/file);pg=doc[page-1];tp=pg.get_textpage();height=pg.get_height()
 if source=='06':
  xs=[74,159,220,267,315,385,435,493,523];ys=[85,104]+[104+i*11.82 for i in range(1,5)]+[168+i*11.82 for i in range(5)]+[231+i*11.82 for i in range(5)]+[295+i*11.82 for i in range(5)]+[359+i*11.82 for i in range(5)]+[429]
  # Replaced below by independent source row baseline positions for the Method column.
  methods=[]
  for i in range(tp.count_chars()):
   l,b,r,t=tp.get_charbox(i);ch=tp.get_text_range(i,1)
   if 162<l<215 and 105<height-t<430 and ch.strip():methods.append((height-t,ch,l,t-b))
 else:methods=[]
 # Inspect source line boxes to freeze independent boundaries without parser tables.
 linecol=(160,220,85,432) if source=='06' else (72,204,88,472)
 chars=[]
 for i in range(tp.count_chars()):
  l,b,r,t=tp.get_charbox(i);ch=tp.get_text_range(i,1)
  if linecol[0]<=l<linecol[1] and linecol[2]<height-t<linecol[3] and ch.strip():chars.append((round(height-t,1),l,ch,t-b))
 groups=[]
 for y,x,ch,h in chars:
  found=next((a for a in groups if abs(a['y']-y)<2),None)
  if found is None:found={'y':y,'chars':[],'h':h};groups.append(found)
  found['chars'].append((x,ch))
 groups.sort(key=lambda a:a['y']);lines=[{'top':g['y'],'height':g['h'],'text':''.join(ch for x,ch in sorted(g['chars']))} for g in groups]
 (R/'local'/f'{source}-table-source-lines.json').write_text(json.dumps(lines,indent=2));print(source,lines)
 # Row starts come only from source glyph geometry; endpoints/columns manually selected from rendered table.
 ys=[x['top']-1 for x in lines]+[430 if source=='06' else 473]
 xs=[74,159,220,267,315,385,435,493,523] if source=='06' else [72,203,400,474,540]
 parsed=json.loads((BASE/'local'/f'{source}-{page}.json').read_text())['tables'][0]['data'];gold=[]
 for ri in range(len(lines)):
  for ci in range(len(xs)-1):
   if source=='06' and ci==0 and ri>0 and (ri-1)%5!=0:continue
   rowspan=5 if source=='06' and ci==0 and ri>0 else 1
   text=tp.get_text_bounded(left=xs[ci],bottom=height-ys[ri+rowspan],right=xs[ci+1],top=height-ys[ri])
   cell=next((c for c in parsed['table_cells'] if c['start_row_offset_idx']==ri and c['start_col_offset_idx']==ci),None)
   actual=None if cell is None else cell['text'];exact=actual is not None and norm(actual)==norm(text)
   gold.append(dict(row=ri,col=ci,rowspan=rowspan,source_text=text,parsed_text=actual,exact_whitespace_match=exact,source_bbox=[xs[ci],ys[ri],xs[ci+1],ys[ri+rowspan]],actual_rowspan=None if cell is None else cell['row_span']))
 (R/'local'/f'{source}-table-full-audit.json').write_text(json.dumps(gold,ensure_ascii=False,indent=2))
 print(source,'cells',len(gold),'exact',sum(c['exact_whitespace_match'] for c in gold))
 for c in gold:
  if not c['exact_whitespace_match']:print(c['row'],c['col'],repr(c['source_text'][:100]),repr((c['parsed_text'] or '')[:100]))
 rows.append(dict(source_id=source,page=page,cells=len(gold),exact=sum(c['exact_whitespace_match'] for c in gold),source_oracle='Visually selected column bands; independent PDFium source glyph row starts; full source cell strings kept local; not parser-derived bounding boxes.'))
(R/'table-audit-summary.json').write_text(json.dumps(rows,indent=2))
