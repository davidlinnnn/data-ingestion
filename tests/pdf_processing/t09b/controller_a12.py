from pathlib import Path
source = Path(__file__).with_name('controller.py').read_text()
for old, new in {'A6':'A12','a6':'a12','from qualify_baseline import qualify':'from qualify_a12 import qualify',"RUNNER = HERE / 'runner.py'":"RUNNER = HERE / 'runner_a12.py'"}.items(): source = source.replace(old,new)
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
