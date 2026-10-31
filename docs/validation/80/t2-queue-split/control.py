"""Negative control for S1: the same run with the inference worker's one-slot limit removed
(hoard_worker.py) must show the hoarding the split removes; otherwise the sampler proves nothing.

    .venv/bin/python docs/validation/80/t2-queue-split/control.py CORPUS_MANIFEST
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scenarios as sc  # noqa: E402

seamb = sc.seamb


async def main(manifest: Path) -> None:
    seamb.LOGS.mkdir(parents=True)
    corpus = {p["index"]: p for p in json.loads(manifest.read_text())["papers"]}
    papers = {i: (manifest.parent / corpus[i]["file"]).read_bytes() for i in sc.PAPERS}
    temporal = subprocess.Popen(
        ["temporal", "server", "start-dev", "--headless", "--port", "7244", "--ui-port", "7245",
         "--db-filename", str(seamb.LOGS / "temporal.db"), "--log-level", "warn",
         "--dynamic-config-value", "matching.numTaskqueueReadPartitions=1",
         "--dynamic-config-value", "matching.numTaskqueueWritePartitions=1"],
        stdout=open(seamb.LOGS / "temporal.log", "w"), stderr=subprocess.STDOUT)
    admission = subprocess.Popen(
        [str(seamb.REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server", "--port",
         "8091", "--log", str(seamb.LOGS / "reports.jsonl")], cwd=seamb.REPO)
    os.environ.update(seamb.BASE_ENV)
    seamb.CLI = [str(seamb.REPO / ".venv/bin/python"), str(Path(__file__).parent / "hoard_worker.py")]
    stack = None
    try:
        for _ in range(60):
            try:
                client = await sc.Client.connect(seamb.TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        stack = sc.Stack(client, papers)
        result = await sc.s1_s4(stack)
        print(json.dumps({k: v for k, v in result.items() if k != "prepare_seconds_after_start"}, indent=1))
    finally:
        if stack:
            stack.stop_workers()
        admission.terminate()
        temporal.terminate()


asyncio.run(main(Path(sys.argv[1])))
