"""Regression for the original cross-document request-20 parser contract."""

import asyncio
import json
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from pdf_processing.execution import Execution
from pdf_processing.supervision import WarmParser
from pdf_processing import warm_child


CHILD = r'''import json,sys
for line in sys.stdin:
    envelope=json.loads(line)
    for kind in ('ready','done'):
        print(json.dumps({'protocol':'pdf-warm-v1',
                          'request_id':envelope['request_id'],
                          'kind':kind,'method':{},'memory':{}}),flush=True)
'''

CANCELLABLE_CHILD = r'''import json,sys,time
for line in sys.stdin:
    envelope=json.loads(line)
    request_id=envelope['request_id']
    request=envelope['request']
    print(json.dumps({'protocol':'pdf-warm-v1','request_id':request_id,
                      'kind':'ready','method':{}}),flush=True)
    if request['mode'] == 'restore':
        time.sleep(60)
    else:
        print(json.dumps({'protocol':'pdf-warm-v1','request_id':request_id,
                          'kind':'done','memory':{}}),flush=True)
'''


class WarmContinuityTest(unittest.IsolatedAsyncioTestCase):
    async def test_restore_preserves_twenty_capture_request_lifetime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child.py"
            child.write_text(CHILD)
            parser = WarmParser(command=[sys.executable, str(child)], max_requests=20)
            execution = Execution(None, None, root, child_runner=parser)
            captures = []
            fresh_calls = []

            async def no_inference(_module, request, _out):
                fresh_calls.append(request["mode"])

            execution.fresh_child = no_inference
            try:
                for group_count in (6, 3, 3, 11, 6):
                    for _ in range(group_count):
                        await execution.child(
                            "pdf_processing.parse",
                            {"mode": "capture", "expected_method": {}},
                            root,
                        )
                        captures.append(dict(execution.observation["parser"]))
                    await execution.child(
                        "pdf_processing.parse",
                        {"mode": "restore", "expected_method": {}},
                        root,
                    )
            finally:
                await parser.close()

        self.assertEqual(len(captures), 29)
        self.assertEqual(fresh_calls, [])
        self.assertEqual(len({row["pid"] for row in captures[:20]}), 1)
        self.assertEqual(len({row["pid"] for row in captures[20:]}), 1)
        self.assertNotEqual(captures[19]["pid"], captures[20]["pid"])
        self.assertEqual([row["restarts"] for row in captures], [1] * 20 + [2] * 9)
        self.assertEqual([row["recycles"] for row in captures], [0] * 19 + [1] * 10)

    def test_restore_checkpoint_assertion_remains_nonretryable_integrity_failure(self):
        request = {
            "version": 1,
            "request_id": "restore-corrupt",
            "request": {
                "mode": "restore",
                "pdf": "/input.pdf",
                "out": "/output",
                "model_cache": "/models",
                "checkpoint": "/corrupt-checkpoint",
            },
        }
        capture = {**request, "request_id": "capture", "request": {**request["request"], "mode": "capture"}}
        for first, second, category, code in (
            (capture, request, "integrity", "checkpoint_validation_failed"),
            (request, capture, "parser", "parser_execution_failed"),
        ):
            with self.subTest(second=second["request_id"]):
                stdin = io.StringIO(json.dumps(first) + "\n" + json.dumps(second) + "\n")
                stdout = io.StringIO()
                def fail_second(active, receive, _notify):
                    self.assertEqual(active.mode, first["request"]["mode"])
                    self.assertEqual(receive().mode, second["request"]["mode"])
                    raise AssertionError("corrupt")
                with (
                    mock.patch.object(sys, "stdin", stdin),
                    mock.patch.object(sys, "stdout", stdout),
                    mock.patch.object(warm_child, "execute", side_effect=fail_second),
                    self.assertRaisesRegex(SystemExit, "1"),
                ):
                    warm_child.main()
                failure = json.loads(stdout.getvalue())
                self.assertEqual(failure["kind"], "failure")
                self.assertEqual(failure["request_id"], second["request_id"])
                self.assertEqual((failure["category"], failure["code"]), (category, code))

    async def test_cancelled_restore_reaps_warm_process_before_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child.py"
            child.write_text(CANCELLABLE_CHILD)
            parser = WarmParser(
                command=[sys.executable, str(child)],
                terminate_seconds=0.2,
                reap_seconds=1,
            )
            execution = Execution(None, None, root, child_runner=parser)
            request = {"expected_method": {}}
            try:
                await execution.child(
                    "pdf_processing.parse", {**request, "mode": "capture"}, root
                )
                first_pid = parser.process.pid
                first_request_id = parser.observation["request_id"]
                restore = asyncio.create_task(
                    execution.child(
                        "pdf_processing.parse", {**request, "mode": "restore"}, root
                    )
                )
                while (
                    parser.observation["request_id"] == first_request_id
                    or not parser.observation["ready"]
                ):
                    await asyncio.sleep(0.01)
                restore.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await restore
                self.assertIsNone(parser.process)
                self.assertEqual(parser.observation["termination_reason"], "attempt_cancelled")
                self.assertEqual(parser.count, 0)

                await execution.child(
                    "pdf_processing.parse", {**request, "mode": "capture"}, root
                )
                self.assertNotEqual(parser.process.pid, first_pid)
                self.assertEqual(parser.observation["restarts"], 2)
            finally:
                await parser.close()


if __name__ == "__main__":
    unittest.main()
