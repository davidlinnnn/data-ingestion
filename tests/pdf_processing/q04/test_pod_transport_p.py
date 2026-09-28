"""Real snapshot/mirror and controller failure-export regressions, no cluster."""
import ast
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pod_durable_evidence import seal

VERSION = os.environ.get('Q04_TRANSPORT_VERSION', 'p')
remote = importlib.import_module('pod_remote_evidence_' + VERSION)
runner = importlib.import_module('sentinel.run_yolo_pod_cgroup_' + VERSION)


class TransportTests(unittest.TestCase):
    def test_entrypoint_policy_survives_live_and_sealed_transport(self):
        import pod_workload_p as workload
        with patch.object(workload, 'parser') as parser, \
             patch.object(workload, 'disable_thp', return_value={'thp_disabled':1}), \
             patch.object(workload, 'run', return_value=0):
            parser.return_value.parse_args.return_value = SimpleNamespace(control=self.root)
            workload.main([])
        self.pull()
        self.stop_and_seal()
        self.pull(received_at=2)
        self.assertEqual(self.mirror.finalize(require_success=False)['status'], 'FAILURE_EVIDENCE_RETAINED')
        self.mirror.verify_archive_fingerprint(json.loads(self.execute(runner.archive_fingerprint_program())))
        self.assertEqual(json.loads((self.mirror.root / 'workload-memory-policy.json').read_text()), {'thp_disabled':1})

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.events = []
        self.root = self.base / 'remote'
        (self.root / 'state').mkdir(parents=True)
        self.config = self.root / 'state/config.json'
        self.config.write_text('{}')
        self.identity = remote.PodEvidenceIdentity('pod', 'container', 42, 99, remote.sha256(b'{}'))
        self.write('transport-identity.json', self.identity.__dict__)
        self.write('supervisor-ownership.json', {'pid':42, 'start_ticks':99})
        self.write('ownership.json', {'config_sha256':self.identity.config_sha256})
        self.volume = {'pvc_uid':'claim-k', 'pv_uid':'pv-j'}
        self.write('evidence-volume-identity.json', self.volume)
        self.proc = self.base / 'proc/42'
        self.proc.mkdir(parents=True)
        (self.proc / 'stat').write_text('42 (supervisor) ' + ' '.join(['S'] + ['0'] * 18 + ['99']))
        self.out = self.base / 'controller'
        self.out.mkdir()
        self.mirror = remote.IncrementalEvidenceMirror(self.out / 'evidence', self.identity)

    def write(self, name, value):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value) + '\n')
        return p

    def execute(self, program):
        program = program.replace(runner.EVIDENCE, str(self.root)).replace("Path('/proc')", 'Path(' + repr(str(self.base / 'proc')) + ')')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(program, {})
        return output.getvalue()

    def pull(self, mirror=None, received_at=1):
        mirror = mirror or self.mirror
        return mirror.ingest(json.loads(self.execute(mirror.request_program(str(self.root)))), received_at=received_at)

    def stop_and_seal(self, success=False):
        shutil.rmtree(self.proc)
        self.write('workload-exit.json', {'returncode':0 if success else 1, 'automatic_retry':False})
        self.write('cleanup-complete.json', {'worker_absent':True, 'owned_children_absent':True, 'scratch_absent':True})
        seal(self.root, volume_identity=self.volume, workload_succeeded=success, cleanup_complete=True)

    def test_normal_scratch_lifecycle_never_enters_durable_mirror(self):
        self.pull()
        name = 'state/' + runner.PHASE + '/worker-1/scratch/07/activity-owned/process.log'
        p = self.write(name, {'parser':'running'})
        self.pull(received_at=2)
        shutil.rmtree(p.parents[2])
        self.pull(received_at=3)
        self.assertNotIn(name, self.mirror.remote_sizes)
        self.stop_and_seal()
        self.pull(received_at=4)
        self.assertEqual(self.mirror.finalize(require_success=False)['status'], 'FAILURE_EVIDENCE_RETAINED')
        self.mirror.verify_archive_fingerprint(json.loads(self.execute(runner.archive_fingerprint_program())))

    def test_durable_disappearance_and_truncation_still_fail(self):
        for operation in ('delete','truncate'):
            with self.subTest(operation=operation):
                target = self.write('state/' + runner.PHASE + '/worker-1.log', {'durable':'trace'})
                mirror = remote.IncrementalEvidenceMirror(self.out / operation, self.identity)
                self.pull(mirror)
                target.unlink() if operation == 'delete' else target.write_text('')
                with self.assertRaisesRegex(ValueError, 'disappeared|offset drift|shrank'):
                    self.pull(mirror,received_at=2)

    def test_live_gap_still_fails(self):
        self.pull()
        with self.assertRaisesRegex(ValueError, 'transport gap exceeded'):
            self.pull(received_at=12)

    def failure_export(self, full_cleanup=False, fail_channel_close=False):
        tree = ast.parse(Path(runner.__file__).read_text())
        function = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute_window')
        block = next(n for n in ast.walk(function) if isinstance(n,ast.Try)
                     and n.body and isinstance(n.body[0],ast.Assign)
                     and ast.unparse(n.body[0].targets[0])=='pod'
                     and 'failure terminal cleanup proof' in ast.unparse(n))
        namespace = {**vars(runner), 'OUT':self.out, 'mirror':self.mirror,
                     'pod_identity':{'pod_name':'pod'}, 'recovery_deadline':time.time()+60,
                     'cleanup':{}, 'terminal_stop_proven':False, 'evidence_captured':False,
                     'evidence_volume':self.volume, 'primary_error':ValueError('live transport failure'),
                     'kube':SimpleNamespace(base=[],exec_python=lambda pod,program,**kwargs:self.execute(program))}
        if full_cleanup:
            outer = next(n for n in function.body if isinstance(n, ast.Try) and n.finalbody)
            block = ast.If(test=ast.Constant(value=True), body=outer.finalbody, orelse=[])
            ast.fix_missing_locations(block)
            owned = [{"kind":"PersistentVolumeClaim", "name":"evidence", "uid":"claim-k"},
                     {"kind":"ConfigMap", "name":"harness", "uid":"cm-k"},
                     {"kind":"Deployment", "name":"worker", "uid":"dep-k"}]
            def delete_owned(*args, **kwargs):
                self.events.append('delete')
                return {"deleted":list(reversed(owned[1:])),"errors":{}}
            def close_sample():
                self.events.append('close-sample')
                if fail_channel_close:
                    raise TimeoutError('injected channel close failure')
            def close_evidence():
                self.events.append('close-evidence')
            namespace.update(
                capacity={"ends_at":time.time()+300,"expected_vm_oom_kill":0},
                vm_stream=None, workload=None, transport_future=None, transport_pool=None,
                sample_channel=SimpleNamespace(close=close_sample),
                evidence_channel=SimpleNamespace(close=close_evidence),
                deployment={"metadata":{"uid":"dep-k"}}, cleanup_identity=None,
                supervisor_identity_published=True, owned_objects=owned,
                cleanup_deployment_and_pod=lambda *a,**k:{"old_runtime_absent":True,"emptydirs_absent":True},
                delete_owned_objects=delete_owned,
                verify_retained_evidence_claim=lambda *a,**k:{"pvc_uid":"claim-k","retained":True},
                verify_outer_identity=lambda *a,**k:None, t09a_health=lambda *a,**k:None,
                node_vm_sample=lambda **k:{"vm_oom_kill":0,"psi_full_avg10":0})
            original = namespace['kube'].exec_python
            namespace['kube'].exec_python = lambda pod,program,**k: json.dumps({
                "available":7*1024**3,"psi_full_avg10":0,"vm_oom_kill":0,
                "memory_events":{},"memory_current":1000,"evidence_used_bytes":1000,
                "evidence_free_bytes":1024**3,"evidence_filesystem_free_bytes":1024**3,
            }) if program == runner.sample_program() else original(pod,program,**k)
        def export(command, **kwargs):
            self.events.append('export')
            with tarfile.open(fileobj=kwargs['stdout'],mode='w') as archive:
                archive.add(self.root,arcname='.')
            return SimpleNamespace(returncode=0)
        with patch.object(runner.subprocess,'run',side_effect=export):
            exec(compile(ast.Module(body=[block],type_ignores=[]), str(runner.__file__), 'exec'), namespace)
        return namespace

    def test_stopped_sealed_export_is_independent_of_failed_live_mirror(self):
        self.pull()
        self.stop_and_seal()
        state = self.failure_export()
        self.assertTrue(state['evidence_captured'], state['cleanup'])
        self.assertEqual(self.mirror.last_received_at,1)
        self.assertFalse(self.mirror.finalized)
        self.assertTrue((self.out/'pod-control-failure-evidence.tar').is_file())
        self.assertEqual(state['cleanup']['live_qualification_passed'],False)
        self.assertTrue(state['cleanup']['forensic_export_complete'])

    def test_channel_close_failure_does_not_skip_remaining_cleanup(self):
        self.pull(); self.stop_and_seal()
        state = self.failure_export(full_cleanup=True, fail_channel_close=True)
        self.assertIn('close-evidence', self.events)
        self.assertIn('delete', self.events)
        self.assertFalse(state['cleanup']['persistent_channels_closed'])
        self.assertIn('sample', state['cleanup']['persistent_channel_close_errors'])
        self.assertTrue((self.out/'outer-cleanup.json').is_file())
        self.assertIn('live transport failure', state['cleanup']['primary_error'])

    def test_complete_failed_controller_cleanup_exports_before_owned_deletion(self):
        self.pull()
        self.stop_and_seal()
        state = self.failure_export(full_cleanup=True)
        cleanup = json.loads((self.out/'outer-cleanup.json').read_text())
        self.assertTrue(state['evidence_captured'],cleanup)
        self.assertIn('live transport failure',cleanup['primary_error'])
        self.assertFalse(cleanup['live_qualification_passed'])
        self.assertTrue(cleanup['forensic_export_complete'])
        self.assertTrue(cleanup['terminal_cgroup_oom_proof'])
        self.assertTrue(cleanup['owned_objects_deleted_with_uid_preconditions'])
        self.assertTrue(cleanup['retained_evidence_claim']['retained'])
        self.assertEqual(cleanup['disposition'],'CLEANED_WITH_WORKLOAD_EVIDENCE_RETAINED')
        self.assertEqual(self.events,['export','close-sample','close-evidence','delete'])
        self.assertFalse(self.mirror.finalized)

    def test_failed_seal_readback_never_counts_as_recovered(self):
        self.pull()
        self.stop_and_seal()
        self.config.write_text('{"tampered":true}')
        state = self.failure_export(full_cleanup=True)
        self.assertFalse(state['evidence_captured'])
        self.assertIn('identity changed',state['cleanup']['evidence_capture_error'])
        self.assertTrue(state['cleanup']['owned_objects_deleted_with_uid_preconditions'])
        self.assertTrue(state['cleanup']['retained_evidence_claim']['retained'])

    def test_forensic_export_requires_every_sealed_chunk(self):
        self.pull()
        self.write('state/'+runner.PHASE+'/worker-1.log', 'x'*(4*1024*1024+100))
        self.stop_and_seal()
        state = self.failure_export()
        self.assertTrue(state['evidence_captured'],state['cleanup'])
        ledger = json.loads((self.out/'forensic-transport-ledger.json').read_text())
        self.assertEqual(len(ledger['records']),2)
        self.assertFalse(ledger['live_qualification_passed'])

    def test_non_worker_scratch_named_evidence_remains_durable(self):
        name='state/'+runner.PHASE+'/worker-not-a-generation/scratch/record.json'
        path=self.write(name,{'durable':True})
        self.pull()
        path.unlink()
        with self.assertRaisesRegex(ValueError,'remote evidence disappeared'):
            self.pull(received_at=2)

    def test_terminal_inventory_digest_mismatch_is_rejected(self):
        self.stop_and_seal()
        path=self.root/'durable-terminal-manifest.json'
        value=json.loads(path.read_text());value['inventory_sha256']='0'*64
        path.write_text(json.dumps(value))
        self.pull()
        with self.assertRaisesRegex(ValueError,'inventory digest mismatch'):
            self.mirror.finalize(require_success=False)

    def test_success_finalization_requires_and_accepts_complete_matrix_inventory(self):
        for name in remote.FINAL_REQUIRED - {'durable-terminal-manifest.json'}:
            if not (self.root/name).exists():
                self.write(name,{})
        self.write('state/'+runner.PHASE+'-measurement/measurement-contract.json',{
            'workload_succeeded':True,'qualification_complete':True,'cgroup_resource_complete':True})
        self.write('state/'+runner.PHASE+'/worker-1/stopped.json',{'parser_absent':True,'scratch_absent':True})
        self.write('state/'+runner.PHASE+'/worker-1.log',{'trace':'complete'})
        self.stop_and_seal(success=True)
        self.pull()
        self.assertEqual(self.mirror.finalize(require_success=True)['status'],'PASS')


if __name__ == '__main__':
    unittest.main()
