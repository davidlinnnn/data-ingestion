"""Exercise the actual runner lifecycle with local service doubles."""
import asyncio
import importlib.util
import json
from pathlib import Path
import signal
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from storage_ledger import reconcile


class StartupTest(unittest.TestCase):
    def test_shared_store_profiles_start_measure_and_clean_up(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'source'; source.mkdir()
            (source/'__init__.py').write_text('')
            config = dict(producer={'__init__.py': 'source'}, temporal='local',
                          endpoint='local', bucket='test', prefix='fresh/',
                          parser_budgets={}, run_id='local', model_cache='local',
                          limits={}, profiles={'a': {}, 'b': {}},
                          queues={'a': 'a', 'b': 'b'}, drain_seconds=1)
            config_path = root/'config.json'
            config_path.write_text(json.dumps(config))
            calls, exits, callbacks = [], [], {}

            class S3:
                def put_object(self, **args):
                    calls.append(args['Key'])
                    return {'ResponseMetadata': {'RetryAttempts': 0}}

            class Parser:
                def __init__(self, **args):
                    self.observation, self.count, self.process = {}, 0, None

            class Processing:
                def __init__(self, store, *args, **kwargs):
                    self.store = store

                async def run(self, value):
                    return await asyncio.to_thread(self.store.client.put_object,
                                                   Key=value, Body=b'x')

            class Client:
                @staticmethod
                async def connect(address):
                    return object()

            class Worker:
                def __init__(self, client, **kwargs):
                    self.options = kwargs

                async def __aenter__(self):
                    options = self.options
                    class Next:
                        async def execute_activity(self, value):
                            return await options['activities'][0](value)
                    wrapped = options['interceptors'][0].intercept_activity(Next())
                    info = SimpleNamespace(workflow_id='w', workflow_run_id='run',
                                           activity_id=options['task_queue'], attempt=1)
                    with patch('worker_measurement.activity.info', return_value=info):
                        await wrapped.execute_activity(options['task_queue'])
                    await asyncio.sleep(0)
                    if options['task_queue'] == 'b':
                        callbacks[signal.SIGTERM]()
                    return self

                async def __aexit__(self, *args):
                    exits.append(self.options['task_queue'])

            async def stop_children(parser):
                parser.process = None

            def require(condition, message):
                if not condition:
                    raise ValueError(message)

            modules = {
                'consumer': SimpleNamespace(require=require, sha=lambda data: 'source'),
                'telemetry': SimpleNamespace(sample=lambda: {'time': __import__('time').time()}),
                'psutil': SimpleNamespace(Process=lambda: SimpleNamespace(create_time=lambda: 1)),
                'boto3': SimpleNamespace(client=lambda *args, **kwargs: S3()),
                'pdf_processing': SimpleNamespace(__file__=str(source/'__init__.py')),
                'pdf_processing.object_store': SimpleNamespace(Store=lambda client, *args: SimpleNamespace(client=client, publish=lambda *a: None)),
                'pdf_processing.processing': SimpleNamespace(Processing=Processing),
                'pdf_processing.supervision': SimpleNamespace(WarmParser=Parser),
                'pdf_processing.execution': SimpleNamespace(stop_owned_children=stop_children),
            }

            async def run():
                with patch.object(asyncio.get_running_loop(), 'add_signal_handler',
                                  side_effect=lambda sig, callback: callbacks.update({sig: callback})):
                    await runner.run(config_path, root/'out', 1)

            with patch.dict(sys.modules, modules), \
                 patch('temporalio.client.Client', Client), patch('temporalio.worker.Worker', Worker):
                spec = importlib.util.spec_from_file_location('t09b_test_runner', Path(__file__).with_name('worker.py'))
                runner = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(runner)
                asyncio.run(run())
            self.assertEqual(calls, ['a', 'b'])
            self.assertEqual(exits, ['b', 'a'])
            report = reconcile(root/'out/storage.jsonl')
            self.assertTrue(report['complete'])
            self.assertEqual({row['activity_id'] for row in report['events']}, {'a', 'b'})
            self.assertTrue(json.loads((root/'out/stopped.json').read_text())['scratch_absent'])
            self.assertTrue((root/'out/ready.json').exists())
