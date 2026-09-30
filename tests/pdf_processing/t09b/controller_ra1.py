from pathlib import Path
source = Path(__file__).with_name('controller.py').read_text()
for old, new in {'A6': 'RA1', 'a6': 'ra1', 'from qualify_baseline import qualify': 'from qualify_recovery import qualify', "RUNNER = HERE / 'runner.py'": "RUNNER = HERE / 'runner_ra1.py'"}.items(): source = source.replace(old, new)
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
