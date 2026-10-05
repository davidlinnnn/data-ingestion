from pathlib import Path
source = Path(__file__).with_name('runner.py').read_text()
for old, new in {'A6': 'RB1', 'a6': 'rb1', 'runner = configure()': "runner = configure(topology_name='topology_rb1', evidence_name='pod_remote_evidence_rb1', identity='t09b-calibration-20260930-rb1', record_name='runtime-rb1', preflight_name='pod_preflight_rb1.py', workload_name='pod_workload_rb1.py')"}.items(): source = source.replace(old, new)
source = source.replace("if __name__ == '__main__':", "\n_normal_scope = runner.authorization_scope\ndef recovery_scope():\n    return {**_normal_scope(), 'sequence': ['native'], 'modes': ['drain'],\n            'group_requests': 6, 'expected_worker_generations': 2,\n            'injection': 'stop owned worker process after ten registered pages during next active group'}\nrunner.authorization_scope = runner.ah.authorization_scope = base.authorization_scope = recovery_scope\n\n" + "if __name__ == '__main__':")
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
