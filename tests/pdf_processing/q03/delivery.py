"""Local final-result seam with real evidence rendering; only S3 transport is fake.

No Temporal execution is claimed by these tests. The runtime driver uses the same
seeded-finalization seam with actual Activities and shared object storage.
"""
import copy
import json
from functools import lru_cache
from pathlib import Path
import tempfile
from fixtures import document, SOURCE
from test_publication import MemoryS3, seed
from q03_fixtures import profile
from pdf_processing.compatibility import dependencies
from pdf_processing.evidence import execute
from pdf_processing.enrichment import Enrichment
from pdf_processing.object_store import Store, digest
from pdf_processing.processing import Processing, encoded
from pdf_processing.relationships import build

class DeliveryFailure(Exception):
    def __init__(self, error, store):
        super().__init__(str(error))
        self.error, self.store = error, store


REQUEST = {'version': 3, 'source_revision': 'q03-private-replay', 'artifact': {'sha256': SOURCE}}

@lru_cache(maxsize=1)
def serialized_document():
    from docling_core.types.doc import DoclingDocument
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/'document.json'
        DoclingDocument.model_validate(document()).save_as_json(path)
        return json.loads(path.read_bytes())

@lru_cache(maxsize=1)
def rendered_files():
    with tempfile.TemporaryDirectory(prefix='q03-render-') as tmp:
        root = Path(tmp)
        (root/'document.json').write_bytes(encoded(serialized_document()))
        source = Path('/private/tmp/t09a-fixtures/08.pdf').read_bytes()
        assert digest(source) == SOURCE
        execute({'out': str(root/'out'), 'parsed': str(root/'document.json'),
            'pdf': '/private/tmp/t09a-fixtures/08.pdf', 'source': REQUEST,
            'parsed_result': 'parsed', 'assembly': 'assembly', 'review': {},
            'policy': 'typed-source-relationships-v2', 'relationships': profile()['content_evidence']['relationships'],
            'renderer_version': 'retained-test-runtime', 'max_render_pixels': 20_000_000})
        return {p.name: p.read_bytes() for p in (root/'out').iterdir()} | {'source.pdf': source}

async def deliver(prof=None, change_report=None, change_files=None, doc=None):
    """Failures expose the Store so callers can prove no complete publication."""
    prof = prof or profile()
    doc = doc or serialized_document()
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(MemoryS3(), 'test', 'q03')
        processing = Processing(store, tmp, tmp, prof)
        seed(processing, doc, REQUEST)
        files = copy.deepcopy(rendered_files())
        report = build(doc, REQUEST, 'parsed', 'assembly', prof['content_evidence']['relationships'])
        if change_report: change_report(report)
        content = json.loads(files['content-evidence.json'])
        content['document_sha256'] = digest(encoded(doc))
        files['content-evidence.json'] = encoded(content)
        files['relationships.json'] = encoded(report)
        if change_files: change_files(files)
        identity = 'pdf-evidence-v1:' + digest(encoded({'assembly': 'assembly', 'parsed_result': 'parsed',
            'source': REQUEST, 'policy': prof['content_evidence'],
            'dependencies': dependencies('evidence', prof, processing.producer)}))
        store.publish(identity, files)
        enrichment = Enrichment(processing)
        value = {'stage': 'finalize', 'plan': 'plan', 'selection': 'selection', 'outcomes': []}
        try:
            result = await enrichment.run(value)
            final = enrichment.read(result['operation'], 'processing-result.json')
            binding = enrichment.read(final['relationships'], 'relationships.json')
            replay = await enrichment.run(value)
            assert replay['operation'] == result['operation']
            return final, binding, store
        except Exception as error:
            raise DeliveryFailure(error, store) from error

def complete_registrations(store):
    return [json.loads(data)['operation'] for key, data in store.client.objects.items()
            if '/registered/' in key and json.loads(data)['operation'].startswith('pdf-complete-')]
