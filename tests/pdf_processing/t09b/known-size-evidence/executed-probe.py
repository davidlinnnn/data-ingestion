import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

root = Path('/private/tmp/t09b-calibration/tests/pdf_processing/t09b')
sys.path.insert(0, str(root))
from minio_trace import accounting

out = root/'known-size-evidence'
out.mkdir(exist_ok=False)
prefix = 't09b/byte-calibration-' + uuid.uuid4().hex
base = ['kubectl', '--context', 'kind-internal-a2a-vs6-local', '-n',
        'pdf-t09a-validation', 'exec', 'objects-6bb8bb5d95-2dfl8', '--', 'sh', '-c']
auth = 'export MC_HOST_probe="http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@127.0.0.1:9000"; '
trace = subprocess.Popen(base + [auth + 'timeout 20 mc admin trace --json --verbose probe'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
results = []
try:
    time.sleep(3)
    for name, value in (('small', 'a'*16), ('large', 'b'*4096)):
        key = f'probe/t09a/{prefix}/{name}'
        put = subprocess.run(base + [auth + f"printf '%s' '{value}' | mc pipe '{key}'"],
                             capture_output=True, timeout=8)
        if put.returncode:
            raise RuntimeError('PUT failed; no automatic retry')
        get = subprocess.run(base + [auth + f"mc cat '{key}'"], capture_output=True, timeout=8)
        results.append({'key': key, 'expected_payload_bytes': len(value),
                        'put_exit': put.returncode, 'get_exit': get.returncode,
                        'exact_readback': get.stdout == value.encode()})
        if get.returncode or get.stdout != value.encode():
            raise RuntimeError('readback failed; no automatic retry')
    stdout, stderr = trace.communicate(timeout=24)
    rows = []
    for line in stdout.splitlines():
        raw = json.loads(line)
        if not isinstance(raw.get('request'), dict):
            continue
        row = accounting(raw, 't09a', prefix)
        if row is not None:
            rows.append(row)
    report = {'prefix': prefix, 'objects_retained': True, 'operations': results,
              'trace_exit': trace.returncode, 'records': rows,
              'scope': 'server HTTP counters; no PDF runtime; raw headers discarded'}
    (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
finally:
    if trace.poll() is None:
        trace.terminate()
        trace.communicate(timeout=24)
