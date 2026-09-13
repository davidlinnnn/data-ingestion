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
        time.sleep(8)
    return original(self,operation,files)

Store.publish=publish
runpy.run_path('/driver/worker.py',run_name='__main__')
