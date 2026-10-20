from pathlib import Path
import json,hashlib,pypdfium2 as pf
P=Path(__file__).resolve().parent
ss=json.loads((P/'audit20-selection.json').read_text());jobs={j['job_id']:j for j in json.loads((P.parent/'html-manifest.json').read_text())['jobs']};d=P/'audit-pages';d.mkdir(exist_ok=True)
for u in ss:
 f=d/f"{u['job_id']}-p{u['page']:03d}.png"
 if not f.exists():
  pdf=pf.PdfDocument(jobs[u['job_id']]['pdf']);pdf[u['page']-1].render(scale=1.8).to_pil().save(f);pdf.close()
 u['source_image']={'path':str(f.resolve()),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'page':u['page']}
for name,records in [('audit20-packets.json',ss),('audit-assignment-trace.json',ss[10:]),('audit-assignment-main.json',ss[:10])]:
 (P/name).write_text(json.dumps(records,ensure_ascii=False,indent=2))
print('PACKETS',len(ss),[(u['job_id'],u['page'])for u in ss])
