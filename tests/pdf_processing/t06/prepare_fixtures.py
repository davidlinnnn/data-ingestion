"""Build bounded derivatives, original-page maps and source-reviewed region policies.

Run with the existing prototype Python environment. Raw PDFs stay in /private/tmp.
The reviewed S2 regions are inputs, not derived from T06's processing result.
"""
import hashlib,json
from pathlib import Path
import pypdfium2 as pdfium
ROOT=Path('/Users/david/work/data-ingestion')
S2=ROOT/'.scratch/worktrees/pdf-s2-profile-quality/docs/prototypes/pdf-profile-quality-spike'
OUT=Path('/private/tmp/t06-fixtures');OUT.mkdir(exist_ok=True)
sources={}
for folder in ('native-2026-09-13/plan.json','bounded-validation-2026-09-13/new-plan.json'):
    for source in json.loads((S2/folder).read_text())['sources']:sources[source['id']]=source
selections={'06':[4,5,8],'07':[3,5],'08':[86,87,104],'09':[2,3,4],'10':[1]}
items=[]
for sid,pages in selections.items():
    source=sources[sid];path=ROOT/'docs/fixtures/pdf-s2-candidates-2026-09-13'/source['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
    with pdfium.PdfDocument(path) as pdf:
        doc=pdfium.PdfDocument.new();doc.import_pages(pdf,[n-1 for n in pages]);doc.save(OUT/(sid+'.pdf'));doc.close()
    review={'source_sha256':hashlib.sha256((OUT/(sid+'.pdf')).read_bytes()).hexdigest(),
        'original_pages':{str(i+1):p for i,p in enumerate(pages)},'regions':[],
        'scope':'S2 reviewed selected pages; not universal detector qualification'}
    if sid=='09':
        for f in json.loads((S2/'bounded-validation-2026-09-13/formula-evidence.json').read_text()):
            l,t,r,b=f['bbox'];review['regions'].append({'id':'eq'+str(f['equation']),'kind':'formula','page':pages.index(f['physical_page'])+1,
                'bbox':{'l':l,'t':t,'r':r,'b':b,'coord_origin':'TOPLEFT'}})
        plan=json.loads((S2/'bounded-validation-2026-09-13/new-plan.json').read_text())
        for page in plan['pages']:
            if page['source_id']=='09' and page['page']==4:
                for region in page['regions']:
                    if region['type']=='body':
                        l,t,r,b=region['bbox'];review['regions'].append({'id':'symbols-'+region['id'],'kind':'representation','page':3,
                            'bbox':{'l':l,'t':t,'r':r,'b':b,'coord_origin':'TOPLEFT'},
                            'reason':'S2: mathematical minus/overbar representation unconfirmed; retain source; no text correction'})
    if sid=='08':
        old=json.loads((S2/'native-2026-09-13/local/08-104.json').read_text())
        paragraph=next(x for x in old['texts'] if x['self_ref']=='#/texts/6')
        review['regions'].append({'id':'uniform-cost-symbols','kind':'representation','page':3,
            'bbox':paragraph['prov'][0]['bbox'],
            'reason':'S2 uniform-cost paragraph: source-font epsilon/dash representation unconfirmed; note associations source-backed'})
    for original_page in pages:
        old_path=S2/f'native-2026-09-13/local/{sid}-{original_page}.json'
        if sid in ('06','08') and old_path.exists():
            old=json.loads(old_path.read_text())
            for item in old['texts']:
                if item.get('label')=='formula':
                    review['regions'].append({'id':f'formula-{original_page}-{item["self_ref"].split("/")[-1]}',
                        'kind':'formula','page':pages.index(original_page)+1,'bbox':item['prov'][0]['bbox']})
    items.append({'id':sid,'pdf':str(OUT/(sid+'.pdf')),'original':str(path),'original_sha256':source['sha256'],
        'source_revision':source['source_revision_reference'],'review':review})
(OUT/'manifest.json').write_text(json.dumps(items,indent=2))
print([(x['id'],x['review']['original_pages']) for x in items])
