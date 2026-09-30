from pathlib import Path
source = Path(__file__).with_name('pod_preflight.py').read_text()
for old, new in {'A6': 'PC1', 'a6': 'pc1', 'baseline_window': 'cold_window', 'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json': 'tests/pdf_processing/t09b/PC1-RUNTIME-INTEGRATION-MANIFEST.json'}.items(): source = source.replace(old, new)
source = source.replace('for old, new in replacements.items():', 'replacements.update({\'from candidate.warm_pod_window_r import validate_contract, validate_scope\': \'from candidate.warm_pod_window_r import validate_contract\\n    from cold_window import validate_scope\', \'"sequence": ["06", "07", "08", "native", "06"]\': \'"sequence": ["07", "08", "native"]\', \'"group_requests": 29\': \'"group_requests": 17\'})\nfor old, new in replacements.items():')
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
