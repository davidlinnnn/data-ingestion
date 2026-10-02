"""Restore exact Q02 bytes from a privately retrieved, sealed Q03 document."""
import argparse
import hashlib
import json
from pathlib import Path

STORED_SHA256 = 'f0f576f3bcc6df04306597ef80368112d1269f9459fc552fb8402c245a0aabca'
BASELINE_SHA256 = '7cbc44478d4a3d2f60256f6f92828b2396b1b932579436546e3d32b6f601f564'


def recover(raw):
    from docling_core.types.doc import DoclingDocument
    if hashlib.sha256(raw).hexdigest() != STORED_SHA256:
        raise ValueError('historical Q03 document digest mismatch')
    doc = DoclingDocument.model_validate_json(raw)
    baseline = json.dumps(doc.model_dump(mode='json'), indent=2).encode()
    if hashlib.sha256(baseline).hexdigest() != BASELINE_SHA256:
        raise ValueError('historical Q02 baseline digest mismatch')
    return baseline


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stored_document', type=Path)
    parser.add_argument('baseline', type=Path)
    args = parser.parse_args()
    baseline = recover(args.stored_document.read_bytes())
    with args.baseline.open('xb') as output:
        output.write(baseline)
    print(BASELINE_SHA256)
