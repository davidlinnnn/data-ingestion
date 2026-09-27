"""CY-only first-component measurement and deliberate fail-stop; no model changes."""
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time

CY_DIAGNOSTIC_HOOK = True
ROOT = Path('/q04-evidence/t09a-bounds-20260928-cy/state/bounds-pod-cgroup-cy/ocr-diagnostic')


def mark(stage):
    ROOT.mkdir(parents=True, exist_ok=True)
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines())
    threads = sorted(int(path.name) for path in Path('/proc/self/task').iterdir())
    row = {'stage': stage, 'time': time.time(), 'pid': os.getpid(),
           'ppid': os.getppid(), 'threads': threads,
           'start_ticks': int(Path('/proc/self/stat').read_text().rsplit(') ', 1)[1].split()[19]),
           'rss_kb': int(status['VmRSS'].split()[0]),
           'minor_faults': resource.getrusage(resource.RUSAGE_SELF).ru_minflt}
    with (ROOT/'phases.jsonl').open('a') as stream:
        stream.write(json.dumps(row)+'\n'); stream.flush()


def lines(frame, event, arg):
    if event == 'return':
        out = Path(frame.f_locals.get('out', '/nonexistent'))
        if (out/'ocr.json').is_file():
            for name in ('ocr.json', 'figure.png'):
                shutil.copyfile(out/name, ROOT/name)
            mark('result_written')
            (ROOT/'planned-stop.json').write_text(json.dumps({'reason':'first_component_complete', 'time':time.time(), 'business_success':False}))
            raise RuntimeError('CY_DIAGNOSTIC_FIRST_COMPONENT_COMPLETE')
    return lines


def trace(frame, event, arg):
    if event == 'call' and frame.f_code.co_name == 'execute' and frame.f_code.co_filename.endswith('/pdf_processing/ocr.py'):
        ROOT.mkdir(parents=True, exist_ok=True)
        # Exclusive ownership prevents a second attempt from reaching inference.
        with (ROOT/'first-component.json').open('x') as stream:
            json.dump(frame.f_locals['request'], stream)
        mark('ocr_enter')
        return lines
    return None


def profile(frame, event, arg):
    instance = frame.f_locals.get('self')
    if event not in ('call', 'return') or instance is None:
        return
    if type(instance).__name__ == 'RapidOCR' and type(instance).__module__.startswith('rapidocr'):
        if frame.f_code.co_name == '__init__':
            mark('engine_start' if event == 'call' else 'engine_ready')
        elif frame.f_code.co_name == '__call__':
            mark('inference_start' if event == 'call' else 'inference_ready')


if 'PDF_PROCESS_LIFECYCLE_FD' in os.environ and 'pdf_processing.ocr' in sys.argv:
    sys.settrace(trace)
    sys.setprofile(profile)
