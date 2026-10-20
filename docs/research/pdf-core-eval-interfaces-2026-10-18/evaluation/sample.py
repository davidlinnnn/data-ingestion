"""Evaluator-only metadata sampling. Never export text, LaTeX, HTML, polygons or answers."""
import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import zip_longest
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def store_frozen(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('frozen output differs; create a new registration revision')
        return
    path.write_bytes(data)


def metadata(page):
    info = page['page_info']
    attrs = info['page_attribute']
    categories = Counter(item['category_type'] for item in page['layout_dets'] if not item.get('ignore', False))
    # No filename-based family inference: authoritative provenance is absent in this release.
    family = info.get('source_document_id') or info.get('source_pdf_sha256')
    return {
        'page_id': info['image_path'], 'page_no': info.get('page_no'),
        'sample_id': info.get('sample_id'), 'width': info['width'], 'height': info['height'],
        'language': attrs.get('language', 'unknown'), 'layout': attrs.get('layout', 'unknown'),
        'data_source': attrs.get('data_source', 'unknown'), 'subset': attrs.get('subset', 'unknown'),
        'special_issue': sorted(attrs.get('special_issue', [])),
        'category_counts': dict(sorted(categories.items())),
        'ignored_units': sum(bool(item.get('ignore', False)) for item in page['layout_dets']),
        'verified_family': str(family) if family else None,
        'family_group': 'verified:' + str(family) if family else 'unresolved-provenance',
    }


def stratum(row):
    cats, issues = row['category_counts'], set(row['special_issue'])
    if cats.get('table'):
        if 'table_with_formula' in issues:
            return 'table_math'
        if 'table_span' in issues:
            return 'table_merged'
        return 'table_other'
    if cats.get('figure') and cats.get('figure_caption'):
        return 'figure_caption'
    if cats.get('equation_isolated'):
        return 'display_formula'
    if issues & {'fuzzy_scan', 'fuzzy_content', 'geometric_deformation', 'transparent_pages'}:
        return 'degraded_scan'
    if row['layout'] in {'double_column', 'three_column', '1andmore_column', 'other_layout'}:
        return 'multicolumn'
    if cats.get('text_block') and not any(cats.get(name) for name in ('figure', 'code_txt', 'equation_inline')) and issues <= {'None'}:
        return 'plain_control'
    return 'out_of_scope'


def select(rows, policy):
    names = [item['name'] for item in policy['strata_priority']]
    quotas = [item['quota'] for item in policy['strata_priority']]
    if type(policy['max_pages']) is not int or not 1 <= policy['max_pages'] <= 60 or any(type(q) is not int or q < 0 for q in quotas):
        raise ValueError('invalid bounded page quotas')
    if type(policy['max_pages_per_verified_family']) is not int or policy['max_pages_per_verified_family'] < 1:
        raise ValueError('invalid verified family cap')
    if len(names) != len(set(names)) or sum(quotas) > policy['max_pages']:
        raise ValueError('duplicate strata or quota exceeds cap')
    ids = [row['page_id'] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate page IDs')
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        groups[stratum(row)][(row['language'], row['data_source'])].append(row)
    chosen, counts, family_counts = [], {}, Counter()
    rank = lambda row: digest((policy['seed'] + '\0' + row['page_id']).encode())
    def interleave(sequences):
        return [row for batch in zip_longest(*sequences) for row in batch if row is not None]
    for rule in policy['strata_priority']:
        cells = groups[rule['name']]
        languages = sorted({lang for lang, _ in cells})
        by_language = [interleave([sorted(items, key=rank) for (cell_lang, _), items in sorted(cells.items()) if cell_lang == lang]) for lang in languages]
        count = 0
        for row in interleave(by_language):
            if count == rule['quota']:
                break
            family = row['verified_family']
            if family and family_counts[family] >= policy['max_pages_per_verified_family']:
                continue
            chosen.append({**row, 'stratum': rule['name'], 'selection_rank': rank(row)})
            if family:
                family_counts[family] += 1
            count += 1
        counts[rule['name']] = {'available': sum(map(len, groups[rule['name']].values())), 'quota': rule['quota'], 'selected': count, 'deficit': rule['quota'] - count}
    return chosen, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annotation', required=True, type=Path)
    args = parser.parse_args()
    lock = json.loads((HERE / 'upstream.lock.json').read_text())
    raw = args.annotation.read_bytes()
    expected = lock['dataset']['annotation_metadata'][0]['lfs']['oid']
    if digest(raw) != expected:
        raise ValueError('annotation bytes differ from locked LFS SHA256')
    pages = json.loads(raw)
    rows = [metadata(page) for page in pages]
    policy_raw = (HERE / 'sampling.json').read_bytes()
    chosen, counts = select(rows, json.loads(policy_raw))
    write = lambda name, value: store_frozen(HERE / name, value)
    inventory = {
        'schema_version': 1, 'annotation_sha256': digest(raw), 'annotation_bytes': len(raw), 'pages': len(rows),
        'page_info_keys': sorted(set().union(*(page['page_info'].keys() for page in pages))),
        'nonempty_block_attribute_count': sum(bool(block.get('attribute')) for page in pages for block in page['layout_dets']),
        'page_strata': dict(Counter(stratum(row) for row in rows)),
        'language': dict(Counter(row['language'] for row in rows)),
        'layout': dict(Counter(row['layout'] for row in rows)),
        'data_source': dict(Counter(row['data_source'] for row in rows)),
        'verified_family_pages': sum(row['verified_family'] is not None for row in rows),
        'unknown_family_policy': 'all unresolved pages share one provenance pool; independence unverified',
        'metadata_only': True,
    }
    write('metadata-inventory.json', inventory)
    manifest = {
        'schema_version': 1, 'status': 'selection_frozen_inputs_not_acquired',
        'code_commit': lock['code']['commit'], 'dataset_revision': lock['dataset']['revision'],
        'annotation_sha256': digest(raw), 'sampling_policy_sha256': digest(policy_raw),
        'page_count': len(chosen), 'strata': counts,
        'independent_source_families_verified': len({row['verified_family'] for row in chosen if row['verified_family']}),
        'unresolved_family_pages': sum(row['verified_family'] is None for row in chosen),
        'selected_marginals': {key: dict(Counter(row[key] for row in chosen)) for key in ('language', 'data_source', 'layout', 'subset')},
        'unrepresented_marginals': {key: sorted({row[key] for row in rows} - {row[key] for row in chosen}) for key in ('language', 'data_source', 'layout', 'subset')},
        'public_regression_not_company_holdout': True, 'inputs_downloaded': False,
        'producer_saw_gt': False, 'candidate_predictions_exist': False, 'pages': chosen,
    }
    write('sample-manifest.json', manifest)
    print(json.dumps({'pages': len(chosen), 'strata': counts, 'verified_source_families': manifest['independent_source_families_verified']}))


if __name__ == '__main__':
    main()
