"""Qualification only: pause an uploaded assembly/final result before registration."""
import json
import os
from pathlib import Path
import sys
import threading

sys.path.insert(0, '/app')
from pdf_processing.object_store import Store

publish = Store.publish


def paused_publish(self, operation, files, after_upload=None, after_register=None):
    name = 'document.json' if os.environ['T10_FAULT'] == 'assembly' else 'processing-result.json'
    target = name in files and (os.environ['T10_FAULT'] != 'assembly' or
        json.loads(files.get('attribution.json', b'{}')).get('operation', {}).get('kind') == 'assembly')
    def uploaded(manifest):
        if after_upload:
            after_upload(manifest)
        if target:
            Path(os.environ.get('SCRATCH','/scratch'),'fault.json').write_text(json.dumps({'operation': operation,
                'stage': os.environ['T10_FAULT'], 'registered': False}))
            # The host must observe the marker and replace this owned Pod.
            if not threading.Event().wait(90):
                raise TimeoutError('T10 host did not inject the bounded Pod loss')
    return publish(self, operation, files, after_upload=uploaded, after_register=after_register)


if __name__ == '__main__':
    Store.publish = paused_publish
    import worker
    import asyncio
    asyncio.run(worker.entrypoint())
