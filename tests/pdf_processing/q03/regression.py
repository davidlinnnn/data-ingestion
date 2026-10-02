"""#68 local regression scopes; each module gets a fresh pinned interpreter."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT/'tests/pdf_processing'
AFFECTED = ('q02/test_delivery.py', 'q02/test_oracle.py', 'q02/test_publication.py',
            'q03/test_q03_compatibility.py', 'q03/test_q03_interruption.py',
            'q03/test_q03_publication.py', 'q03/test_q03_runtime.py', 'q03/test_representation.py')
PACKAGES = {'docling': '2.102.0', 'docling-core': '2.96.0', 'psutil': '7.2.2',
            'temporalio': '1.23.0', 'pypdfium2': '5.13.0', 'Pillow': '12.3.0',
            'reportlab': '5.0.1', 'boto3': '1.40.24'}
FIXTURES = {'baseline-document.json': '7cbc44478d4a3d2f60256f6f92828b2396b1b932579436546e3d32b6f601f564',
            'source.pdf': 'b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980',
            'source-oracle.json': 'ae3176eb987341243a90dc0fb4a476be3286f2f63c56196c8706f8067788ae7c'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path, help='new private directory for logs and summary')
    parser.add_argument('--scope', choices=('affected', 'current'), default='affected')
    args = parser.parse_args()
    versions = {name: importlib.metadata.version(name) for name in PACKAGES}
    if platform.python_version() != '3.12.13' or versions != PACKAGES:
        parser.error('use the qualified Python 3.12.13 environment described in REGRESSION.md')
    fixtures = args.fixtures.resolve()
    for name, expected in FIXTURES.items():
        if hashlib.sha256((fixtures/name).read_bytes()).hexdigest() != expected:
            parser.error(f'private fixture digest mismatch: {name}')
    if not __debug__:
        parser.error('historical integrity assertions require an interpreter without -O')
    if args.scope == 'current':
        manifest = Path('/private/tmp/q44-inputs-warm-20260928-db/inputs.json')
        if not manifest.is_file():
            parser.error('current scope requires the retained Q44 inputs.json mount; see REGRESSION.md')
    args.out.mkdir(parents=True, exist_ok=False)
    paths = [TESTS/name for name in AFFECTED]
    if args.scope == 'current':
        paths += [TESTS/'q03/test_fixture_recovery.py', TESTS/'q02/test_compatibility.py', TESTS/'q01/test_identity.py']
        for directory in ('t04', 't05', 't09b', 't10'):
            paths += sorted((TESTS/directory).glob('test_*.py'))
    rows = []
    for path in paths:
        env = {**os.environ, 'PYTHONPATH': os.pathsep.join(map(str, [path.parent, ROOT/'src',
            TESTS/'q02', TESTS/'q03', TESTS/'q04', TESTS/'t09b', TESTS/'q01_q02'])),
            'PYTHONDONTWRITEBYTECODE': '1', 'HF_HUB_OFFLINE': '1', 'OMP_NUM_THREADS': '4',
            'Q02_BASELINE': str(fixtures/'baseline-document.json'),
            'Q02_SOURCE_PDF': str(fixtures/'source.pdf'),
            'Q02_SOURCE_ORACLE': str(fixtures/'source-oracle.json')}
        try:
            result = subprocess.run([sys.executable, '-B', '-m', 'unittest', path.stem, '-v'],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
            log = result.stdout + result.stderr
            code = result.returncode
        except subprocess.TimeoutExpired:
            log, code = 'module exceeded 180 seconds', 124
        count = re.search(r'Ran (\d+) tests?', log)
        tests = int(count[1]) if count else 0
        passed = code == 0 and tests > 0 and not re.search(r'skipped=|expected failures=', log)
        name = str(path.relative_to(TESTS))
        log_name = name.replace('/', '__') + '.log'
        (args.out/log_name).write_text(log)
        rows.append({'module': name, 'tests': tests, 'returncode': code, 'passed': passed, 'log': log_name})
        print(name, 'PASS' if passed else 'FAIL', tests, flush=True)
    summary = {'scope': args.scope, 'python': platform.python_version(), 'packages': versions,
               'fixtures': FIXTURES, 'modules': rows, 'tests': sum(row['tests'] for row in rows),
               'passed': all(row['passed'] for row in rows)}
    (args.out/'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
