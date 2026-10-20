"""Read-only public provenance checks; never calls inference endpoints or handles credentials."""
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import urllib.error

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CACHE = Path('/private/tmp/pdf-core-g2-api-public-source-checks-20261014')
CACHE.mkdir(exist_ok=True)
SOURCES = (
 ('nccu', 'https://posman.nccu.edu.tw/files/archive/424_1f69c9f2.pdf',
  'docs/fixtures/pdf-s2-candidates-2026-09-13/03-nccu-personal-statement-manual.pdf',
  '3a8d8a946a5962cc1b666ec6a33dc5482556da7013a70ca096fc8d86439a5f6e'),
 ('llm-survey', 'https://arxiv.org/pdf/2303.18223v1',
  'docs/prototypes/pdf-checkpoint-prototype/fixtures/llm-survey-2303.18223v1.pdf',
  'd58be5fc39608dc9aec45194c602436d793f2f2bf56f267d0e38d6258a9f7a9e'),
)
rows = []
for name, url, source, expected in SOURCES:
 started = time.monotonic()
 request = urllib.request.Request(url, method='GET')
 assert not request.has_header('Authorization')
 try:
  response = urllib.request.urlopen(request, timeout=60)
 except urllib.error.HTTPError as error:
  row={'source_name':name,'official_url':url,'http_status':error.code,'exact_public_pdf_bytes_match_local_source':False,'verification_status':'public_GET_blocked','authorization_header_sent':False,'inference_request_sent':False}
  rows.append(row)
  (HERE/'public-ocr-order.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps(row,ensure_ascii=False),flush=True)
  continue
 with response:
  body = response.read(32*1024*1024+1)
  assert len(body) <= 32*1024*1024 and body.startswith(b'%PDF-')
  row = {'source_name':name, 'official_url':url, 'resolved_url':response.geturl(),
         'http_status':response.status, 'content_type':response.headers.get('Content-Type'),
         'bytes':len(body), 'fetched_sha256':hashlib.sha256(body).hexdigest(),
         'local_source_path':source,'local_sha256':hashlib.sha256((REPO/source).read_bytes()).hexdigest(),
         'expected_frozen_sha256':expected,'retrieval_seconds':time.monotonic()-started,
         'authorization_header_sent':False,'inference_request_sent':False}
 assert row['fetched_sha256']==row['local_sha256']==expected
 target=CACHE/f'{name}.pdf';target.write_bytes(body);row['temporary_fetched_pdf']=str(target)
 row['exact_public_pdf_bytes_match_local_source']=True
 rows.append(row)
 (HERE/'public-ocr-order.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(row,ensure_ascii=False),flush=True)
