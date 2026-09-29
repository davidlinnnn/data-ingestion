from pathlib import Path
source=Path(__file__).with_name('runner.py').read_text()
for old,new in {'A6':'A11','a6':'a11','runner = configure()':"runner = configure(topology_name='topology_a11', evidence_name='pod_remote_evidence_a11', identity='t09b-calibration-20260929-a11', record_name='runtime-a11', preflight_name='pod_preflight_a11.py', workload_name='pod_workload_a11.py')"}.items(): source=source.replace(old,new)
exec(compile(source,__file__,'exec'),globals())
