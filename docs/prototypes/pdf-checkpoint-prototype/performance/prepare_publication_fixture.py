"""Host-side pack of the real accepted parsing/assembly outputs, excluding OCR."""
from pathlib import Path
import json
import hashlib
import shutil
ROOT=Path(__file__).resolve().parent.parent
STORE=ROOT/'PROTOTYPE-wipe-me/linux-k8s-evidence/shared-store-export'
OUT=ROOT/'PROTOTYPE-wipe-me/performance-publication-fixture'
assert not OUT.exists(),'Use a fresh fixture directory'
count=0
for reg in (STORE/'linux-normal-final/registered').glob('*.json'):
    manifest=json.loads(reg.read_text())
    if any(x['name']=='ocr.json' for x in manifest['files']):continue
    count+=1
    for file in manifest['files']:
        target=OUT/manifest['operation']/file['name']
        target.parent.mkdir(parents=True,exist_ok=True)
        raw=(STORE/file['key']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==file['sha256']
        target.write_bytes(raw)
assert count==12
print(OUT)
