"""Behavior tests for the YOLO parser-lifetime candidate."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from pdf_processing.execution import Execution, SourceRequest
from pdf_processing.compatibility import dependencies
from pdf_processing.supervision import WarmParser


READY_DONE_CHILD = r'''import json,sys,time
for line in sys.stdin:
    envelope=json.loads(line)
    request_id=envelope['request_id']
    print(json.dumps({'protocol':'pdf-warm-v1','request_id':request_id,
                      'kind':'ready','method':{}}),flush=True)
    time.sleep(.15)
    print(json.dumps({'protocol':'pdf-warm-v1','request_id':request_id,
                      'kind':'done','memory':{'peak_rss':100}}),flush=True)
'''


class WarmParserHandoffTests(unittest.IsolatedAsyncioTestCase):
    async def test_handoff_waits_for_active_capture_then_rebuilds_on_next_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child.py"
            child.write_text(READY_DONE_CHILD)
            parser = WarmParser(command=[sys.executable, str(child)])
            request = {"expected_method": {}}

            capture = asyncio.create_task(
                parser.run(request, root, lambda detail: None, 3)
            )
            while not parser.observation["ready"]:
                await asyncio.sleep(.01)
            first_pid = parser.process.pid
            handoff_entered = asyncio.Event()
            release_handoff = asyncio.Event()

            async def own_fresh_child():
                async with parser.fresh_child_handoff():
                    handoff_entered.set()
                    await release_handoff.wait()

            handoff = asyncio.create_task(own_fresh_child())
            await asyncio.sleep(.03)

            self.assertFalse(handoff.done())
            self.assertEqual(parser.process.pid, first_pid)
            await capture
            await handoff_entered.wait()
            self.assertIsNone(parser.process)
            self.assertEqual(parser.observation["termination_reason"], "fresh_child_handoff")

            rebuilt_task = asyncio.create_task(
                parser.run(request, root, lambda detail: None, 3)
            )
            await asyncio.sleep(.03)
            self.assertFalse(rebuilt_task.done())
            self.assertIsNone(parser.process)
            release_handoff.set()
            await handoff
            rebuilt = await rebuilt_task
            self.assertNotEqual(rebuilt["pid"], first_pid)
            self.assertEqual(rebuilt["restarts"], 2)
            self.assertEqual(rebuilt["handoffs"], 1)
            await parser.close()

    async def test_cancelled_handoff_finishes_owned_process_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child.py"
            child.write_text(READY_DONE_CHILD)
            parser = WarmParser(
                command=[sys.executable, str(child)],
                terminate_seconds=.1,
                reap_seconds=2,
            )
            await parser.run({"expected_method": {}}, root, lambda detail: None, 3)
            self.assertIsNotNone(parser.process)

            original_stop = parser.stop
            entered = asyncio.Event()

            async def observable_stop(reason):
                entered.set()
                await original_stop(reason)

            with mock.patch.object(parser, "stop", observable_stop):
                async def own_fresh_child():
                    async with parser.fresh_child_handoff():
                        pass

                handoff = asyncio.create_task(own_fresh_child())
                await entered.wait()
                handoff.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await handoff

            self.assertIsNone(parser.process)
            self.assertEqual(parser.observation["termination_reason"], "fresh_child_handoff")


class ExecutionHandoffTests(unittest.IsolatedAsyncioTestCase):
    async def test_restore_waits_for_handoff_before_spawning_and_propagates_spawn_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"pdf")
            source = SourceRequest(pdf, "rev", "sha", {}, root)

            class Runner:
                def __init__(self):
                    self.entered = asyncio.Event()
                    self.release = asyncio.Event()

                @asynccontextmanager
                async def fresh_child_handoff(self):
                    self.entered.set()
                    await self.release.wait()
                    yield {"termination_reason": "fresh_child_handoff"}

            runner = Runner()
            execution = Execution(source, object(), root, child_runner=runner)
            request = {"mode": "restore", "out": str(root / "result")}
            with mock.patch(
                "pdf_processing.execution.asyncio.create_subprocess_exec",
                new=mock.AsyncMock(side_effect=RuntimeError("synthetic spawn failure")),
            ) as spawn:
                task = asyncio.create_task(
                    execution.child("pdf_processing.parse", request, root)
                )
                await runner.entered.wait()
                self.assertEqual(spawn.await_count, 0)
                self.assertFalse(task.done())
                runner.release.set()
                with self.assertRaisesRegex(RuntimeError, "synthetic spawn failure"):
                    await task
                self.assertEqual(spawn.await_count, 1)
                self.assertEqual(
                    execution.observation["parser_handoff"]["termination_reason"],
                    "fresh_child_handoff",
                )

    async def test_restore_spawn_failure_still_leaves_real_warm_parser_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child.py"
            child.write_text(READY_DONE_CHILD)
            parser = WarmParser(command=[sys.executable, str(child)])
            await parser.run({"expected_method": {}}, root, lambda detail: None, 3)
            self.assertIsNotNone(parser.process)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"pdf")
            execution = Execution(
                SourceRequest(pdf, "rev", "sha", {}, root),
                object(),
                root,
                child_runner=parser,
            )
            with mock.patch(
                "pdf_processing.execution.asyncio.create_subprocess_exec",
                new=mock.AsyncMock(side_effect=RuntimeError("synthetic spawn failure")),
            ):
                with self.assertRaisesRegex(RuntimeError, "synthetic spawn failure"):
                    await execution.child(
                        "pdf_processing.parse",
                        {"mode": "restore", "out": str(root / "result")},
                        root,
                    )
            self.assertIsNone(parser.process)
            self.assertEqual(parser.observation["termination_reason"], "fresh_child_handoff")


class CandidateIdentityTests(unittest.TestCase):
    def test_assembly_identity_includes_supervision_lifecycle(self):
        method = {
            "format": "PROTOTYPE-page-v1",
            "options": {"do_ocr": False},
            "option_types": {},
            "packages": {},
            "model_artifacts": {},
        }
        profile = {"method": method}
        producer = {
            name: name + "-sha"
            for name in (
                "continuation.py",
                "parse.py",
                "execution.py",
                "compatibility.py",
                "supervision.py",
            )
        }
        first = dependencies("assembly", profile, producer)
        changed = dependencies(
            "assembly",
            profile,
            {**producer, "supervision.py": "changed-sha"},
        )
        self.assertIn("supervision.py", first["producer"])
        self.assertNotEqual(first, changed)


if __name__ == "__main__":
    unittest.main()
