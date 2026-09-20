"""Real subprocess checks for the prestarted Pod Python command channel."""
import ast,importlib,json,os,sys,tempfile,time,unittest
from pathlib import Path
from pod_persistent_python import PersistentPython

class PersistentPythonTests(unittest.TestCase):
 def start(self):
  p=PersistentPython([sys.executable]);self.addCleanup(p.close);return p
 def test_repeated_requests_keep_one_process_and_program_scope_is_fresh(self):
  p=self.start();pid=p.run("import os; x=7;print(os.getpid())")
  self.assertEqual(p.run("import os;print(os.getpid())"),pid)
  self.assertEqual(p.run("print('x' in globals())"),'False\n')
 def test_remote_error_does_not_masquerade_as_output(self):
  p=self.start()
  with self.assertRaisesRegex(RuntimeError,'PermissionError'):p.run("raise PermissionError('denied')")
  self.assertEqual(p.run("print('alive')"),'alive\n')
 def test_large_snapshot_response_is_complete(self):
  p=self.start();self.assertEqual(len(p.run("print('x'*6000000)")),6000001)
 def test_timeout_closes_channel_without_retry(self):
  p=self.start();start=time.monotonic()
  with self.assertRaises(TimeoutError):p.run("import time;time.sleep(30)",timeout=.1)
  self.assertLess(time.monotonic()-start,3);self.assertIsNotNone(p.process.poll())
  with self.assertRaises(RuntimeError):p.run("print('must not retry')")
 def test_remote_exit_is_detected_and_close_reaps(self):
  p=self.start()
  with self.assertRaises(RuntimeError):p.run("import os;os._exit(0)")
  p.close();self.assertIsNotNone(p.process.poll())
 def test_owner_read_handles_atomic_publication_and_rejects_corruption(self):
  runner=importlib.import_module('sentinel.run_yolo_pod_cgroup_'+os.environ.get('Q04_RUNNER_VERSION','k'))
  from pod_durable_evidence import write_once
  tree=ast.parse(Path(runner.__file__).read_text())
  assignment=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=='owner' and 'sample_channel.run' in ast.unparse(n.value))
  expression=assignment.value.args[0].args[0]
  p=self.start()
  with tempfile.TemporaryDirectory() as directory:
   program=eval(compile(ast.Expression(expression),'<owner program>','eval'),{'EVIDENCE':directory})
   self.assertIsNone(json.loads(p.run(program))['config_sha256'])
   root=Path(directory)
   write_once(root/'supervisor-ownership.json',{'pid':12,'start_ticks':34})
   self.assertIsNone(json.loads(p.run(program))['config_sha256'])
   write_once(root/'ownership.json',{'config_sha256':'bound'})
   self.assertEqual(json.loads(p.run(program)),{'pid':12,'start_ticks':34,'config_sha256':'bound'})
   (root/'ownership.json').write_text('')
   with self.assertRaisesRegex(RuntimeError,'JSONDecodeError'):p.run(program)
 def test_controller_live_loop_uses_prestarted_lanes_without_exec_births(self):
  runner=importlib.import_module('sentinel.run_yolo_pod_cgroup_'+os.environ.get('Q04_RUNNER_VERSION','k'))
  tree=ast.parse(Path(runner.__file__).read_text())
  function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute_window')
  loop=next(n for n in ast.walk(function) if isinstance(n,ast.While) and ast.unparse(n.test)=='workload.poll() is None')
  calls=[ast.unparse(n.func) for n in ast.walk(loop) if isinstance(n,ast.Call)]
  self.assertNotIn('kube.exec_python',calls);self.assertNotIn('kube.run',calls)
  self.assertIn('sample_channel.run',calls);self.assertIn('evidence_channel.run',calls)
  source=ast.unparse(function)
  self.assertLess(source.index('evidence_channel = PersistentPython'),source.index('workload = subprocess.Popen'))
if __name__=='__main__':unittest.main()
