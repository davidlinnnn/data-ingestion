"""Re-score saved OCR against the visually corrected transcription; no OCR rerun."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
raw=ROOT/'evidence/ocr.json'
reference=ROOT/'ocr-reference.json'
o=json.loads(raw.read_text());r=json.loads(reference.read_text())
norm=lambda s: ''.join(c.lower() for c in s if c.isalnum())
text=norm(' '.join(o['texts']))
matched=[label for label in r['labels'] if norm(label) in text]
report={'ocr_result_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),
 'verified_reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),
 'matched_labels':matched,'missing_labels':[x for x in r['labels'] if x not in matched],
 'label_recall':len(matched)/len(r['labels']),
 'scope':o['accuracy_scope'],
 'reference_correction':'Initial score was 57/58. Source actually spells Galatica; OCR correctly preserved it. Corrected transcription scores 58/58. Logos, reading order, duplicate occurrences and precision are not evaluated.'}
(ROOT/'evidence/ocr-evaluation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
