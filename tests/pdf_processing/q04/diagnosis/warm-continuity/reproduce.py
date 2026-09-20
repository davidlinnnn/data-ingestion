"""No-inference reproduction of the original cross-document warm requirement."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile

from pdf_processing.execution import Execution
from pdf_processing.supervision import WarmParser


CHILD = '''import json,sys
for line in sys.stdin:
    envelope=json.loads(line)
    for kind in ('ready','done'):
        print(json.dumps({'protocol':'pdf-warm-v1','request_id':envelope['request_id'],
                          'kind':kind,'method':{},'memory':{}}),flush=True)
'''


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        script = root/'child.py'
        script.write_text(CHILD)
        parser = WarmParser(command=[sys.executable, str(script)], max_requests=20)
        execution = Execution(None, None, root, child_runner=parser)
        fresh_calls = []
        async def no_inference(module, request, out):
            fresh_calls.append(request['mode'])
        execution.fresh_child = no_inference
        try:
            await execution.child('pdf_processing.parse', {'mode':'capture','expected_method':{}}, root)
            first = parser.process.pid
            await execution.child('pdf_processing.parse', {'mode':'restore','expected_method':{}}, root)
            await execution.child('pdf_processing.parse', {'mode':'capture','expected_method':{}}, root)
            second = parser.process.pid
            result = {'first_capture_pid':first,'next_document_capture_pid':second,
                      'same_warm_pid':first == second,'capture_requests_before_recycle':2,
                      'observed_parser_count':parser.count,'fresh_calls':fresh_calls,
                      'inference':False,'external_runtime':False}
            print(json.dumps(result, indent=2))
            assert first == second, 'assembly ended warm lifetime before original request20 recycle'
            assert parser.count == 2, 'only capture groups count toward original request20 recycle'
        finally:
            await parser.close()


if __name__ == '__main__':
    asyncio.run(main())
