"""Checked-storage acceptance with synthetic one-page data; no inference claims."""
import copy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from consumer import Consumer, ROOT, sha
from pdf_processing.object_store import Store
from pdf_processing.processing import encoded
from pdf_processing.relationships import build
from test_publication import MemoryS3


class DurableConsumer(unittest.TestCase):
    def fixture(self, root, mutation=None):
        store = Store(MemoryS3(), 'test', 'q04-local')
        source = b'private synthetic source bytes'
        digest = sha(source)
        request = {'version':3,'request_id':'local','source_revision':'local', 'artifact':{'sha256':digest}}
        profile = {'id':'native-v1','content_evidence': {'relationships': {'method':'local-function-block-v1',
            'coverage':{'mode':'unknown'},'unresolved':'allow_unknown'}}}
        producer = {p.name:sha(p.read_bytes()) for p in (ROOT/'src/pdf_processing').glob('*.py')}
        doc = {'body': {'self_ref':'#/body','children':[]}, 'furniture':{'self_ref':'#/furniture','children':[]},
            'texts':[], 'tables':[], 'pictures':[], 'groups':[], 'pages':{'1':{'size':{'width':10,'height':10}}}}
        refs=root/'references';refs.mkdir()
        (refs/'native.json').write_text(json.dumps(doc)); (root/'oracles').mkdir()
        picture=BytesIO();Image.new('RGB',(1,1),'white').save(picture,format='PNG'); png=picture.getvalue()
        page={'artifact':'page-1.png','sha256':sha(png),'physical_page':1,'original_physical_page':1,
            'size_points':[10,10],'pixel_dimensions':[1,1]}
        report={'source':request,'assembly':'assembly','parsed_result':'parsed','document_sha256':sha(encoded(doc)),
            'pages':{'1':page},'items':[{'ref':'#/'+name,'actual_type':'group','text':None,'collection':name,
                'parent':None,'children':[],'captions':[],'regions':[]} for name in ('body','furniture')]}
        relations=build(doc,request,'parsed','assembly',profile['content_evidence']['relationships'])
        final={'plan':'plan','source':request,'parsed_result':'parsed','assembly':'assembly','selection':'selection',
            'content_evidence':'evidence','relationships':'relationships','enrichments':[],
            'processing_complete':True,'quality_accepted':False,'canonical_accepted':False,
            'provenance':{'profile':profile,'producer':producer},
            'required_work':{'pages':1,'components':0,'ocr':'not_applicable','relationships':'finished'}}
        plan={'profile':profile,'producer':producer,'request':request,'groups':[[1,1]]}
        documents={'plan':{'plan.json':encoded(plan)}, 'assembly':{'document.json':encoded(doc)},
            'parsed':{'parsed-result.json':encoded({'plan':'plan','source':request,'assembly':'assembly','page_groups':['group']})},
            'selection':{'selection.json':encoded({'plan':'plan','source':request,'assembly':'assembly','parsed_result':'parsed','selected':[],'ocr_method':{}})},
            'group':{'complete.json':encoded({'source_sha256':digest,'pages':[{'file':'1.json'}]}),'checkpoints/1.json':encoded({'page_no':1})},
            'evidence':{'content-evidence.json':encoded(report),'source.pdf':source,'original-source.pdf':source,'page-1.png':png},
            'relationships':{'relationships.json':encoded({'content_evidence':'evidence','relationships':relations})},
            'final':{'processing-result.json':encoded(final)}}
        if mutation:mutation(documents)
        for identity, files in documents.items(): store.publish(identity, files)
        result={'status':'complete','processing_complete':True,'processing_result':'final', 'steps':[
            {'stage':'group','operation':'group'},{'stage':'assembly','operation':'assembly'}]}
        fixture={'id':'native','source_revision':'local','sha256':digest,'original_sha256':digest,'original_pages':[1]}
        return store,result,request,profile,fixture

    def test_durable_unknown_is_complete_only_with_every_artifact_and_exact_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store,result,request,profile,fixture=self.fixture(root)
            accepted=Consumer(store,root/'result').verify(result,request,profile,fixture,root/'oracles')
            self.assertEqual(accepted['checks']['items'],2)
            self.assertFalse(accepted['final']['quality_accepted'])
            registration=store.resolve('evidence')
            page=next(f for f in registration['files'] if f['name']=='page-1.png')
            del store.client.objects[page['key']]
            with self.assertRaisesRegex(Exception, 'committed_payload_missing'):
                Consumer(store,root/'retry').verify(result,request,profile,fixture,root/'oracles')

    def test_rejects_self_consistently_hashed_but_unreadable_page(self):
        def corrupt(files):
            files['evidence']['page-1.png']=b'not an image'
            report=json.loads(files['evidence']['content-evidence.json'])
            report['pages']['1']['sha256']=sha(b'not an image')
            files['evidence']['content-evidence.json']=encoded(report)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store,result,request,profile,fixture=self.fixture(root,corrupt)
            with self.assertRaises(Exception):
                Consumer(store,root/'result').verify(result,request,profile,fixture,root/'oracles')

    def test_missing_required_checkpoint_rejected(self):
        def corrupt(files):files['group']['checkpoints/1.json']=encoded({'page_no':2})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store,result,request,profile,fixture=self.fixture(root,corrupt)
            with self.assertRaisesRegex(ValueError,'checkpoint page coverage'):
                Consumer(store,root/'result').verify(result,request,profile,fixture,root/'oracles')
