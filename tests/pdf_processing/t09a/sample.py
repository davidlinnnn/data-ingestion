"""One-second Linux single-container Pod and child measurements, metadata only."""
import json
import os
from pathlib import Path
import time
import psutil

out = Path('/tmp/t09a-samples.jsonl')
cgroup = Path('/sys/fs/cgroup')
def read(name):
    try: return (cgroup/name).read_text().strip()
    except OSError: return None

def scratch():
    size = allocated = 0
    for root, _, files in os.walk('/scratch'):
        for name in files:
            try:
                st = os.stat(Path(root)/name); size += st.st_size; allocated += st.st_blocks*512
            except FileNotFoundError: pass
    return {'bytes':size,'allocated_bytes':allocated,'free_bytes':psutil.disk_usage('/scratch').free}

with out.open('a',buffering=1) as f:
    while not Path('/tmp/t09a-stop-sampling').exists():
        processes = []
        for proc in psutil.process_iter():
            try:
                info = proc.as_dict(attrs=['pid','ppid','cmdline','memory_info','create_time']); cmd = info['cmdline'] or []
                module = next((m for m in ('pdf_processing.warm_child','pdf_processing.parse','pdf_processing.ocr','pdf_processing.preflight','worker.py') if any(m in v for v in cmd)), None)
                if module: processes.append({'pid':info['pid'],'ppid':info['ppid'],'module':module,'created':info['create_time'],'rss':info['memory_info'].rss,'cpu_seconds':sum(proc.cpu_times()[:2])})
            except (psutil.NoSuchProcess,psutil.AccessDenied): pass
        row = json.dumps({'time':time.time(),'memory_current':read('memory.current'),'memory_peak':read('memory.peak'),
            'memory_max':read('memory.max'),'memory_events':read('memory.events'),'memory_stat':read('memory.stat'),
            'cpu_stat':read('cpu.stat'),'cpu_max':read('cpu.max'),'pressure':read('memory.pressure'),
            'processes':processes,'scratch':scratch(),'sampler_pid':os.getpid()})
        f.write(row+'\n')
        print(row,flush=True)
        time.sleep(1)
