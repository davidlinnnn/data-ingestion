"""Compare complete outputs, with grouping supplied by the current trial."""
import json
from pathlib import Path


def verify(actual, reference, pages, group_pages, observed_groups):
    if any(type(v) is not int or v < 1 for v in (pages, group_pages)):
        raise ValueError('positive page counts required')
    expected = [[start, min(start + group_pages - 1, pages)]
                for start in range(1, pages + 1, group_pages)]
    if observed_groups != expected:
        raise ValueError('group coverage mismatch')
    for name in ('document.json', 'checks.json'):
        left = json.loads((Path(actual) / name).read_text())
        right = json.loads((Path(reference) / name).read_text())
        if left != right:
            raise ValueError(f'complete output mismatch: {name}')
    result = json.loads((Path(actual) / 'result.json').read_text())
    if result.get('processing_complete') is not True:
        raise ValueError('business completion missing')
    return {'full_output_equal': True, 'groups': len(expected), 'pages': pages}
