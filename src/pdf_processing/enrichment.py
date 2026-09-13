"""Persisted required PictureItem OCR and complete processing-result validation.

This internal contract does not grant canonical acceptance or downstream delivery.
"""
import asyncio
import json
from pathlib import Path
import tempfile

from .object_store import digest
from .compatibility import dependencies


def validate_coverage(selected, outcomes):
    actual = [item['component'] for item in outcomes]
    if len(actual) != len(set(actual)) or set(actual) != set(selected):
        raise ValueError('incomplete_required_components')
    return 'complete' if selected else 'not_applicable'


class Enrichment:
    def __init__(self, processing):
        self.processing = processing
        self.store = processing.store

    def read(self, identity, name):
        from .processing import reject
        manifest = self.store.resolve(identity)
        if manifest is None:
            reject('required_registration_missing', 'integrity')
        entries = [item for item in manifest['files'] if item['name'] == name]
        if len(entries) != 1:
            reject('required_artifact_missing', 'integrity')
        data = self.store.read_artifact(entries[0])
        return json.loads(data)

    async def run(self, value):
        from .processing import encoded, observed, reject
        from .execution import Execution, SourceRequest
        plan = await asyncio.to_thread(self.processing.load_plan, value['plan'])
        stage = value['stage']
        if stage == 'select':
            parsed_id = value['parsed_result']
            parsed = await asyncio.to_thread(self.read, parsed_id, 'parsed-result.json')
            if parsed['plan'] != value['plan'] or parsed['source'] != plan['request']:
                reject('parsed_source_mismatch', 'integrity')
            document = await asyncio.to_thread(self.read, parsed['assembly'], 'document.json')
            candidates = []
            for picture in document.get('pictures', []):
                # Even unsupported geometry is selected and must fail explicitly at crop validation.
                candidates.append({'component': picture['self_ref'], 'selected': True,
                                   'reason': 'required_picture_v1', 'provenance': picture.get('prov', [])})
            selected = [c['component'] for c in candidates if c['selected']]
            if len(selected) != len(set(selected)):
                reject('duplicate_component', 'integrity')
            selection = {'version': 1, 'rule': 'all-picture-items-v1', 'plan': value['plan'],
                'parsed_result': parsed_id, 'assembly': parsed['assembly'], 'source': plan['request'],
                'parsed_sha256': digest(encoded(document)), 'candidates': candidates, 'selected': selected,
                'excluded': [{'kind': 'page_render', 'reason': 'not_a_picture_item'}],
                'dependencies': dependencies('selection', plan['profile'], plan['producer']),
                'ocr_method': dependencies('ocr', plan['profile'], plan['producer']), 'concurrency': 1}
            identity = 'pdf-selection-v1:' + digest(encoded(selection))
            await asyncio.to_thread(self.store.publish, identity, {'selection.json': encoded(selection)})
            return {'operation': identity, 'selected': selected, 'observed_at': observed()}
        selection = await asyncio.to_thread(self.read, value['selection'], 'selection.json')
        if selection['plan'] != value['plan'] or selection['source'] != plan['request']:
            reject('selection_source_mismatch', 'integrity')
        if stage == 'component_ocr':
            component = value['component']
            if component not in selection['selected']:
                reject('component_outside_selection', 'integrity')
            identity = 'pdf-component-v1:' + digest(encoded({'selection': value['selection'], 'component': component}))
            reused = await asyncio.to_thread(self.store.resolve, identity) is not None
            if not reused:
                with tempfile.TemporaryDirectory(prefix='ocr-', dir=self.processing.scratch) as tmp:
                    root = Path(tmp)
                    request = plan['request']
                    pdf = root/request['artifact']['name']
                    await asyncio.to_thread(self.processing.read_source, request, pdf)
                    source = SourceRequest(pdf, request['source_revision'], request['artifact']['sha256'],
                                           plan['profile']['method'], self.processing.model_cache)
                    execution = Execution(source, self.store, root, child_timeout=plan['limits']['child_seconds'])
                    await asyncio.to_thread(execution.materialize, selection['assembly'], root/'parsed')
                    await execution.child('pdf_processing.ocr', {'parsed': str(root/'parsed'/'document.json'),
                        'pdf': str(pdf), 'out': str(root/'result'), 'component': component,
                        'max_render_pixels': plan['limits']['max_page_pixels'],
                        'allow_cropbox': request['version'] == 3,
                        'scale': plan['profile'].get('picture_ocr', {'render_scale': 3})['render_scale']}, root)
                    report = json.loads((root/'result'/'ocr.json').read_text())
                    if (report['source_sha256'] != request['artifact']['sha256'] or report['component'] != component
                            or report['parsed_result_sha256'] != digest((root/'parsed'/'document.json').read_bytes())):
                        reject('ocr_source_mismatch', 'integrity')
                    expected_models = {k.split('/')[-1]: v for k, v in plan['profile']['method']['model_artifacts'].items() if k.startswith('rapidocr/')}
                    producer = report['producer']
                    if (producer['model_sha256'] != expected_models
                            or producer['version'] != plan['profile']['method']['packages']['rapidocr']
                            or producer['backend'] != 'onnxruntime '+plan['profile']['method']['packages']['onnxruntime']):
                        reject('ocr_method_mismatch', 'method')
                    candidate = next(c for c in selection['candidates'] if c['component'] == component)
                    if candidate['provenance'] != [report['provenance']]:
                        reject('ocr_region_mismatch', 'integrity')
                    report.update(version=1, selection=value['selection'], parsed_result=selection['parsed_result'],
                        assembly=selection['assembly'], source=request, method=selection['ocr_method'],
                        outcome='text_detected' if report['texts'] else 'no_text_detected',
                        quality_accepted=False)
                    (root/'result'/'ocr.json').write_bytes(encoded(report))
                    await asyncio.to_thread(self.store.publish, identity,
                        {p.name: p.read_bytes() for p in (root/'result').iterdir() if p.is_file()})
            report = await asyncio.to_thread(self.read, identity, 'ocr.json')
            return {'operation': identity, 'component': component, 'outcome': report['outcome'],
                    'stage': 'component_ocr', 'reused': reused, 'observed_at': observed()}
        outcomes = []
        for identity in value['outcomes']:
            report = await asyncio.to_thread(self.read, identity, 'ocr.json')
            if (report['selection'] != value['selection'] or report['source'] != plan['request']
                    or report['method'] != selection['ocr_method'] or report['parsed_result'] != selection['parsed_result']
                    or report['outcome'] not in ('text_detected', 'no_text_detected')):
                reject('ocr_attribution_mismatch', 'integrity')
            registration = await asyncio.to_thread(self.store.resolve, identity)
            crops = [f for f in registration['files'] if f['name'] == 'figure.png']
            if len(crops) != 1 or crops[0]['sha256'] != report['crop_sha256']:
                reject('ocr_crop_reference_invalid', 'integrity')
            outcomes.append({'component': report['component'], 'operation': identity, 'outcome': report['outcome']})
        try:
            coverage = validate_coverage(selection['selected'], outcomes)
        except ValueError:
            reject('incomplete_required_components', 'integrity')
        parsed = await asyncio.to_thread(self.read, selection['parsed_result'], 'parsed-result.json')
        document = await asyncio.to_thread(self.read, selection['assembly'], 'document.json')
        if digest(encoded(document)) != selection['parsed_sha256']:
            reject('selection_parsed_version_mismatch', 'integrity')
        if sorted(int(n) for n in document['pages']) != list(range(1, plan['pages']+1)):
            reject('incomplete_page_coverage', 'integrity')
        if parsed['plan'] != value['plan'] or parsed['source'] != plan['request'] or len(parsed['page_groups']) != len(plan['groups']):
            reject('parsed_plan_mismatch', 'integrity')
        for group, (start, end) in zip(parsed['page_groups'], plan['groups']):
            complete = await asyncio.to_thread(self.read, group, 'complete.json')
            checkpoints = [await asyncio.to_thread(self.read, group, 'checkpoints/'+p['file']) for p in complete['pages']]
            if (complete['source_sha256'] != plan['request']['artifact']['sha256']
                    or [p['page_no'] for p in checkpoints] != list(range(start, end+1))):
                reject('page_group_coverage_mismatch', 'integrity')
        final = {'version': 1, 'status': 'complete', 'processing_complete': True, 'canonical_accepted': False,
            'plan': value['plan'], 'source': plan['request'], 'parsed_result': selection['parsed_result'],
            'assembly': selection['assembly'], 'selection': value['selection'], 'enrichments': outcomes,
            'required_work': {'pages': plan['pages'], 'components': len(outcomes), 'ocr': coverage},
            'quality_accepted': False,
            'dependencies': dependencies('finalize', plan['profile'], plan['producer']),
            'provenance': {'profile': plan['profile'], 'producer': plan['producer']}}
        if plan['request']['version'] == 3:
            final['version'] = 2
            final['content_evidence'] = await self.content_evidence(plan, selection, document)
        identity = 'pdf-complete-v1:' + digest(encoded(final))
        await asyncio.to_thread(self.store.publish, identity, {'processing-result.json': encoded(final)})
        return {'operation': identity, 'stage': 'finalize', 'observed_at': observed()}

    async def content_evidence(self, plan, selection, document):
        from .processing import encoded
        from .execution import Execution, SourceRequest
        policy = plan['profile'].get('content_evidence', {'version': 'typed-source-evidence-v1', 'reviews': {}})
        request = plan['request']
        review = policy.get('reviews', {}).get(request['artifact']['sha256'], {})
        identity = 'pdf-evidence-v1:' + digest(encoded({'assembly': selection['assembly'],
            'parsed_result': selection['parsed_result'], 'source': request, 'policy': policy,
            'dependencies': dependencies('evidence', plan['profile'], plan['producer'])}))
        if await asyncio.to_thread(self.store.resolve, identity) is not None:
            return identity
        with tempfile.TemporaryDirectory(prefix='activity-evidence-', dir=self.processing.scratch) as tmp:
            root = Path(tmp)
            # Separate fixed scratch paths: a client filename such as original.pdf
            # must not alias the retained original source during derivative checks.
            pdf = root/'source.pdf'
            await asyncio.to_thread(self.processing.read_source, request, pdf)
            original = review.get('original_source')
            original_path = root/'original.pdf'
            if original:
                await asyncio.to_thread(self.processing.read_source, original, original_path)
            parsed_path = root/'document.json'
            registration = await asyncio.to_thread(self.store.resolve, selection['assembly'])
            entry = next(f for f in registration['files'] if f['name'] == 'document.json')
            parsed_path.write_bytes(await asyncio.to_thread(self.store.read_artifact, entry))
            source = SourceRequest(pdf, request['source_revision'], request['artifact']['sha256'],
                                   plan['profile']['method'], self.processing.model_cache)
            execution = Execution(source, self.store, root, child_timeout=plan['limits']['child_seconds'])
            await execution.child('pdf_processing.evidence', {'pdf': str(pdf), 'parsed': str(parsed_path),
                'out': str(root/'result'), 'source': request, 'parsed_result': selection['parsed_result'],
                'assembly': selection['assembly'], 'review': review, 'policy': policy['version'],
                'original_pdf': str(original_path) if original else None,
                'renderer_version': plan['profile']['method']['packages']['pypdfium2'],
                'max_render_pixels': plan['limits']['max_page_pixels']}, root)
            files = {p.name: p.read_bytes() for p in (root/'result').iterdir() if p.is_file()}
            files['source.pdf'] = pdf.read_bytes()
            if original:
                files['original-source.pdf'] = original_path.read_bytes()
            await asyncio.to_thread(self.store.publish, identity, files)
        await asyncio.to_thread(self.store.resolve, identity)
        return identity
