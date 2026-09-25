"""Worker readiness must start after the first durable telemetry sample."""

import asyncio
import json
from pathlib import Path
import tempfile
import time
import unittest

from worker_bc import publish_ready_after_first_sample


class WorkerReadinessTest(unittest.TestCase):
    def test_ready_marker_follows_first_sample(self):
        async def check():
            with tempfile.TemporaryDirectory() as raw:
                out = Path(raw)
                first_sample = asyncio.Event()
                task = asyncio.create_task(publish_ready_after_first_sample(
                    out, {"pid": 7, "generation": 2}, first_sample, []))
                await asyncio.sleep(0)
                self.assertFalse((out / "ready.json").exists())
                observed = time.time()
                (out / "samples.jsonl").write_text(json.dumps({"time": observed}) + "\n")
                first_sample.set()
                await task
                self.assertGreaterEqual(json.loads((out / "ready.json").read_text())["time"], observed)
        asyncio.run(check())

    def test_sampler_failure_cannot_publish_ready(self):
        async def check():
            with tempfile.TemporaryDirectory() as raw:
                out = Path(raw)
                first_sample = asyncio.Event()
                first_sample.set()
                with self.assertRaises(ValueError):
                    await publish_ready_after_first_sample(
                        out, {"pid": 7, "generation": 2}, first_sample, ["ValueError"])
                self.assertFalse((out / "ready.json").exists())
        asyncio.run(check())
