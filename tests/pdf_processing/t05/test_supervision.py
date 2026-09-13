"""Small process-protocol cases impractical to isolate with native inference."""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest

from pdf_processing.supervision import WarmParser

class SupervisionTests(unittest.IsolatedAsyncioTestCase):
    async def test_hung_sigterm_resistant_child_is_reaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp)/'child.py'
            script.write_text('import signal,time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nwhile True: time.sleep(.1)\n')
            parser = WarmParser(command=[sys.executable, str(script)], no_progress_seconds=.3,
                                startup_seconds=.3, terminate_seconds=.1, reap_seconds=2)
            with self.assertRaisesRegex(Exception, 'child_startup_deadline'):
                await parser.run({'mode':'capture','expected_method':{},'scan':False}, Path(tmp), lambda d: None, 3)
            self.assertIsNone(parser.process)
            self.assertEqual(parser.observation['termination_reason'], 'child_startup_deadline')
            self.assertTrue(parser.observation['forced_kill'])

if __name__ == '__main__': unittest.main()

class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_correlated_requests_reuse_process_and_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp)/'child.py'
            script.write_text('''import sys,json
for line in sys.stdin:
 e=json.loads(line)
 for kind in ('ready','done'):
  print(json.dumps({'protocol':'pdf-warm-v1','request_id':e['request_id'],'kind':kind,'method':{},'memory':{'peak_rss':100}}),flush=True)
''')
            parser = WarmParser(command=[sys.executable,str(script)])
            req={'expected_method':{}}
            first=await parser.run(req,Path(tmp),lambda d:None,3)
            second=await parser.run(req,Path(tmp),lambda d:None,3)
            self.assertEqual(first['pid'],second['pid'])
            self.assertNotEqual(first['request_id'],second['request_id'])
            with self.assertRaisesRegex(Exception,'worker_method_mismatch'):
                await parser.run({'expected_method':{'changed':True}},Path(tmp),lambda d:None,3)
            self.assertIsNone(parser.process)
            await parser.close()

    async def test_hard_deadline_bounds_child_that_keeps_reporting_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            script=Path(tmp)/'child.py'
            script.write_text('''import sys,json,time
r=json.loads(sys.stdin.readline())
def emit(kind): print(json.dumps({'protocol':'pdf-warm-v1','request_id':r['request_id'],'kind':kind,'method':{}}),flush=True)
emit('ready')
while True:
 emit('progress');time.sleep(.03)
''')
            parser=WarmParser(command=[sys.executable,str(script)], no_progress_seconds=1)
            with self.assertRaisesRegex(Exception,'child_hard_deadline'):
                await parser.run({'expected_method':{}},Path(tmp),lambda d:None,.3)
            self.assertIsNone(parser.process)

    async def test_activity_cancellation_reaps_child_before_scratch_can_be_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            script=Path(tmp)/'child.py'
            script.write_text('''import sys,json,time,signal
signal.signal(signal.SIGTERM,signal.SIG_IGN)
r=json.loads(sys.stdin.readline())
print(json.dumps({'protocol':'pdf-warm-v1','request_id':r['request_id'],'kind':'ready','method':{}}),flush=True)
while True: time.sleep(.1)
''')
            parser=WarmParser(command=[sys.executable,str(script)],terminate_seconds=.1)
            ready=asyncio.Event()
            task=asyncio.create_task(parser.run({'expected_method':{}},Path(tmp),lambda d: ready.set() if d['parser']['ready'] else None,3))
            await asyncio.wait_for(ready.wait(),2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
            self.assertIsNone(parser.process)
            self.assertTrue(parser.observation['forced_kill'])
