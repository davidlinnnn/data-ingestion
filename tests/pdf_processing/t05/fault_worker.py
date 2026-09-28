"""Test-only publication pause: exercise SDK drain around real S3 registration."""
import os
import runpy
import time
from pdf_processing.object_store import Store
original=Store.publish
armed=True

def publish(self, operation, files):
    global armed
    if armed and 'complete.json' in files:
        armed=False
        print('T05_PUBLICATION_PAUSED',flush=True)
        time.sleep(int(os.environ.get('T05_PUBLICATION_PAUSE_SECONDS', '8')))
    return original(self,operation,files)

from pdf_processing.supervision import WarmParser
close=WarmParser.close
async def observed_close(self):
    await close(self)
    from pathlib import Path
    import json
    print(json.dumps({'event':'T05_CLEANUP_OBSERVED','parser_reaped':self.process is None,
                      'scratch_remaining':[p.name for p in Path('/scratch').iterdir()]}),flush=True)
WarmParser.close=observed_close
Store.publish=publish
runpy.run_path('/driver/worker.py',run_name='__main__')
