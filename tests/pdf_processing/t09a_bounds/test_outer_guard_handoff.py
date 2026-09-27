import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from outer_guard_handoff import handoff_on_guard


CHILD = """import json,signal,sys,time
from pathlib import Path
signal.signal(signal.SIGINT, lambda *_: sys.exit(130))
stop=Path(sys.argv[1]);terminal=Path(sys.argv[2])
if sys.argv[3]=='self-stop':
 stop.write_text(json.dumps({'time':time.time(),'reason':'VM PSI guard breached','automatic_retry':False}))
 time.sleep(.5)
 terminal.write_text('sealed')
else:
 time.sleep(10)
"""


class OuterGuardHandoffTest(unittest.TestCase):
    def run_child(self, mode):
        root = tempfile.TemporaryDirectory()
        path = Path(root.name)
        started_at = time.time()
        process = subprocess.Popen([sys.executable, "-c", CHILD,
                                    str(path / "controller-stop.json"),
                                    str(path / "terminal"), mode])
        return root, path, process, started_at

    def test_runner_stop_gets_bounded_cleanup_without_second_signal(self):
        root, path, process, started_at = self.run_child("self-stop")
        try:
            deadline = time.monotonic() + 2
            while not (path / "controller-stop.json").exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(handoff_on_guard(process, path / "controller-stop.json", started_at),
                             "runner_cleanup")
            self.assertEqual(process.wait(timeout=2), 0)
            self.assertEqual((path / "terminal").read_text(), "sealed")
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            root.cleanup()

    def test_outer_guard_still_signals_when_runner_has_not_stopped(self):
        root, path, process, started_at = self.run_child("outer-stop")
        try:
            time.sleep(.1)
            self.assertEqual(handoff_on_guard(process, path / "controller-stop.json", started_at),
                             "outer_signalled")
            self.assertEqual(process.wait(timeout=2), 130)
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            root.cleanup()


if __name__ == "__main__":
    unittest.main()
