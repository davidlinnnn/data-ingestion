"""Small literal native PDF for recovery; not extraction-quality qualification."""
import sys
from reportlab.pdfgen import canvas

pdf=canvas.Canvas(sys.argv[1],pagesize=(400,500))
for page in range(1,11):
    pdf.drawString(30,450,f'T03 recovery fixture page {page}')
    for row in range(1,20):
        pdf.drawString(30,450-row*18,f'Page {page} row {row}: durable checkpoint evidence.')
    pdf.showPage()
pdf.save()
