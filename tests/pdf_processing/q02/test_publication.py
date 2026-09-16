"""Fast final-result barrier tests; real Temporal/shared storage driver is separate."""
import io
import json
import tempfile
import unittest
from botocore.exceptions import ClientError
from temporalio.exceptions import ApplicationError
from pdf_processing.processing import Processing, encoded
from pdf_processing.enrichment import Enrichment
from pdf_processing.relationships import build, POLICY
from pdf_processing.object_store import Store, digest
from fixtures import document, policy, mutate, FAILURES, SOURCE


class MemoryS3:
    """Only transport is in-memory; registrations and integrity checks use Store."""
    def __init__(self): self.objects = {}
    def get_object(self, Bucket, Key, **kwargs):
        if Key not in self.objects:
            raise ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
        return {'Body': io.BytesIO(self.objects[Key]), 'ContentLength': len(self.objects[Key])}
    def put_object(self, Bucket, Key, Body, **kwargs):
        if kwargs.get('IfNoneMatch') and Key in self.objects:
            raise ClientError({'Error': {'Code': 'PreconditionFailed'}}, 'PutObject')
        self.objects[Key] = Body
        return {'VersionId': 'test-version'}


def profile():
    return {'id': 'native-v1', 'method': {'options': {'do_ocr': False}, 'python': '3.12',
            'platform': 'test', 'packages': {}, 'model_artifacts': {}},
            'content_evidence': {'version': POLICY, 'reviews': {}, 'relationships': policy()}}


def seed(processing, doc, request, document_bytes=None):
    store = processing.store
    plan = {'profile': processing.profile, 'producer': processing.producer, 'limits': processing.limits,
            'request': request, 'pages': len(doc['pages']), 'groups': [[1, len(doc['pages'])]]}
    store.publish('plan', {'plan.json': encoded(plan)})
    store.publish('assembly', {'document.json': document_bytes if document_bytes is not None else encoded(doc)})
    checkpoints = {'complete.json': encoded({'source_sha256': SOURCE,
        'pages': [{'file': f'{i}.json'} for i in range(1, len(doc['pages'])+1)]})}
    checkpoints.update({f'checkpoints/{i}.json': encoded({'page_no': i}) for i in range(1, len(doc['pages'])+1)})
    store.publish('group', checkpoints)
    parsed = {'plan': 'plan', 'source': request, 'assembly': 'assembly', 'page_groups': ['group']}
    store.publish('parsed', {'parsed-result.json': encoded(parsed)})
    selection = {'plan': 'plan', 'source': request, 'assembly': 'assembly', 'parsed_result': 'parsed',
                 'parsed_sha256': digest(encoded(doc)), 'selected': [], 'ocr_method': {}}
    store.publish('selection', {'selection.json': encoded(selection)})
    return plan, selection


class Publication(unittest.IsolatedAsyncioTestCase):
    async def attempt(self, case):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(MemoryS3(), 'test', 'q02')
            prof = profile()
            if case == 'allowed_unknown':
                prof['content_evidence']['relationships'] = {'method': 'local-function-block-v1',
                    'coverage': {'mode': 'unknown'}, 'unresolved': 'allow_unknown'}
            if case == 'required_missing':
                prof['content_evidence']['relationships']['coverage']['regions'][0]['required_count'] = 2
            processing = Processing(store, tmp, tmp, prof)
            doc = document()
            request = {'version': 3, 'source_revision': 'private-replay', 'artifact': {'sha256': SOURCE}}
            document_bytes = json.dumps(doc, indent=2).encode() if case in ('formatted_json', 'wrong_document_digest') else encoded(doc)
            plan, selection = seed(processing, doc, request, document_bytes)
            report = build(doc, request, 'parsed', 'assembly', prof['content_evidence']['relationships'])
            report = mutate(report, case, doc)
            content = {'source': request, 'parsed_result': 'parsed', 'assembly': 'assembly', 'policy': POLICY,
                       'document_sha256': digest(document_bytes), 'pages': {}}
            # Fast test source/pages are synthetic; real rendering is covered by runtime driver.
            files = {'relationships.json': encoded(report)}
            for n in doc['pages']:
                data = b'page evidence fixture'
                files[f'page-{n}.png'] = data
                content['pages'][n] = {'artifact': f'page-{n}.png', 'sha256': digest(data)}
            if case == 'wrong_document_digest': content['document_sha256'] = digest(encoded(doc))
            files['content-evidence.json'] = encoded(content)
            source = __import__('pathlib').Path('/private/tmp/t09a-fixtures/08.pdf').read_bytes()
            self.assertEqual(digest(source), SOURCE)
            files['source.pdf'] = source
            if case == 'missing_output': del files['relationships.json']
            if case == 'wrong_page': content['pages']['3']['sha256'] = '0'*64; files['content-evidence.json'] = encoded(content)
            if case == 'missing_ocr':
                selection['selected'] = ['#/pictures/required']
                store.client.objects.clear()
                plan, _ = seed(processing, doc, request)
                store.publish('selection-with-ocr', {'selection.json': encoded(selection)})
            from pdf_processing.compatibility import dependencies
            identity = 'pdf-evidence-v1:' + digest(encoded({'assembly': 'assembly', 'parsed_result': 'parsed',
                'source': request, 'policy': prof['content_evidence'],
                'dependencies': dependencies('evidence', prof, processing.producer)}))
            store.publish(identity, files)
            value = {'stage': 'finalize', 'plan': 'plan', 'selection': 'selection-with-ocr' if case == 'missing_ocr' else 'selection', 'outcomes': []}
            if case in ('valid', 'split', 'allowed_unknown', 'formatted_json'):
                result = await Enrichment(processing).run(value)
                final = Enrichment(processing).read(result['operation'], 'processing-result.json')
                self.assertTrue(final['processing_complete'])
                self.assertFalse(final['quality_accepted'])
                self.assertFalse(final['canonical_accepted'])
                binding = Enrichment(processing).read(final['relationships'], 'relationships.json')
                self.assertEqual(bool(binding['relationships']['unresolved']), case == 'allowed_unknown')
            else:
                with self.assertRaises(ApplicationError):
                    await Enrichment(processing).run(value)
                registrations = [json.loads(v)['operation'] for k, v in store.client.objects.items() if '/registered/' in k]
                self.assertFalse(any(i.startswith('pdf-complete-') for i in registrations))

    async def test_formatted_json_delivery(self): await self.attempt('formatted_json')
    async def test_wrong_document_digest_rejected(self): await self.attempt('wrong_document_digest')

    async def test_valid_delivery(self): await self.attempt('valid')
    async def test_split_ranges_delivered(self): await self.attempt('split')
    async def test_explicit_unknown_delivered(self): await self.attempt('allowed_unknown')
    async def test_required_failures_never_publish_complete(self):
        for case in FAILURES + ['required_missing', 'missing_output', 'wrong_page', 'missing_ocr']:
            with self.subTest(case=case): await self.attempt(case)
