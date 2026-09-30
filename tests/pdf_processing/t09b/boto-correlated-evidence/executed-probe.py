import base64
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

import boto3
from botocore.config import Config

root = Path('/private/tmp/t09b-calibration/tests/pdf_processing/t09b')
sys.path.insert(0, str(root))
from minio_trace import accounting
from storage_ledger import Ledger, reconcile
from reconcile_traffic import reconcile as reconcile_traffic
from storage_measurement import MeasuredClient, scope

out = root/'boto-correlated-evidence'
out.mkdir(exist_ok=False)
prefix = 't09b/boto-calibration-' + uuid.uuid4().hex
kube = ['kubectl', '--context', 'kind-internal-a2a-vs6-local', '-n', 'pdf-t09a-validation']
pod = 'objects-6bb8bb5d95-2dfl8'
auth = 'export MC_HOST_probe="http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@127.0.0.1:9000"; '
trace = subprocess.Popen(kube + ['exec', pod, '--', 'sh', '-c',
                         auth+'timeout 20 mc admin trace --json --verbose probe'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
forward = subprocess.Popen(kube+['port-forward', 'pod/'+pod, f'{port}:9000', '--address=127.0.0.1'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ledger = Ledger(out/'storage.jsonl')
raw = None
try:
    deadline = time.monotonic()+10
    while True:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.2):
                break
        except OSError:
            if forward.poll() is not None or time.monotonic()>deadline:
                raise RuntimeError('port-forward unavailable')
            time.sleep(.1)
    secret = json.loads(subprocess.check_output(kube+['get', 'secret', 'store-access', '-o', 'json'], timeout=10))['data']
    raw = boto3.client('s3', endpoint_url=f'http://127.0.0.1:{port}', region_name='us-east-1',
                       aws_access_key_id=base64.b64decode(secret['AWS_ACCESS_KEY_ID']).decode(),
                       aws_secret_access_key=base64.b64decode(secret['AWS_SECRET_ACCESS_KEY']).decode(),
                       config=Config(connect_timeout=5, read_timeout=5, retries={'total_max_attempts': 1}))
    del secret
    client = MeasuredClient(raw, ledger)
    time.sleep(2)
    operations = []
    with scope('boto-calibration', 'put-get', 1):
        for size in (16, 4096):
            key = f'{prefix}/{size}'
            payload = b'x'*size
            client.put_object(Bucket='t09a', Key=key, Body=payload, IfNoneMatch='*')
            body = client.get_object(Bucket='t09a', Key=key)['Body']
            try:
                observed = body.read()
            finally:
                body.close()
            if observed != payload:
                raise RuntimeError('readback differs')
            operations.append({'key': key, 'bytes': size, 'exact_readback': True})
    ledger.close()
    stdout, stderr = trace.communicate(timeout=24)
    rows = []
    for line in stdout.splitlines():
        event = json.loads(line)
        if isinstance(event.get('request'), dict):
            row = accounting(event, 't09a', prefix)
            if row is not None:
                rows.append(row)
    report = {'prefix': prefix, 'operations': operations, 'records': rows,
              'trace_exit': trace.returncode, 'ledger': reconcile(out/'storage.jsonl'),
              'objects_retained': True,
              'traffic': reconcile_traffic(reconcile(out/'storage.jsonl')['events'], rows, 't09a')}
    (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
finally:
    ledger.close()
    if raw is not None:
        raw.close()
    for process in (forward, trace):
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=24)
    (out/'cleanup.json').write_text(json.dumps({'port_forward_exit': forward.returncode,
                                               'trace_exit': trace.returncode})+'\n')
