from pathlib import Path
source = Path(__file__).with_name('controller.py').read_text()
for old, new in {'A6':'A11','a6':'a11','from qualify_baseline import qualify':'from qualify_a11 import qualify',"RUNNER = HERE / 'runner.py'":"RUNNER = HERE / 'runner_a11.py'"}.items(): source = source.replace(old,new)
exec(compile(source,__file__,'exec'),globals())
