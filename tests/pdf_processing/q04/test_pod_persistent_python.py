"""Real subprocess checks for the prestarted Pod Python command channel."""
import ast,sys,time,unittest
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
 def test_controller_live_loop_uses_prestarted_lanes_without_exec_births(self):
  from sentinel import run_yolo_pod_cgroup_k as runner
  tree=ast.parse(Path(runner.__file__).read_text())
  function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute_window')
  loop=next(n for n in ast.walk(function) if isinstance(n,ast.While) and ast.unparse(n.test)=='workload.poll() is None')
  calls=[ast.unparse(n.func) for n in ast.walk(loop) if isinstance(n,ast.Call)]
  self.assertNotIn('kube.exec_python',calls);self.assertNotIn('kube.run',calls)
  self.assertIn('sample_channel.run',calls);self.assertIn('evidence_channel.run',calls)
  source=ast.unparse(function)
  self.assertLess(source.index('evidence_channel = PersistentPython'),source.index('workload = subprocess.Popen'))
if __name__=='__main__':unittest.main()
