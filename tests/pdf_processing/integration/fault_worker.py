"""Test-only fault injection around the integrated production OCR seams."""
import asyncio
import json
import os
from pathlib import Path
import runpy
import signal
import time
import pdf_processing.execution as execution
from pdf_processing.object_store import Store

pids = []
original_child = execution.Execution.child
async def child(self, module, request, out):
    if os.environ['INTEGRATION_FAULT'] != 'active' or module != 'pdf_processing.ocr':
        return await original_child(self, module, request, out)
    task = asyncio.create_task(original_child(self, module, request, out))
    while not execution._fresh_children and not task.done():
        await asyncio.sleep(.01)
    process = next(iter(execution._fresh_children))
    pids.append(process.pid)
    os.killpg(process.pid, signal.SIGSTOP)
    print('INTEGRATION_OCR_PAUSED', flush=True)
    try:
        return await task
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
execution.Execution.child = child
original_publish = Store.publish

def publish(self, operation, files, *args, **kwargs):
    if os.environ['INTEGRATION_FAULT'] == 'publication' and 'ocr.json' in files:
        print('INTEGRATION_OCR_PAUSED', flush=True)
        time.sleep(90)
    return original_publish(self, operation, files, *args, **kwargs)
Store.publish = publish
original_exit = os._exit

def observed_exit(code):
    def alive(pid):
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
    print(json.dumps({'event':'integration_cleanup','exit_code':code,
        'pids':pids,'alive':[pid for pid in pids if alive(pid)],
        'tracked_children':len(execution._fresh_children),
        'scratch':[p.name for p in Path('/scratch').iterdir()]}),flush=True)
    original_exit(code)
os._exit = observed_exit
runpy.run_path('/driver/worker.py', run_name='__main__')
