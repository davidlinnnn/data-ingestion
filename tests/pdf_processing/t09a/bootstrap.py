"""Copy verified private fixtures to the isolated coordinator; run upload once."""
import json
from pathlib import Path
import subprocess

NS='pdf-t09a-validation'
def k(*args):subprocess.run(['kubectl','--request-timeout=15s','-n',NS,*args],check=True)

if __name__=='__main__':
    k('wait','--for=condition=Ready','pod/coordinator','--timeout=60s')
    k('exec','coordinator','--','mkdir','-p','/tmp/t09a-fixtures','/tmp/t09a-originals','/tmp/t09a-test','/tmp/t09a-results','/tmp/t09a-oracles')
    manifest=Path('/private/tmp/t09a-fixtures/manifest.json')
    for entry in json.loads(manifest.read_text()):
        k('cp',entry['pdf'],'coordinator:/tmp/t09a-fixtures/'+entry['id']+'.pdf')
        k('cp',entry['original'],'coordinator:/tmp/t09a-originals/'+entry['id']+'.pdf')
    k('cp',str(manifest),'coordinator:/tmp/t09a-fixtures/manifest.json')
    k('cp','tests/pdf_processing/t09a/upload.py','coordinator:/tmp/t09a-test/upload.py')
    k('exec','coordinator','--','/experiment/.venv/bin/python','/tmp/t09a-test/upload.py')
    k('cp','coordinator:/tmp/t09a-profile.json','/private/tmp/t09a-profile.json')
