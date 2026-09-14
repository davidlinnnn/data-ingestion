"""Verify original bytes and prepare a contiguous private chapter context."""
import hashlib
import json
from pathlib import Path
import shutil
import pypdfium2 as pdfium

ROOT = Path('/Users/david/work/data-ingestion')
CATALOG = ROOT/'docs/fixtures/pdf-s2-candidates-2026-09-13'
OUT = Path('/private/tmp/t09a-fixtures')
OUT.mkdir(exist_ok=True)
S2 = ROOT/'.scratch/worktrees/pdf-s2-profile-quality/docs/prototypes/pdf-profile-quality-spike'
manifest = json.loads((CATALOG/'manifest.json').read_text())
entries = next(v for v in manifest.values() if isinstance(v, list) and v and isinstance(v[0], dict) and 'id' in v[0])
prior = {x['id']: x for x in json.loads(Path('/private/tmp/t06-fixtures/manifest.json').read_text())}
items = []
for sid in ('native', '06', '07', '08', '09', '10'):
    if sid == 'native':
        inventory = json.loads((ROOT/'docs/prototypes/pdf-checkpoint-prototype/evidence/fixtures.json').read_text())['native']
        original = ROOT/'docs/prototypes/pdf-checkpoint-prototype/fixtures'/inventory['file']
        expected = inventory['sha256']; revision = inventory['source_revision']; pages = list(range(1,52))
    else:
        source = next(x for x in entries if x['id'] == sid)
        original = CATALOG/source['file']; expected = source['sha256']; revision = source['source_revision_reference']
        pages = list(range(99,111)) if sid == '08' else [2,3,4] if sid == '09' else list(range(1,source['pages']+1))
    assert hashlib.sha256(original.read_bytes()).hexdigest() == expected, sid
    target = OUT/(sid+'.pdf')
    with pdfium.PdfDocument(original) as pdf:
        if len(pages) == len(pdf): shutil.copyfile(original,target)
        else:
            derivative = pdfium.PdfDocument.new(); derivative.import_pages(pdf,[n-1 for n in pages]); derivative.save(target); derivative.close()
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    review = {'source_sha256':sha, 'original_pages':{str(i+1):n for i,n in enumerate(pages)}, 'regions':[], 'scope':'T09a bounded source-reviewed regions; other content unreviewed'}
    if sid in prior:
        old = prior[sid]['review']
        for region in old['regions']:
            original_page = old['original_pages'][str(region['page'])]
            if original_page in pages:
                review['regions'].append({**region,'page':pages.index(original_page)+1})
    with pdfium.PdfDocument(target) as pdf:
        inventory = [{'page':i+1,'original_page':pages[i], 'printed_page':pages[i]-19 if sid=='08' else None,
                      'size_points':list(p.get_size()),'native_characters':len(p.get_textpage().get_text_range()),
                      'pixels_scale3':int(p.get_width()*3+.999)*int(p.get_height()*3+.999)} for i,p in enumerate(pdf)]
    items.append({'id':sid,'pdf':str(target),'original':str(original),'original_sha256':expected,'source_revision':revision,
                  'bytes':target.stat().st_size,'review':review,'inventory':inventory})
(OUT/'manifest.json').write_text(json.dumps(items,indent=2))
print([(x['id'],len(x['inventory']),x['bytes'],max(p['pixels_scale3'] for p in x['inventory'])) for x in items])
