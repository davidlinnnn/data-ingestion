from pathlib import Path
source=Path(__file__).with_name('runner.py').read_text()
for old,new in {'A6':'A12','a6':'a12','runner = configure()':"runner = configure(topology_name='topology_a12', evidence_name='pod_remote_evidence_a12', identity='t09b-calibration-20260930-a12', record_name='runtime-a12', preflight_name='pod_preflight_a12.py', workload_name='pod_workload_a12.py')"}.items(): source=source.replace(old,new)
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
