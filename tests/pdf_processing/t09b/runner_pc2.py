from pathlib import Path
source=Path(__file__).with_name('runner.py').read_text()
for old,new in {'A6':'PC2','a6':'pc2','runner = configure()':"runner = configure(topology_name='topology_pc2', evidence_name='pod_remote_evidence_pc2', identity='t09b-calibration-20260930-pc2', record_name='runtime-pc2', preflight_name='pod_preflight_pc2.py', workload_name='pod_workload_pc2.py')"}.items(): source=source.replace(old,new)
source = source.replace('20260929', '20260930')
source = source.replace("if __name__ == '__main__':", "\n_normal_scope = runner.authorization_scope\ndef cold_scope():\n    return {**_normal_scope(), 'sequence': ['native', '07', '08'], 'group_requests':17, 'expected_worker_generations':3, 'expected_parser_generations':3}\nrunner.authorization_scope = runner.ah.authorization_scope = base.authorization_scope = cold_scope\n\n" + "if __name__ == '__main__':")
exec(compile(source,__file__,'exec'),globals())
