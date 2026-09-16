"""Bounded Q03 declarations, independent of runtime derivation."""
import json
from pathlib import Path
from fixtures import SOURCE
from test_publication import profile as q02_profile

ROOT = Path(__file__).resolve().parent

def profile():
    result = q02_profile()
    result['content_evidence']['relationships'] = policy()
    return result

def policy():
    return {'method': 'local-function-block-v1', 'unresolved': 'reject',
        'coverage': {'mode': 'selected_regions', 'source_sha256': SOURCE, 'regions': [
            {'id': f'page-{page}', 'page': page, 'box': box, 'required_count': 1}
            for page, box in [(3, [100,75,500,290]), (5, [100,75,500,350]),
                              (9, [100,75,500,285]), (10, [100,85,500,205])]]},
        'representation': json.loads((ROOT/'reviewed-representation.json').read_text())}
