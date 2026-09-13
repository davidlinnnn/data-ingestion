"""Check full document bytes against the fixed 85925fa Linux evidence baseline."""
import hashlib
import json
from pathlib import Path
import sys


def verify(output):
    reference = json.loads((Path(__file__).parent/'evidence/historical-comparison.json').read_text())
    for label in ('native', 'scan'):
        actual = hashlib.sha256((output/f'{label}-baseline/document.json').read_bytes()).hexdigest()
        expected = reference[label]['historical_sha256']
        if actual != expected:
            raise AssertionError(f'{label}: historical document differs ({actual} != {expected})')
    print('Native and scanned document bytes match fixed historical Linux evidence.')

if __name__ == '__main__': verify(Path(sys.argv[1]))
