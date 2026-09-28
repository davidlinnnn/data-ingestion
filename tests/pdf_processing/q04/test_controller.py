"""Local orchestration at external workflow/process transports, no live services."""
import asyncio
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

from consumer import Consumer
from host import Host
from q04_runtime import Run
import test_consumer


class WorkflowTransport:
    def __init__(self, request, result, intent_path=None):
        self.request, self.output = request, result
        self.intent_path = intent_path

    async def start_workflow(self, method, submission, **kwargs):
        if submission['request'] != self.request:
            raise ValueError('transport received a reinterpreted accepted request')
        if self.intent_path is not None:
            intent = json.loads(self.intent_path.read_text())
            if intent['workflow_id'] != kwargs['id']:
                raise ValueError('workflow ownership was not registered before submit')
        return self

    async def result(self):
        await asyncio.sleep(.01)
        return self.output

    async def query(self, method):
        return {'registered_pages':0,'steps':[]}

    async def fetch_history(self):
        return SimpleNamespace(to_json=lambda:'{"local_transport":true}')


class Controller(unittest.IsolatedAsyncioTestCase):
    async def test_replay_drives_actual_checked_consumer_and_retains_history(self):
        with tempfile.TemporaryDirectory(prefix='q04-controller-') as tmp:
            root=Path(tmp)
            helper=test_consumer.DurableConsumer()
            store,result,request,profile,fixture=helper.fixture(root)
            previous_dir=root/'fresh'
            accepted=Consumer(store,previous_dir).verify(result,request,profile,fixture,root/'oracles')
            previous={'request':request,'profile':profile,'result':result,'accepted':accepted,'directory':str(previous_dir)}
            for step in result['steps']:step['reused']=True
            result.update(pages=1,selected_components=0,registered_components=0)
            window={'owner':'local-test','approval_reference':'local transport only','starts_at':time.time()-10,'ends_at':time.time()+300,
                'admission_seconds':1,'admission_available_bytes':50,'min_available_bytes':50,'max_cgroup_bytes':30,
                'max_full_psi':0,'max_sample_gap_seconds':2,'max_replacement_seconds':5,'cleanup_seconds':120}
            config={'profiles':{'native':profile},'queues':{'native':'local'},'producer':{},'bundle':str(root),'state':str(root),
                'run_id':'q04-local','workflow_queue':'local','window':window,'trial_seconds':10}
            config_path=root/'config.json';config_path.write_text(json.dumps(config))
            host=SimpleNamespace(current=root,generation=1,config_path=config_path,pod=None,process=SimpleNamespace(poll=lambda:None))
            running=True
            async def telemetry():
                with (root/'samples.jsonl').open('w',buffering=1) as stream:
                    while running:
                        stream.write(json.dumps({'time':time.time(),'available':100,'memory_current':20,'vm_oom_kill':0,
                            'memory_events':{'oom_kill':0},'psi_full_avg10':0})+'\n')
                        await asyncio.sleep(.05)
            observer=asyncio.create_task(telemetry());await asyncio.sleep(.01)
            run=Run(config,{'fixtures':[fixture]},root,
                    WorkflowTransport(request,result,root/'exact/workflow-intent.json'),store,host)
            try:
                outcome=await run.trial('native','replay','exact',previous)
                self.assertTrue(outcome['verified'])
                self.assertTrue((root/'exact/history.json').exists())
                intent=json.loads((root/'exact/workflow-intent.json').read_text())
                self.assertEqual(intent['phase'],root.name)
                self.assertEqual(intent['trial'],'exact')
            finally:
                running=False
                await observer

    async def test_original_failure_survives_all_cleanup_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            called = []
            async def stop():
                self.assertEqual(json.loads((root/'failure.json').read_text())['reason'], 'original injection')
                called.append('stop')
                raise RuntimeError('forced cleanup')
            async def history():
                called.append('history')
                raise RuntimeError('history transport')
            async def cancel(handle):
                called.append('cancel')
                raise RuntimeError('cancel transport')
            def publication(request):
                called.append('publication')
                raise RuntimeError('scan transport')
            run = Run({}, {}, root, None, None, SimpleNamespace(stop=stop))
            run.cancel_owned = cancel
            run.no_complete = publication
            handle = SimpleNamespace(fetch_history=history)
            run.active = handle
            task = asyncio.create_task(asyncio.sleep(60))
            outcomes = await run.retain_failure(root, ValueError('original injection'), {'kind':'test'}, handle, task, {}, True)
            self.assertEqual(called, ['cancel', 'stop', 'publication', 'history'])
            self.assertTrue(task.cancelled())
            self.assertIs(run.active, handle)  # outer cleanup can retry an unconfirmed cancellation
            self.assertEqual([k for k,v in outcomes.items() if not v['ok']], ['cancel','worker-stop','publication','history'])
            self.assertEqual(json.loads((root/'failure.json').read_text())['type'], 'ValueError')
            self.assertEqual(json.loads((root/'cleanup.json').read_text()), outcomes)

    async def test_stale_telemetry_and_changed_worker_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'samples.jsonl').write_text(json.dumps({'time':time.time()-20})+'\n')
            window={'owner':'local-test','approval_reference':'local only','starts_at':time.time()-1,'ends_at':time.time()+300,
                'admission_seconds':1,'admission_available_bytes':50,'min_available_bytes':50,'max_cgroup_bytes':30,
                'max_full_psi':0,'max_sample_gap_seconds':2,'max_replacement_seconds':5,'cleanup_seconds':120}
            host=SimpleNamespace(current=root,process=SimpleNamespace(poll=lambda:None))
            run=Run({'window':window},{},root,None,None,host)
            with self.assertRaisesRegex(ValueError,'telemetry lost'):await run.guard()
            host.process=SimpleNamespace(poll=lambda:1)
            with self.assertRaisesRegex(ValueError,'worker exited'):await run.guard()


class OwnedProcesses(unittest.TestCase):
    def test_force_cleanup_targets_only_owned_process_tree(self):
        import os
        import psutil
        with tempfile.TemporaryDirectory(prefix='q04-process-') as tmp:
            root=Path(tmp)
            child_file=root/'child.pid'
            script='import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(60)'
            owned=subprocess.Popen([sys.executable,'-c',script,str(child_file),'q04/worker.py'],start_new_session=True)
            unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
            try:
                deadline=time.monotonic()+5
                while not child_file.exists():
                    self.assertLess(time.monotonic(),deadline)
                    time.sleep(.02)
                (root/'ownership.json').write_text(json.dumps({'pid':owned.pid,'created':psutil.Process(owned.pid).create_time()}))
                host=Host(root/'config.json',root,{'python':sys.executable})
                host.force_stop()
                owned.wait(timeout=5)
                self.assertIsNone(unrelated.poll())
                child_pid=int(child_file.read_text())
                self.assertTrue(not psutil.pid_exists(child_pid) or psutil.Process(child_pid).status()==psutil.STATUS_ZOMBIE)
                self.assertTrue((root/'forced-cleanup.json').exists())
            finally:
                for process in (owned,unrelated):
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait(timeout=5)

class AdmissionAndPublication(unittest.TestCase):
    def test_cli_requires_explicit_capacity_before_reading_inputs(self):
        command=[sys.executable,str(Path(__file__).with_name('q04_runtime.py')),
            '--phase','matrix','--bundle','/nonexistent/q04','--state','/nonexistent/q04-state','--capacity','/nonexistent/window']
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('new capacity approval',result.stderr)
        self.assertNotIn('Traceback',result.stderr)

    def test_failed_publication_scan_cannot_miss_later_pages(self):
        from pdf_processing.object_store import Store
        from pdf_processing.processing import encoded
        from consumer import sha
        from test_publication import MemoryS3
        class PaginatedS3(MemoryS3):
            def get_paginator(self, name):
                return SimpleNamespace(paginate=lambda **kwargs:pages)
        client=PaginatedS3();store=Store(client,'test','q04-local')
        request={'request_id':'failed-request'}
        store.publish('unrelated',{'note.json':b'{}'})
        store.publish('forbidden-complete',{'processing-result.json':encoded({'plan':'pdf-plan-v1:'+sha(encoded(request['request_id']))})})
        pages=[{'Contents':[{'Key':store.registry_key('unrelated')}]},
               {'Contents':[{'Key':store.registry_key('forbidden-complete')}]}]
        run=Run({}, {},Path('/unused'),None,store,None)
        with self.assertRaisesRegex(ValueError,'failed work left a complete registration'):
            run.no_complete(request)
