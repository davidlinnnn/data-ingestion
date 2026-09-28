"""Retained checkpoint seam: structure and representation are separate claims."""
import copy
import unittest
from fixtures import document, SOURCE
from oracle.score import score
from pdf_processing.relationships import build, validate
from q03_fixtures import policy

class RepresentationReplay(unittest.TestCase):
    def test_four_structures_preserve_source_reviewed_uncertainty(self):
        doc = document()
        original = copy.deepcopy(doc)
        source = {'artifact': {'sha256': SOURCE}}
        report = build(doc, source, 'parsed', 'assembly', policy())
        self.assertEqual(len(report['resolved']), 4)
        self.assertEqual(report['unresolved'], [])
        validate(report, doc, source, 'parsed', 'assembly', policy())
        candidate = {**report['candidates'], 'relationships': [
            {**r, 'disposition': 'candidate'} for r in report['resolved']]}
        self.assertEqual([r['structure_pass'] for r in score(doc, candidate)], [True]*4)
        self.assertEqual(doc, original)
        depth = report['resolved'][2]['representation']
        self.assertFalse(depth['source_native_equal'])
        self.assertEqual(depth['semantic_equivalence'], 'not_claimed')
        self.assertEqual([d['kind'] for d in depth['streams']['header_body']['differences']],
                         ['minus_hyphen', 'combining_control'])
        self.assertEqual(depth['isolated_symbols'][0]['member']['order'], None)
        self.assertEqual(depth['isolated_symbols'][0]['evidence']['scope'], 'full_page_context')


class RepresentationRegressions(unittest.TestCase):
    def test_only_reviewed_differences_are_allowed(self):
        for mutation in ('unreviewed_text', 'missing_mark', 'caption_corruption'):
            doc = document()
            if mutation == 'missing_mark':
                doc['texts'] = [i for i in doc['texts'] if not (i['text'] == '\u0338' and i['prov'][0]['page_no'] == 9)]
            else:
                item = next(i for i in doc['texts'] if i['prov'] and i['prov'][0]['page_no'] == (10 if mutation == 'caption_corruption' else 9)
                            and ('Figure 3.18' in i['text'] if mutation == 'caption_corruption' else 'RECURSIVE-DLS' in i['text']))
                item['text'] = item['text'].replace('search', 'WRONG!') if mutation == 'caption_corruption' else item['text'].replace('RECURSIVE-DLS', 'RECURSIVE-XYZ')
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'unreviewed'):
                build(doc, {'artifact': {'sha256': SOURCE}}, 'parsed', 'assembly', policy())

    def test_comparison_offsets_are_not_used_as_raw_item_ranges(self):
        doc = document()
        report = build(doc, {'artifact': {'sha256': SOURCE}}, 'parsed', 'assembly', policy())
        depth = report['resolved'][2]['representation']['streams']['header_body']['differences']
        minus = depth[0]
        raw = minus['raw_extracted_ranges'][0]
        item = next(i for i in doc['texts'] if i['self_ref'] == raw['ref'])
        self.assertEqual(item['text'][slice(*raw['range'])], '-')
        self.assertNotEqual(raw['range'], minus['extracted_range'])
        self.assertEqual(depth[1]['raw_extracted_ranges'], [])
        caption = report['resolved'][3]['representation']['streams']['caption']['differences']
        self.assertEqual([d['raw_extracted_ranges'] for d in caption], [[], []])

    def test_review_policy_rejects_unknown_and_misattributed_annotations(self):
        from pdf_processing.relationships import validate_policy
        for case in ('version', 'wrong_source', 'wrong_page', 'duplicate', 'missing', 'unknown_disposition', 'boolean_offset', 'incomplete_stream', 'unknown_field', 'allow_unknown'):
            value = policy()
            representation = value['representation']
            review = representation['reviews'][2]
            difference = review['streams']['header_body']['differences'][0]
            if case == 'version': representation['version'] = 'unknown'
            elif case == 'wrong_source': review['source_sha256'] = 'a'*64
            elif case == 'wrong_page': review['page'] = 8
            elif case == 'duplicate': representation['reviews'].append(copy.deepcopy(review))
            elif case == 'missing': representation['reviews'].pop()
            elif case == 'unknown_disposition': difference['disposition'] = 'strip_symbol'
            elif case == 'boolean_offset': difference['source_range'][0] = True
            elif case == 'incomplete_stream': del review['streams']['caption']
            elif case == 'unknown_field': difference['normalize'] = True
            elif case == 'allow_unknown': value['unresolved'] = 'allow_unknown'
            with self.subTest(case=case), self.assertRaises(ValueError): validate_policy(value)
