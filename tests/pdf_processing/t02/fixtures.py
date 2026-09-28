"""Small explicit native PDF fixtures; not multilingual quality evidence."""
from pathlib import Path
import sys
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pdfencrypt import StandardEncryption

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
for name, pages, size, encryption in [
    ('native-review.pdf', 3, (612,792), None),
    ('password.pdf', 1, (612,792), StandardEncryption('secret')),
    ('too-many-pages.pdf', 101, (612,792), None),
    ('too-many-pixels.pdf', 1, (10000,10000), None),
]:
    canvas = Canvas(str(out/name), pagesize=size, encrypt=encryption, invariant=1)
    for page in range(pages):
        canvas.drawString(72, size[1]-72, f'T02 native contract fixture page {page+1}')
        canvas.drawString(72, size[1]-100, 'Captured sources remain independent from canonical acceptance.')
        canvas.showPage()
    canvas.save()
(out/'invalid.pdf').write_bytes(b'not a PDF')
(out/'too-many-bytes.pdf').write_bytes(b'%PDF-1.7\n'+b'0'*(5*1024*1024))
