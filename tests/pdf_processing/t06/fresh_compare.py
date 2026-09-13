"""Independent uninterrupted parsing versus reconstructed real delivery, no scoring normalization."""
import asyncio,json,subprocess,sys
from pathlib import Path

async def main():
    profile=json.loads(Path('/driver/native-v1.json').read_text())
    root=Path('/tmp/t06-results');results={}
    for sid in ('06','07','08','09','10'):
        out=Path('/tmp/t06-fresh')/sid
        request={'mode':'baseline','pdf':'/tmp/t06-fixtures/'+sid+'.pdf','out':str(out),
            'model_cache':'/experiment/PROTOTYPE-wipe-me/hf','expected_method':profile['method']}
        if '--existing-baselines' not in sys.argv:
          with (root/(sid+'-baseline.log')).open('wb') as log:
            subprocess.run(['/experiment/.venv/bin/python','-m','pdf_processing.parse'],input=json.dumps(request).encode(),stdout=log,stderr=log,check=True,timeout=540)
        expected=json.loads((out/'document.json').read_text())
        actual=json.loads((root/(sid+'-document.json')).read_text())
        assert expected==actual,sid
        results[sid]={'full_document_json_equal':True,'comparison':'no normalization'}
        (root/'fresh-comparison.json').write_text(json.dumps(results,indent=2))
        print(sid,'full reconstructed JSON equals uninterrupted output',flush=True)
asyncio.run(main())
