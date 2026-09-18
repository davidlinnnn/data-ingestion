"""Behavior tests for the YOLO parser-lifetime candidate."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from pdf_processing import execution as execution_module
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
    async def test_failed_reap_retains_process_ownership(self):
        class NeverReaped:
            pid = 4242
            returncode = None

            async def wait(self):
                await asyncio.Future()

        parser = WarmParser(terminate_seconds=.01, reap_seconds=.01)
        process = NeverReaped()
        parser.process = process
        parser.count = 4
        with mock.patch("pdf_processing.supervision.os.killpg"):
            with self.assertRaises(TimeoutError):
                await parser.stop("synthetic_reap_timeout")
        self.assertIs(parser.process, process)
        self.assertEqual(parser.count, 4)

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

    async def test_cancelled_restore_reaps_fresh_child_releases_lock_and_allows_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            warm_child = root / "warm_child.py"
            warm_child.write_text(READY_DONE_CHILD)
            blocking_child = root / "blocking_child.py"
            blocking_child.write_text("import time\ntime.sleep(60)\n")
            parser = WarmParser(command=[sys.executable, str(warm_child)])
            request = {"expected_method": {}}
            await parser.run(request, root, lambda detail: None, 3)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"pdf")
            execution = Execution(
                SourceRequest(pdf, "rev", "sha", {}, root),
                object(),
                root,
                child_runner=parser,
            )
            started = asyncio.Event()
            create = asyncio.create_subprocess_exec
            spawned = []

            async def spawn(*_args, **kwargs):
                process = await create(sys.executable, str(blocking_child), **kwargs)
                spawned.append(process)
                started.set()
                return process

            with mock.patch(
                "pdf_processing.execution.asyncio.create_subprocess_exec",
                new=spawn,
            ):
                restore = asyncio.create_task(
                    execution.child(
                        "pdf_processing.parse",
                        {"mode": "restore", "out": str(root / "result")},
                        root,
                    )
                )
                await started.wait()
                restore.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await restore

            self.assertIsNone(parser.process)
            self.assertIsNotNone(spawned[0].returncode)
            self.assertEqual(execution_module._fresh_children, set())
            rebuilt = await parser.run(request, root, lambda detail: None, 3)
            self.assertEqual(rebuilt["restarts"], 2)
            await parser.close()

    async def test_cancelling_one_execution_does_not_kill_another_fresh_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blocking_child = root / "blocking_child.py"
            blocking_child.write_text("import time\ntime.sleep(60)\n")
            create = asyncio.create_subprocess_exec
            spawned = []
            both_started = asyncio.Event()

            async def spawn(*_args, **kwargs):
                process = await create(sys.executable, str(blocking_child), **kwargs)
                spawned.append(process)
                if len(spawned) == 2:
                    both_started.set()
                return process

            def execution(directory):
                pdf = directory / "source.pdf"
                pdf.write_bytes(b"pdf")
                return Execution(
                    SourceRequest(pdf, "rev", "sha", {}, directory),
                    object(),
                    directory,
                )

            first_root = root / "first"
            second_root = root / "second"
            first_root.mkdir()
            second_root.mkdir()
            first = execution(first_root)
            second = execution(second_root)
            with mock.patch(
                "pdf_processing.execution.asyncio.create_subprocess_exec",
                new=spawn,
            ):
                first_task = asyncio.create_task(
                    first.child("pdf_processing.ocr", {}, first_root)
                )
                second_task = asyncio.create_task(
                    second.child("pdf_processing.ocr", {}, second_root)
                )
                await both_started.wait()
                while not first.fresh_children or not second.fresh_children:
                    await asyncio.sleep(0)
                first_process = next(iter(first.fresh_children))
                second_process = next(iter(second.fresh_children))
                first_task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await first_task
                self.assertIsNotNone(first_process.returncode)
                self.assertIsNone(second_process.returncode)
                self.assertFalse(second_task.done())
                second_task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await second_task
            self.assertEqual(execution_module._fresh_children, set())


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
