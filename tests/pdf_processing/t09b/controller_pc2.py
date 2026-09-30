from pathlib import Path
source = Path(__file__).with_name('controller.py').read_text()
for old, new in {'A6':'PC2','a6':'pc2',"RUNNER = HERE / 'runner.py'":"RUNNER = HERE / 'runner_pc2.py'"}.items(): source = source.replace(old,new)
source = source.replace('20260929', '20260930')
source = source.replace('from qualify_baseline import qualify', 'from qualify_cold_pc2 import qualify')
exec(compile(source,__file__,'exec'),globals())
