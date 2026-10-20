"""Fetch only the two versioned RapidAI recognition candidates; verify pinned hashes."""
import hashlib
import json
from pathlib import Path
import time
import urllib.request

HERE = Path(__file__).resolve().parent
CACHE = Path('/private/tmp/pdf-core-g2r3-ocr-models-20261014')
CANDIDATES = {
 'mobile': '5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5',
 'server': 'e09385400eaaaef34ceff54aeb7c4f0f1fe014c27fa8b9905d4709b65746562a',
}
CACHE.mkdir(exist_ok=True)
rows = []
for variant, expected in CANDIDATES.items():
 name = f'ch_PP-OCRv5_rec_{variant}.onnx'
 url = 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv5/rec/' + name
 started = time.monotonic()
 request = urllib.request.Request(url, method='HEAD')
 with urllib.request.urlopen(request, timeout=30) as response:
  headers = dict(response.headers)
  size = response.headers.get('Content-Length')
 if size is not None:
  assert int(size) < 150_000_000, size
 path = CACHE / name
 if not path.exists():
  temporary = path.with_suffix('.part')
  with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as out:
   while chunk := response.read(1024*1024):
    out.write(chunk)
    assert out.tell() < 150_000_000, 'Candidate size exceeded bounded download'
  assert hashlib.sha256(temporary.read_bytes()).hexdigest() == expected
  temporary.rename(path)
 assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
 row = {'variant':variant, 'filename':name,'versioned_registry':'RapidAI/RapidOCR v3.9.2', 'url':url,'path':str(path),'bytes':path.stat().st_size,'expected_sha256':expected,'actual_sha256':expected,'head_headers':headers,'download_check_seconds':time.monotonic()-started,'inference_executed':False}
 rows.append(row)
 (HERE/'download.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in row.items() if k!='head_headers'}),flush=True)
