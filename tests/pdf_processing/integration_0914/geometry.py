"""Exercise the combined producer's evidence writer with bounded synthetic geometry."""
import json
from pathlib import Path
import tempfile

import pypdfium2 as pdfium
from pdf_processing.evidence import execute
from pdf_processing.execution import ChildFailure
from pdf_processing.object_store import digest

def main():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        pdf=pdfium.PdfDocument.new(); page=pdf.new_page(100,100); page.close()
        pdf.save(root/'source.pdf'); pdf.close()
        box={'l':20,'t':30,'r':20,'b':40,'coord_origin':'TOPLEFT'}
        document={'pages':{'1':{'size':{'width':100,'height':100}}},
            'texts':[{'self_ref':'#/texts/0','label':'text','text':'\u0338',
                'prov':[{'page_no':1,'bbox':box}]}]}
        def run(name,doc,review=None):
            path=root/(name+'.json');path.write_text(json.dumps(doc));before=path.read_bytes()
            execute({'out':str(root/name),'pdf':str(root/'source.pdf'),'parsed':str(path),
                'policy':'typed-source-evidence-v1','review':review or {},
                'source':{'artifact':{'sha256':digest((root/'source.pdf').read_bytes())}},
                'parsed_result':'synthetic:parsed','assembly':'synthetic:assembly',
                'max_render_pixels':1000000,'renderer_version':'local-regression'})
            assert path.read_bytes()==before
            return json.loads((root/name/'content-evidence.json').read_text())
        result=run('combining',document)
        item=result['items'][0];region=item['regions'][0]
        assert item['text']=='\u0338' and region['provenance']['bbox']==box
        assert region['crop_recipe']=={'scale':3,'box_pixels':[0,0,300,300],'scope':'full_page_context'}
        assert region['geometry_status']=='zero_width_combining_mark'
        assert result['representation_observations'][0]['text_rewritten'] is False
        assert not result['formula_occurrences']
        for name in ('ordinary','reversed','outside','zero_height','review_overlap'):
            doc=json.loads(json.dumps(document));node=doc['texts'][0];b=node['prov'][0]['bbox'];review=None
            if name=='ordinary':node['text']='x'
            elif name=='reversed':b['r']=19
            elif name=='outside':b['l']=b['r']=-1
            elif name=='zero_height':b['b']=b['t']
            else:review={'source_sha256':digest((root/'source.pdf').read_bytes()),'regions':[{'id':'eq','page':1,'kind':'formula','bbox':{**box,'l':19,'r':21}}]}
            try:run(name,doc,review)
            except ChildFailure:
                code=json.loads((root/name/'failure.json').read_text())['code']
                assert code==('review_region_has_no_typed_content' if name=='review_overlap' else 'region_outside_page'),code
            else:raise AssertionError(name+' unexpectedly accepted')
        print('PASS: evidence writer preserves combining mark/provenance, full-page recipe and uncertainty; five invalid/false-overlap cases rejected')

if __name__=='__main__':main()
