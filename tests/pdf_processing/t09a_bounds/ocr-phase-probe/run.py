"""One bounded plain/observed OCR comparison; run only inside the diagnostic container."""
import asyncio
import json
import os
from pathlib import Path
import time

ROOT = Path('/probe')
os.environ.update(json.loads((ROOT / 'child-env.json').read_text()))
os.environ['PDF_PROCESS_LIFECYCLE_LOCK'] = str(ROOT / 'lifecycle.lock')
from pdf_processing.execution import Execution


def sample():
    def fields(path):
        return {line.split()[0].rstrip(':'): int(line.split()[1])
                for line in Path(path).read_text().splitlines()}
    def pressure(path):
        line = next(x for x in Path(path).read_text().splitlines() if x.startswith('full '))
        return dict(x.split('=') for x in line.split()[1:])
    return {'time': time.time(), 'available': fields('/proc/meminfo')['MemAvailable'] * 1024,
            'oom': fields('/proc/vmstat')['oom_kill'],
            'memory': int(Path('/sys/fs/cgroup/memory.current').read_text()),
            'events': fields('/sys/fs/cgroup/memory.events'),
            'vm_psi': pressure('/proc/pressure/memory'),
            'cgroup_psi': pressure('/sys/fs/cgroup/memory.pressure')}


async def main():
    baseline = sample()
    assert baseline['available'] >= 4_831_838_208, 'admission memory floor'
    async def guard():
        with (ROOT / 'samples.jsonl').open('x') as out:
            while True:
                row = sample()
                out.write(json.dumps(row) + '\n'); out.flush()
                if row['available'] < 1_610_612_736 or row['memory'] > 4_294_967_296:
                    raise RuntimeError('memory guard')
                if row['oom'] != baseline['oom'] or any(row['events'][k] for k in ('max','oom','oom_kill')):
                    raise RuntimeError('OOM/max guard')
                if any(float(row[k]['avg10']) != 0 or int(row[k]['total']) > int(baseline[k]['total'])
                       for k in ('vm_psi', 'cgroup_psi')):
                    raise RuntimeError('PSI guard')
                await asyncio.sleep(.1)
    async def workload():
        for variant in ('observed', 'plain'):
            out = ROOT / variant; out.mkdir()
            if variant == 'observed':
                os.environ['Q04_OCR_TRACE_DIR'] = str(ROOT / 'trace')
            else:
                os.environ.pop('Q04_OCR_TRACE_DIR', None)
            execution = Execution(None, None, out, child_timeout=60)
            await execution.child('pdf_processing.ocr', {
                'parsed':'/input/document.json', 'pdf':'/input/06.pdf',
                'component':'#/pictures/0', 'scale':3, 'allow_cropbox':True,
                'max_render_pixels':20_000_000, 'out':str(out)}, out)
        a,b=[json.loads((ROOT / name / 'ocr.json').read_text()) for name in ('plain','observed')]
        for value in (a,b):value.pop('seconds_including_engine_load')
        assert a == b, 'OCR output drift'
        assert (ROOT/'plain/figure.png').read_bytes() == (ROOT/'observed/figure.png').read_bytes()
        rows=[json.loads(line) for path in (ROOT/'trace').glob('*.jsonl') for line in path.read_text().splitlines()]
        assert [r['stage'] for r in rows] == ['ocr_enter','imports_ready','document_ready','crop_ready','engine_start','engine_ready','inference_start','inference_ready','result_written']
        (ROOT/'result.json').write_text(json.dumps({'status':'PASS_DIAGNOSTIC_ONLY','output_equal':True,'stages':rows},indent=2))
    tasks=[asyncio.create_task(workload()),asyncio.create_task(guard())]
    try:
        done,_=await asyncio.wait(tasks,timeout=120,return_when=asyncio.FIRST_COMPLETED)
        if not done:raise TimeoutError('diagnostic deadline')
        for task in done:task.result()
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)


if __name__ == '__main__':
    asyncio.run(main())
