"""Behavior tests for the YOLO parser-lifetime candidate."""

import asyncio
from contextlib import asynccontextmanager
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
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
    async def test_lifecycle_lock_brackets_warm_parser_reap(self):
        import fcntl
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child.py"
            child.write_text("import time\ntime.sleep(60)\n")
            lock_path = root / "lifecycle.lock"
            parser = WarmParser(command=[sys.executable, str(child)])
            parser.process = await asyncio.create_subprocess_exec(
                sys.executable, str(child), start_new_session=True
            )
            with lock_path.open("a") as held, mock.patch.dict(
                os.environ, {"PDF_PROCESS_LIFECYCLE_LOCK": str(lock_path)}
            ):
                fcntl.flock(held, fcntl.LOCK_EX)
                stopped = asyncio.create_task(parser.stop("request_recycle"))
                await asyncio.sleep(.03)
                self.assertFalse(stopped.done())
                self.assertIsNone(parser.process.returncode)
                fcntl.flock(held, fcntl.LOCK_UN)
                await stopped
            self.assertIsNone(parser.process)

    async def test_lifecycle_lock_timeout_still_reaps_and_fails_closed(self):
        import fcntl
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child.py"
            child.write_text("import time\ntime.sleep(60)\n")
            lock_path = root / "lifecycle.lock"
            parser = WarmParser(command=[sys.executable, str(child)])
            parser.process = await asyncio.create_subprocess_exec(
                sys.executable, str(child), start_new_session=True
            )
            env = {
                "PDF_PROCESS_LIFECYCLE_LOCK": str(lock_path),
                "PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS": ".03",
            }
            with lock_path.open("a") as held, mock.patch.dict(os.environ, env):
                fcntl.flock(held, fcntl.LOCK_EX)
                with self.assertRaisesRegex(
                    RuntimeError, "process_lifecycle_lock_timeout"
                ):
                    await parser.stop("request_recycle")
            self.assertIsNone(parser.process)

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
        self.assertTrue(parser.closed)
        self.assertTrue(parser.observation["reap_failed"])
        with self.assertRaisesRegex(Exception, "worker_draining"):
            await parser.run({"expected_method": {}}, Path("."), lambda detail: None, 1)

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

    async def test_unreaped_restore_child_fails_closed_before_handoff_unlocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"pdf")
            parser = WarmParser()
            execution = Execution(
                SourceRequest(pdf, "rev", "sha", {}, root),
                object(),
                root,
                child_runner=parser,
            )

            class NeverReaped:
                pid = 4242
                returncode = None
                stdin = None

                async def communicate(self, _request):
                    raise RuntimeError("synthetic child failure")

                async def wait(self):
                    await asyncio.Future()

            process = NeverReaped()
            request = {"mode": "restore", "scan": True, "out": str(root / "result")}

            async def timeout_wait(awaitable, _seconds):
                awaitable.close()
                raise TimeoutError

            with mock.patch(
                "pdf_processing.execution.asyncio.create_subprocess_exec",
                new=mock.AsyncMock(return_value=process),
            ), mock.patch(
                "pdf_processing.execution.asyncio.wait_for",
                new=timeout_wait,
            ), mock.patch("pdf_processing.execution.os.killpg"):
                with self.assertRaisesRegex(Exception, "fresh_child_reap_failed"):
                    await execution.child("pdf_processing.parse", request, root)

            self.assertTrue(parser.closed)
            self.assertTrue(parser.observation["reap_failed"])
            self.assertEqual(
                parser.observation["termination_reason"], "fresh_child_reap_failed"
            )
            self.assertIn(process, execution.fresh_children)
            self.assertIn(process, execution_module._fresh_children)
            with self.assertRaisesRegex(Exception, "worker_draining"):
                await parser.run(
                    {"expected_method": {}}, root, lambda detail: None, 1
                )
            execution.fresh_children.clear()
            execution_module._fresh_children.clear()

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
    async def test_double_cancel_during_spawn_closes_lifecycle_sockets(self):
        parent = mock.Mock()
        child = mock.Mock()
        child.fileno.return_value = 42

        async def blocked_spawn(*args, **kwargs):
            await asyncio.Future()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            execution = Execution(None, None, root)
            with (
                mock.patch.dict(
                    os.environ, {"PDF_PROCESS_LIFECYCLE_LOCK": str(root / "lock")}
                ),
                mock.patch("socket.socketpair", return_value=(parent, child)),
                mock.patch(
                    "pdf_processing.execution.asyncio.create_subprocess_exec",
                    new=blocked_spawn,
                ),
            ):
                running = asyncio.create_task(
                    execution.fresh_child("fixture", {}, root)
                )
                await asyncio.sleep(0)
                running.cancel()
                await asyncio.sleep(0)
                running.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await running
        parent.close.assert_called_once_with()
        child.close.assert_called_once_with()

    async def test_shutdown_attempts_every_fresh_child_after_reap_timeout(self):
        class Process:
            returncode = None

            def __init__(self, pid, fail):
                self.pid = pid
                self.fail = fail

            async def wait(self):
                if self.fail:
                    raise TimeoutError
                self.returncode = -9

        stuck = Process(4242, True)
        reaped = Process(4343, False)
        children = {stuck, reaped}
        execution_module._fresh_children.update(children)
        try:
            with mock.patch("pdf_processing.execution.os.killpg") as kill:
                with self.assertRaisesRegex(Exception, "fresh_child_reap_failed"):
                    await execution_module._stop_children(children)
            self.assertEqual(
                {call.args[0] for call in kill.call_args_list}, {4242, 4343}
            )
            self.assertEqual(children, {stuck})
            self.assertIn(stuck, execution_module._fresh_children)
            self.assertNotIn(reaped, execution_module._fresh_children)
        finally:
            execution_module._fresh_children.difference_update(children)

    async def test_shutdown_attempts_fresh_cleanup_after_warm_close_failure(self):
        class Parser:
            async def close(self, reason):
                self.reason = reason
                raise RuntimeError("synthetic warm close failure")

        parser = Parser()
        with mock.patch(
            "pdf_processing.execution.stop_fresh_children",
            new=mock.AsyncMock(),
        ) as stop_fresh:
            with self.assertRaisesRegex(RuntimeError, "synthetic warm close failure"):
                await execution_module.stop_owned_children(parser)
        self.assertEqual(parser.reason, "worker_shutdown")
        stop_fresh.assert_awaited_once_with()

    async def test_shutdown_stops_fresh_child_that_holds_handoff_lock(self):
        close_started = asyncio.Event()
        release_handoff = asyncio.Event()

        class Parser:
            async def close(self, _reason):
                close_started.set()
                await release_handoff.wait()

        async def stop_fresh():
            await close_started.wait()
            release_handoff.set()

        with mock.patch(
            "pdf_processing.execution.stop_fresh_children", new=stop_fresh
        ):
            await asyncio.wait_for(
                execution_module.stop_owned_children(Parser()), timeout=.2
            )

    async def test_q04_worker_preserves_scratch_when_cleanup_is_incomplete(self):
        consumer = types.ModuleType("consumer")
        consumer.require = lambda *_args: None
        consumer.sha = lambda _value: "sha"
        telemetry = types.ModuleType("telemetry")
        telemetry.sample = lambda: {}
        path = Path(__file__).with_name("worker.py")
        spec = importlib.util.spec_from_file_location("q04_worker_cleanup_test", path)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(
            sys.modules, {"consumer": consumer, "telemetry": telemetry}
        ):
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            scratch.mkdir()
            with mock.patch(
                "pdf_processing.execution.stop_owned_children",
                new=mock.AsyncMock(side_effect=RuntimeError("unreaped child")),
            ):
                with self.assertRaisesRegex(RuntimeError, "unreaped child"):
                    await module.cleanup_owned_work(object(), scratch)
            self.assertTrue(scratch.is_dir())

    async def test_deploy_worker_preserves_scratch_when_cleanup_is_incomplete(self):
        temporalio = types.ModuleType("temporalio")
        client = types.ModuleType("temporalio.client")
        client.Client = object
        worker = types.ModuleType("temporalio.worker")
        worker.Worker = object
        path = Path(__file__).parents[3] / "deploy/pdf-processing/worker.py"
        spec = importlib.util.spec_from_file_location("deploy_worker_cleanup_test", path)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(
            sys.modules,
            {
                "temporalio": temporalio,
                "temporalio.client": client,
                "temporalio.worker": worker,
            },
        ):
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            owned = scratch / "activity-owned"
            owned.mkdir()
            with mock.patch.dict(os.environ, {"SCRATCH": str(scratch)}), mock.patch(
                "pdf_processing.execution.stop_owned_children",
                new=mock.AsyncMock(side_effect=RuntimeError("unreaped child")),
            ):
                with self.assertRaisesRegex(RuntimeError, "unreaped child"):
                    await module.cleanup_owned_work(object())
            self.assertTrue(owned.is_dir())

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
            request = {"mode": "restore", "scan": True, "out": str(root / "result")}
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
                        {"mode": "restore", "scan": True, "out": str(root / "result")},
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
                        {"mode": "restore", "scan": True, "out": str(root / "result")},
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

    async def test_lifecycle_lock_keeps_completed_fresh_child_until_sample_finishes(self):
        import fcntl
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = root / "lifecycle_fixture.py"
            marker = root / "completed"
            module.write_text(
                "import json, pathlib, sys\n"
                "request=json.load(sys.stdin)\n"
                "pathlib.Path(request['marker']).write_text('done')\n"
            )
            lock_path = root / "lifecycle.lock"
            pdf = root / "source.pdf"
            pdf.write_bytes(b"pdf")
            execution = Execution(
                SourceRequest(pdf, "rev", "sha", {}, root), object(), root
            )
            env = {
                "PDF_PROCESS_LIFECYCLE_LOCK": str(lock_path),
                "PYTHONPATH": str(root) + os.pathsep + os.environ.get("PYTHONPATH", ""),
            }
            with lock_path.open("a") as held, mock.patch.dict(os.environ, env):
                fcntl.flock(held, fcntl.LOCK_EX)
                running = asyncio.create_task(
                    execution.fresh_child(
                        "lifecycle_fixture", {"marker": str(marker)}, root
                    )
                )
                while not marker.exists():
                    await asyncio.sleep(.01)
                await asyncio.sleep(.03)
                self.assertFalse(running.done())
                process = next(iter(execution.fresh_children))
                self.assertIsNone(process.returncode)
                fcntl.flock(held, fcntl.LOCK_UN)
                await running
            self.assertEqual(execution.fresh_children, set())

    async def test_completed_fresh_child_cleans_its_process_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = root / "descendant_fixture.py"
            marker = root / "descendant.pid"
            module.write_text(
                "import json, pathlib, subprocess, sys\n"
                "request=json.load(sys.stdin)\n"
                "child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                "pathlib.Path(request['marker']).write_text(str(child.pid))\n"
            )
            lock_path = root / "lifecycle.lock"
            pdf = root / "source.pdf"
            pdf.write_bytes(b"pdf")
            execution = Execution(
                SourceRequest(pdf, "rev", "sha", {}, root), object(), root
            )
            env = {
                "PDF_PROCESS_LIFECYCLE_LOCK": str(lock_path),
                "PYTHONPATH": str(root) + os.pathsep + os.environ.get("PYTHONPATH", ""),
            }
            with mock.patch.dict(os.environ, env):
                await execution.fresh_child(
                    "descendant_fixture", {"marker": str(marker)}, root
                )
            descendant = int(marker.read_text())
            try:
                import psutil
                status = psutil.Process(descendant).status()
            except psutil.NoSuchProcess:
                status = "absent"
            self.assertIn(status, {"absent", psutil.STATUS_ZOMBIE})


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
