"""Freeze an opt-in release from a verified runtime profile; never edit old profiles."""
import hashlib
import json
from pathlib import Path
import sys

from pdf_processing.continuation import METHOD

ROOT = Path(__file__).resolve().parents[3]


def freeze(profile):
    profile = json.loads(json.dumps(profile))
    producer = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT/'src/pdf_processing').glob('*.py'))}
    profile['version'] = 2
    profile['release'] = 'q01-' + hashlib.sha256(
        json.dumps(producer, sort_keys=True).encode()).hexdigest()
    profile['method']['continuation'] = {'version': METHOD, 'sha256': producer['continuation.py']}
    return profile


if __name__ == '__main__':
    profile = freeze(json.loads(Path(sys.argv[1]).read_text()))
    with Path(sys.argv[2]).open('x') as output:
        output.write(json.dumps(profile, indent=2)+'\n')
