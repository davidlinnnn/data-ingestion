"""Full structural/evidence comparison. Never strip provenance or relationships."""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def changes(a, b, path='$'):
    if type(a) is not type(b):
        return [path + ': type mismatch']
    if isinstance(a, dict):
        result = [path + ': keys mismatch'] if a.keys() != b.keys() else []
        for k in a.keys() & b.keys():
            result += changes(a[k], b[k], path + '.' + k)
        return result
    if isinstance(a, list):
        result = [path + f': length {len(a)} != {len(b)}'] if len(a) != len(b) else []
        for i, (x, y) in enumerate(zip(a, b)):
            result += changes(x, y, path + f'[{i}]')
        return result
    return [] if a == b else [path]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline', type=Path)
    p.add_argument('recovered', type=Path)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    a, b = [json.loads((d / 'document.json').read_text()) for d in (args.baseline, args.recovered)]
    diff = changes(a, b)
    am, bm = [json.loads((d / 'metrics.json').read_text()) for d in (args.baseline, args.recovered)]
    forbidden = ['PagePreprocessingModel', 'RapidOcrModel', 'LayoutModel', 'TableStructureModel', 'PageAssembleModel']
    report = {'same_full_document': not diff, 'different_paths': diff,
              'comparison': 'All JSON fields, including reading order, hierarchy, tables, captions, hyperlinks, bbox/charspan and embedded page/picture image bytes. No fields removed.',
              'fresh_process': am['pid'] != bm['pid'],
              'repeated_completed_page_stage_inputs': {k: bm['page_stage_inputs'].get(k, 0) for k in forbidden},
              'baseline': am, 'recovered': bm}
    args.out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('baseline', 'recovered')}, indent=2))
    if diff or not report['fresh_process'] or any(report['repeated_completed_page_stage_inputs'].values()):
        raise SystemExit(2)

if __name__ == '__main__':
    main()
