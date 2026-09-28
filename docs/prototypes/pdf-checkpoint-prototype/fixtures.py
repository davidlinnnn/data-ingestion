"""Build a raster-only scan derivative and capture fixture inventory."""
import hashlib
import json
from pathlib import Path
import pypdfium2 as pdfium
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
ROOT = Path(__file__).resolve().parent
native = ROOT / 'fixtures/llm-survey-2303.18223v1.pdf'
scan = ROOT / 'fixtures/scan-pages-3-5.pdf'
doc = pdfium.PdfDocument(native)
c = Canvas(str(scan), invariant=1)
for index in (2, 4):
    page = doc[index]
    c.setPageSize(page.get_size())
    c.drawImage(ImageReader(page.render(scale=2).to_pil()), 0, 0, *page.get_size())
    c.showPage()
c.save()
manifest = {'native': {'file': native.name, 'source': 'https://arxiv.org/pdf/2303.18223v1',
    'acquisition_basis': 'Public research PDF downloaded for local parser evaluation; no redistribution license assumed',
    'source_revision': 'arXiv:2303.18223v1', 'sha256': hashlib.sha256(native.read_bytes()).hexdigest(),
    'pages': len(doc), 'inventory': []},
    'scan': {'file': scan.name, 'sha256': hashlib.sha256(scan.read_bytes()).hexdigest(),
    'derived_from': native.name, 'original_pages': [3, 5], 'render_dpi': 144,
    'description': 'Raster-only derivative; synthetic scan, no physical noise/skew. Native text layer removed.'}}
for i, p in enumerate(doc):
    txt = p.get_textpage().get_text_range()
    manifest['native']['inventory'].append({'page': i+1, 'size_points': p.get_size(),
        'native_characters': len(txt), 'table_mentions': txt.count('TABLE'), 'figure_mentions': txt.count('Fig.'),
        'excerpt': txt[:90]})
(ROOT / 'evidence/fixtures.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({k: {a:b for a,b in v.items() if a != 'inventory'} for k,v in manifest.items()}, indent=2))
