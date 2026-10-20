import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sample import digest, metadata, select, stratum, store_frozen
from check import verify_files

HERE = Path(__file__).resolve().parent
POLICY = json.loads((HERE / 'sampling.json').read_text())


def row(name, language='english', source='book', family=None, categories=None, issues=None):
    return {
        'page_id': name, 'language': language, 'data_source': source, 'layout': 'single_column',
        'category_counts': categories or {'text_block': 1}, 'special_issue': issues or [],
        'verified_family': family, 'family_group': 'verified:' + family if family else 'unresolved-provenance',
    }


def control_policy(quota):
    return {**POLICY, 'strata_priority': [{'name': 'plain_control', 'quota': quota}]}


class SamplingTests(unittest.TestCase):
    def test_deterministic_under_input_permutation(self):
        rows = [row(str(i)) for i in range(10)]
        self.assertEqual(select(rows, control_policy(4)), select(list(reversed(rows)), control_policy(4)))
        self.assertEqual(json.dumps(select(rows, control_policy(4))), json.dumps(select(list(reversed(rows)), control_policy(4))))

    def test_frozen_output_refuses_refresh(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'manifest.json'
            store_frozen(path, {'version': 1})
            original = path.read_bytes()
            store_frozen(path, {'version': 1})
            with self.assertRaises(ValueError):
                store_frozen(path, {'version': 2})
            self.assertEqual(path.read_bytes(), original)

    def test_lock_detects_mutated_bytes(self):
        with TemporaryDirectory() as folder:
            base = Path(folder)
            path = base / 'config'
            path.write_bytes(b'original')
            entries = [{'path': 'config', 'size_bytes': 8, 'sha256': digest(b'original')}]
            verify_files(base, entries)
            path.write_bytes(b'mutation')
            with self.assertRaises(ValueError):
                verify_files(base, entries)

    def test_quotas_never_backfilled(self):
        rows = [row('only')]
        chosen, counts = select(rows, POLICY)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(counts['table_math']['deficit'], 10)

    def test_priority_uses_annotation_labels_without_table_answer(self):
        item = row('x', categories={'table': 2, 'figure': 1}, issues=['table_span', 'table_with_formula'])
        self.assertEqual(stratum(item), 'table_math')

    def test_plain_control_excludes_unpaired_figure_and_code(self):
        for category in ('figure', 'code_txt', 'equation_inline'):
            self.assertEqual(stratum(row('x', categories={'text_block': 1, category: 1})), 'out_of_scope')

    def test_duplicate_page_ids_refused(self):
        with self.assertRaises(ValueError):
            select([row('same'), row('same')], control_policy(2))

    def test_verified_family_cap_global_across_groups(self):
        rows = [row(str(i), language=str(i), family='same-paper') for i in range(8)]
        chosen, _ = select(rows, control_policy(8))
        self.assertEqual(len(chosen), 2)

    def test_unknown_family_does_not_fake_independence_or_cap_to_two(self):
        chosen, _ = select([row(str(i)) for i in range(8)], control_policy(8))
        self.assertEqual(len(chosen), 8)
        self.assertEqual({x['family_group'] for x in chosen}, {'unresolved-provenance'})
        self.assertTrue(all(x['verified_family'] is None for x in chosen))

    def test_round_robin_balances_language_document_groups(self):
        rows = [row('dominant-' + str(i), source='book') for i in range(20)]
        rows += [row('minority-document', source='PPT2PDF'), row('minority-language', language='traditional_chinese')]
        chosen, _ = select(rows, control_policy(3))
        self.assertEqual({(x['language'], x['data_source']) for x in chosen}, {('english', 'book'), ('english', 'PPT2PDF'), ('traditional_chinese', 'book')})

    def test_languages_not_weighted_by_number_of_document_cells(self):
        rows = [row('english-' + str(i), source=str(i)) for i in range(20)]
        rows += [row('traditional-' + str(i), language='traditional_chinese') for i in range(5)]
        chosen, _ = select(rows, control_policy(4))
        self.assertEqual(sum(x['language'] == 'english' for x in chosen), 2)
        self.assertEqual(sum(x['language'] == 'traditional_chinese' for x in chosen), 2)

    def test_answer_fields_never_exported(self):
        page = {'page_info': {'image_path': 'id.png', 'page_no': 0, 'height': 10, 'width': 10, 'page_attribute': {'language': 'english', 'data_source': 'book'}}, 'layout_dets': [{'category_type': 'text_block', 'text': 'ANSWER_CANARY', 'latex': 'ANSWER_CANARY', 'html': 'ANSWER_CANARY', 'poly': [1, 2], 'ignore': False}]}
        self.assertNotIn('ANSWER_CANARY', json.dumps(metadata(page)))
        self.assertNotIn('poly', metadata(page))

    def test_invalid_budget_refused(self):
        for cap in (0, 61, -1, True):
            policy = control_policy(1)
            policy['max_pages'] = cap
            with self.assertRaises(ValueError):
                select([row('x')], policy)

    def test_real_manifest_binding_and_marginals(self):
        manifest = json.loads((HERE / 'sample-manifest.json').read_text())
        self.assertEqual(manifest['sampling_policy_sha256'], digest((HERE / 'sampling.json').read_bytes()))
        self.assertEqual(manifest['page_count'], 60)
        self.assertEqual(len({x['page_id'] for x in manifest['pages']}), 60)
        self.assertEqual(manifest['unresolved_family_pages'], 60)
        self.assertEqual(manifest['independent_source_families_verified'], 0)
        self.assertTrue(all(x['deficit'] == 0 for x in manifest['strata'].values()))
        self.assertGreater(len(manifest['selected_marginals']['data_source']), 1)


if __name__ == '__main__':
    unittest.main()
