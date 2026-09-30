from pathlib import Path
source = Path(__file__).with_name('pod_preflight.py').read_text()
for old, new in {'A6': 'RA2', 'a6': 'ra2', 'baseline_window': 'recovery_window', 'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json': 'tests/pdf_processing/t09b/RA2-RUNTIME-INTEGRATION-MANIFEST.json'}.items(): source = source.replace(old, new)
source = source.replace('for old, new in replacements.items():', 'replacements.update({\'from candidate.warm_pod_window_r import validate_contract, validate_scope\': \'from candidate.warm_pod_window_r import validate_contract\\n    from recovery_window import validate_scope\', \'"sequence": ["06", "07", "08", "native", "06"]\': \'"sequence": ["native"]\', \'"group_requests": 29\': \'"group_requests": 11\'})\nfor old, new in replacements.items():')
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
