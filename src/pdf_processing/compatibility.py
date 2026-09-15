"""Internal v2 dependency contract. Full observed provenance is never projected away.

Unknown runtime dependencies stay conservative. Only dependencies known to be
inactive in native parsing or confined to transport/tooling are omitted.
"""
import copy

CONTRACT = 'pdf-stage-dependencies-v2'
_TRANSPORT = {'boto3', 'botocore', 's3transfer', 'temporalio', 'pytest', 'pyright', 'pip', 'uv'}
_NATIVE_INACTIVE = {'rapidocr', 'onnxruntime', 'coloredlogs', 'humanfriendly', 'pyclipper'}
_NATIVE_ONLY = {'docling', 'docling-core', 'docling-parse', 'docling-ibm-models',
                'torch', 'torchvision', 'transformers', 'safetensors', 'tokenizers'}
_FILES = {
    'group': ('continuation.py', 'parse.py', 'execution.py', 'compatibility.py', 'supervision.py', 'warm_child.py'),
    'assembly': ('continuation.py', 'parse.py', 'execution.py', 'compatibility.py'),
    'selection': ('enrichment.py', 'processing.py', 'compatibility.py'),
    'ocr': ('ocr.py', 'enrichment.py', 'processing.py', 'execution.py', 'compatibility.py'),
    'evidence': ('relationships.py', 'relationship_method.py', 'evidence.py', 'enrichment.py', 'processing.py', 'execution.py', 'compatibility.py'),
    'finalize': ('relationships.py', 'relationship_method.py', 'evidence.py', 'enrichment.py', 'processing.py', 'compatibility.py'),
}


def parsing_method(method):
    value = copy.deepcopy(method)
    if value['format'] != 'PROTOTYPE-page-v1':
        raise ValueError('unsupported_checkpoint_format')
    ignored = set(_TRANSPORT)
    if value['options']['do_ocr'] is False:
        ignored.update(_NATIVE_INACTIVE)
        value['model_artifacts'] = {k: v for k, v in value['model_artifacts'].items()
                                    if not k.startswith('rapidocr/')}
        value['options'].pop('ocr_options', None)
        value['option_types'].pop('ocr_options', None)
    value['packages'] = {k: v for k, v in value['packages'].items()
                         if k.lower().replace('_', '-') not in ignored}
    return value


def enrichment_runtime(method, ocr):
    # Both children consume serialized JSON, not Docling models. OCR is fixed to
    # ONNX; evidence only renders regions. Unknown packages remain conservative.
    ignored = _TRANSPORT | _NATIVE_ONLY | (set() if ocr else _NATIVE_INACTIVE)
    return {'python': method['python'], 'platform': method['platform'],
            'packages': {k: v for k, v in method['packages'].items()
                         if k.lower().replace('_', '-') not in ignored},
            'model_artifacts': {k: v for k, v in method['model_artifacts'].items()
                                if ocr and k.startswith('rapidocr/')}}


def methods_match(saved, current, scoped=False):
    return parsing_method(saved) == parsing_method(current) if scoped else saved == current


def dependencies(stage, profile, producer):
    """Closed stage vocabulary; new output-affecting code belongs in this contract."""
    result = {'contract': CONTRACT, 'stage': stage,
              'producer': {name: producer[name] for name in _FILES[stage] if name in producer}}
    if stage in ('group', 'assembly'):
        result['method'] = parsing_method(profile['method'])
    elif stage == 'selection':
        result['policy'] = 'all-picture-items-v1'
    elif stage == 'ocr':
        result['method'] = enrichment_runtime(profile['method'], True)
        result['policy'] = profile.get('picture_ocr', {'render_scale': 3})
    elif stage == 'evidence':
        result['method'] = enrichment_runtime(profile['method'], False)
        result['policy'] = profile.get('content_evidence', {'version': 'typed-source-evidence-v1', 'reviews': {}})
    elif stage == 'finalize':
        result['policy'] = 'required-work-barrier-v3'
        if profile.get('content_evidence', {}).get('version') == 'typed-source-relationships-v2':
            result['policy'] = {'version': 'required-relationships-barrier-v1',
                                'evidence': profile['content_evidence']}
    return result
