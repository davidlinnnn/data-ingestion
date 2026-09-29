from pathlib import Path
source=Path(__file__).with_name('candidate_controller.py').read_text()
for old,new in {'B2':'B5','b2':'b5','from qualify_candidate import qualify':'from qualify_candidate_b5 import qualify',"RUNNER = HERE / 'candidate_runner.py'":"RUNNER = HERE / 'candidate_runner_b5.py'"}.items(): source=source.replace(old,new)
exec(compile(source,__file__,'exec'),globals())
