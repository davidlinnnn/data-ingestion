"""Bounded literal image text and legitimate no-text/no-picture controls."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',32)
for name, texts in [('multiple',['ALPHA 12345','BETA 67890']),('blank',['']),('none',[])]:
    c=canvas.Canvas(str(out/(name+'.pdf')),pagesize=(600,800))
    c.drawString(30,770,'Component OCR verification '+name)
    for i,text in enumerate(texts):
        image=Image.new('RGB',(900,300),'white');draw=ImageDraw.Draw(image)
        draw.rectangle((5,5,895,295),outline='black',width=4)
        for n,color in enumerate(('red','blue','green','orange','purple','cyan')):
            draw.ellipse((40+n*125,30,150+n*125,150),fill=color)
        if text: draw.text((50,200),text,font=font,fill='black')
        path=out/(name+str(i)+'.png');image.save(path)
        c.drawImage(str(path),50,480-i*220,width=450,height=150)
    c.save()
# Supported page geometry is deliberately bounded; selected rotated pictures fail.
import pypdfium2 as pdfium
with pdfium.PdfDocument(out/'blank.pdf') as document:
    page=document[0];page.set_rotation(90);page.close()
    document.save(out/'rotated.pdf')
