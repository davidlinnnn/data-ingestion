"""Small real-render contracts; only the external OCR engine is replaced.

The full Temporal suite separately uses actual RapidOCR. These isolate absent OCR
fields and malformed crops without relying on a recognizer's nondeterminism.
"""
import base64,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import pypdfium2 as pdfium
from rapidocr.utils.output import RapidOCROutput
from reportlab.pdfgen import canvas
from pdf_processing.ocr import execute

class CropContract(unittest.TestCase):
    def fixture(self,root,origin='BOTTOMLEFT'):
        pdf=root/'source.pdf';c=canvas.Canvas(str(pdf),pagesize=(100,100));c.rect(10,10,80,80);c.save()
        with pdfium.PdfDocument(pdf) as doc:
            page=doc[0]; image=page.render(scale=1.5).to_pil().resize((100,100));page.close()
        def inline(image):
            data=io.BytesIO();image.save(data,format='PNG')
            return {'image':{'uri':'data:image/png;base64,'+base64.b64encode(data.getvalue()).decode()}}
        bbox={'l':10,'r':90,'t':90 if origin=='BOTTOMLEFT' else 10,'b':10 if origin=='BOTTOMLEFT' else 90,'coord_origin':origin}
        document={'pages':{'1':inline(image)},'pictures':[{'self_ref':'#/pictures/0','prov':[{'page_no':1,'bbox':bbox}],**inline(image.crop((10,10,90,90)))}]}
        parsed=root/'document.json';parsed.write_text(json.dumps(document))
        return {'pdf':str(pdf),'parsed':str(parsed),'out':str(root/'result'),'component':'#/pictures/0'}

    def test_both_origins_preserve_evidence_with_all_ocr_fields_absent(self):
        for origin in ('BOTTOMLEFT','TOPLEFT'):
            with self.subTest(origin=origin),tempfile.TemporaryDirectory() as tmp:
                req=self.fixture(Path(tmp),origin)
                with patch('rapidocr.RapidOCR',return_value=lambda image:RapidOCROutput()): execute(req)
                report=json.loads((Path(req['out'])/'ocr.json').read_text())
                self.assertEqual([report['texts'],report['scores'],report['boxes']],[[],[],[]])
                self.assertEqual(report['pixel_dimensions'],[240,240])
                self.assertTrue(report['cached_component_pixels_match_coordinates'])

    def test_wrong_cached_crop_fails_before_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            req=self.fixture(Path(tmp));p=Path(req['parsed']);d=json.loads(p.read_text())
            d['pictures'][0]['image']=d['pages']['1']['image'];p.write_text(json.dumps(d))
            with patch('rapidocr.RapidOCR',side_effect=RuntimeError('must not recognize wrong evidence')):
                with self.assertRaises(AssertionError): execute(req)
