"""Consumer-visible final delivery, never just a validation-helper exception."""
import unittest
from temporalio.exceptions import ApplicationError
from delivery import deliver, complete_registrations, DeliveryFailure
from q03_fixtures import profile

class Q03Publication(unittest.IsolatedAsyncioTestCase):
    async def test_selected_disposition_delivers_all_four_and_gate_prevents_completion(self):
        final, binding, _ = await deliver()
        self.assertTrue(final['processing_complete'])
        self.assertFalse(final['quality_accepted'])
        self.assertFalse(final['canonical_accepted'])
        self.assertEqual(len(binding['relationships']['resolved']), 4)
        prof = profile()
        prof['content_evidence']['relationships']['representation']['reviews'][2]['streams']['header_body']['differences'][0]['disposition'] = 'release_gate'
        with self.assertRaises(DeliveryFailure) as failure:
            await deliver(prof)
        self.assertEqual(complete_registrations(failure.exception.store), [])


class Q03ReadableEvidence(unittest.IsolatedAsyncioTestCase):
    async def test_hash_consistent_unreadable_source_evidence_cannot_complete(self):
        import json
        from pdf_processing.processing import encoded
        from pdf_processing.object_store import digest
        def replace_page(files):
            data = b'not an image, but the registration hash is consistent'
            content = json.loads(files['content-evidence.json'])
            page = content['pages']['9']
            files[page['artifact']] = data
            page['sha256'] = digest(data)
            files['content-evidence.json'] = encoded(content)
        with self.assertRaises(DeliveryFailure) as failure:
            await deliver(change_files=replace_page)
        self.assertEqual(complete_registrations(failure.exception.store), [])

class Q03UnsupportedPolicy(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_difference_kind_is_rejected_before_work(self):
        prof = profile()
        prof['content_evidence']['relationships']['representation']['reviews'][2]['streams']['header_body']['differences'][0]['kind'] = 'semantic_equivalence'
        with self.assertRaisesRegex(ValueError, 'unsupported_representation_difference'):
            await deliver(prof)

class Q03AttributionFailures(unittest.IsolatedAsyncioTestCase):
    async def test_tampered_representation_and_required_structure_fail_before_publication(self):
        from fixtures import mutate, FAILURES
        from delivery import serialized_document
        def change(report, case):
            if case in FAILURES:
                updated = mutate(report, case, serialized_document())
                report.clear(); report.update(updated)
                return
            relation = report['resolved'][2]
            representation = relation['representation']
            difference = representation['streams']['header_body']['differences'][0]
            if case == 'fabricated_symbol_position': representation['isolated_symbols'][0]['position_in_body'] = 1
            elif case == 'missing_symbol': relation['symbol_uncertainty'].clear()
            elif case == 'wrong_raw_offset': difference['raw_extracted_ranges'][0]['range'] = [447, 448]
            elif case == 'wrong_comparison_offset': difference['extracted_range'][0] += 1
            elif case == 'missing_disposition': del difference['disposition']
            elif case == 'false_equality': representation['source_native_equal'] = True
            elif case == 'wrong_review': representation['review_id'] = 'unrelated'
            elif case == 'outside_source': representation['evidence']['page'] = 8
            elif case == 'missing_recursive_body': relation['members'].pop(1)
            elif case == 'missing_caption': report['resolved'][3]['members'].pop()
        cases = FAILURES + ['fabricated_symbol_position', 'missing_symbol', 'wrong_raw_offset',
            'wrong_comparison_offset', 'missing_disposition', 'false_equality', 'wrong_review',
            'outside_source', 'missing_recursive_body', 'missing_caption']
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(DeliveryFailure) as failure:
                    await deliver(change_report=lambda r: change(r, case))
                self.assertIsInstance(failure.exception.error, ApplicationError)
                self.assertEqual(complete_registrations(failure.exception.store), [])

    async def test_each_observation_can_independently_block_release(self):
        for review_index, stream, difference_index in [(2, 'header_body', 0), (2, 'header_body', 1),
                (3, 'header_body', 0), (3, 'caption', 0), (3, 'caption', 1), (2, 'symbol', 0), (3, 'symbol', 0)]:
            with self.subTest(review=review_index, stream=stream, difference=difference_index):
                prof = profile()
                review = prof['content_evidence']['relationships']['representation']['reviews'][review_index]
                observation = review['isolated_symbols'][0] if stream == 'symbol' else review['streams'][stream]['differences'][difference_index]
                observation['disposition'] = 'release_gate'
                with self.assertRaises(DeliveryFailure) as failure:
                    await deliver(prof)
                self.assertIn('representation_release_gate', str(failure.exception))
                self.assertEqual(complete_registrations(failure.exception.store), [])

    async def test_corrupt_or_wrongly_attributed_evidence_fails(self):
        import json
        from pdf_processing.processing import encoded
        for case in ('wrong_page', 'wrong_source', 'wrong_document', 'missing_page', 'missing_source', 'wrong_policy'):
            def change(files):
                content = json.loads(files['content-evidence.json'])
                if case == 'wrong_page': content['pages']['9']['physical_page'] = 10
                elif case == 'wrong_source': content['source']['source_revision'] = 'other'
                elif case == 'wrong_document': content['document_sha256'] = 'a'*64
                elif case == 'missing_page': del files[content['pages']['9']['artifact']]
                elif case == 'missing_source': del files['source.pdf']
                elif case == 'wrong_policy': content['policy'] = 'typed-source-evidence-v1'
                files['content-evidence.json'] = encoded(content)
            with self.subTest(case=case):
                with self.assertRaises(DeliveryFailure) as failure:
                    await deliver(change_files=change)
                self.assertEqual(complete_registrations(failure.exception.store), [])

    async def test_fragmentation_survives_final_delivery(self):
        from fixtures import mutate
        from delivery import serialized_document
        from oracle.score import score
        def split(report):
            updated = mutate(report, 'split', serialized_document())
            report.clear(); report.update(updated)
        _, binding, _ = await deliver(change_report=split)
        report = binding['relationships']
        candidate = {**report['candidates'], 'relationships': [{**r, 'disposition': 'candidate'} for r in report['resolved']]}
        self.assertEqual([r['structure_pass'] for r in score(serialized_document(), candidate)], [True]*4)
        self.assertEqual(len(binding['representation_evidence']), 4)
        self.assertEqual(len(binding['representation_evidence'][2]['views']), 2)

class Q03TypedRanges(unittest.IsolatedAsyncioTestCase):
    async def test_symbol_and_comparison_offsets_cannot_masquerade_as_integers(self):
        for case in ('boolean_symbol_range', 'float_raw_range', 'float_comparison_range'):
            def change(report):
                relation = report['resolved'][2]
                difference = relation['representation']['streams']['header_body']['differences'][0]
                if case == 'boolean_symbol_range': relation['symbol_uncertainty'][0]['range'][0] = False
                elif case == 'float_raw_range':
                    bounds = difference['raw_extracted_ranges'][0]['range']
                    bounds[0] = float(bounds[0])
                else:
                    bounds = difference['extracted_range']
                    bounds[0] = float(bounds[0])
            with self.subTest(case=case):
                with self.assertRaises(DeliveryFailure) as failure:
                    await deliver(change_report=change)
                self.assertEqual(complete_registrations(failure.exception.store), [])

class Q03DecodedEvidence(unittest.IsolatedAsyncioTestCase):
    async def test_valid_png_checksums_with_undecodable_pixels_cannot_complete(self):
        import json
        import struct
        import zlib
        from pdf_processing.processing import encoded
        from pdf_processing.object_store import digest
        def corrupt_pixels(files):
            content = json.loads(files['content-evidence.json'])
            page = content['pages']['9']
            original = files[page['artifact']]
            chunks = [original[:8]]
            offset = 8
            replaced = False
            while offset < len(original):
                length = struct.unpack('>I', original[offset:offset+4])[0]
                kind = original[offset+4:offset+8]
                if kind == b'IDAT':
                    if not replaced:
                        data = b'not a zlib-compressed pixel stream'
                        chunks.append(struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)))
                        replaced = True
                else:
                    chunks.append(original[offset:offset+length+12])
                offset += length+12
            self.assertTrue(replaced)
            damaged = b''.join(chunks)
            files[page['artifact']] = damaged
            page['sha256'] = digest(damaged)
            files['content-evidence.json'] = encoded(content)
        with self.assertRaises(DeliveryFailure) as failure:
            await deliver(change_files=corrupt_pixels)
        self.assertEqual(complete_registrations(failure.exception.store), [])
