from pathlib import Path
source = Path(__file__).with_name('controller.py').read_text()
for old, new in {'A6': 'RB1', 'a6': 'rb1', 'from qualify_baseline import qualify': 'from qualify_recovery import qualify', "RUNNER = HERE / 'runner.py'": "RUNNER = HERE / 'runner_rb1.py'"}.items(): source = source.replace(old, new)
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
