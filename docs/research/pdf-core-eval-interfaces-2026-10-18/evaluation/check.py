"""Read-only evaluation registration verification; no network, GT read or evaluator execution."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def verify_files(base, entries):
    for entry in entries:
        path = (base / entry['path']).resolve()
        if not path.is_relative_to(base.resolve()):
            raise ValueError('hash path leaves registration')
        data = path.read_bytes()
        if len(data) != entry['size_bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('frozen bytes changed: ' + entry['path'])


def main():
    seal = json.loads((HERE / 'artifacts.json').read_text())
    verify_files(HERE, seal['files'])
    lock = json.loads((HERE / 'upstream.lock.json').read_text())
    verify_files(HERE, lock['files'])
    result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(HERE), '-p', 'test_sampling.py', '-v'], capture_output=True, text=True, check=True)
    print(result.stdout + result.stderr, end='')
    match = re.search(r'Ran (\d+) tests?', result.stderr)
    if not match or int(match.group(1)) == 0:
        raise ValueError('no sampling checks ran')
    print(json.dumps({'status': 'metadata_lock_and_sampling_checks_passed', 'frozen_files': len(seal['files']), 'tests': int(match.group(1)), 'sampled_pages': 60, 'new_model_calls': 0, 'page_assets_acquired': False, 'official_evaluator_executed': False, 'live_ready': False}))


if __name__ == '__main__':
    main()
