"""Record gpt-6-luna fixtures from the rest of the public corpus (#129: "fixture 先從
`gpt-6-luna` 對 20 篇公開論文錄"); run.py recorded paper 20 with its Seam B evidence.

    env HF_HUB_OFFLINE=1 OPENAI_API_KEY=... .venv/bin/python docs/validation/80/t4-seam-b/record.py \
        CORPUS_MANIFEST [INDEX ...]
    env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t4-seam-b/record.py \
        --collect RUN INDEX ...

Same stack as run.py. Each paper gets a fresh bucket and its own workers, runs once against the
real model, and saves its responses with run.save_fixtures. Stops before the next paper once the
spend so far passes MAX_SPEND_USD. --collect saves fixtures and the summary from the buckets of
an earlier run without sending anything. recorded.json is rewritten after every paper: per paper
the receipt summary, the statuses and the redrive markers, no content.
"""

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from temporalio.client import Client

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run  # noqa: E402

from kp_processing.ports.object_store import ObjectNotFound  # noqa: E402
from kp_processing.stages import finalize  # noqa: E402

t2 = run.t2
RECORDED = HERE / "recorded.json"
# gpt-6-luna standard price per token (US$0.10/M in, US$0.50/M out).
PRICE = {"prompt_tokens": 0.10e-6, "completion_tokens": 0.50e-6}
MAX_SPEND_USD = 1.0


async def collect(rid: str, index: int, seconds: float | None) -> dict:
    """Save paper `index`'s fixtures from run `rid`'s bucket and add its entry to recorded.json;
    returns recorded.json's content."""
    store = t2.store(f"seamb-{rid}-p{index}")
    request_id = f"req_{rid}_p{index}"
    try:
        result = json.loads(await store.get(f"requests/{request_id}/result.json"))
    except ObjectNotFound:
        result = {}
    sent = await run.receipts(store, request_id)
    recorded = json.loads(RECORDED.read_text()) if RECORDED.exists() else {"papers": {}}
    recorded["papers"][str(index)] = {
        "run": rid, "seconds": seconds, "outcome": result.get("outcome"),
        "receipts": run.receipt_summary(sent),
        "statuses": run.per_method(result) if result else None,
        "service_unavailable_markers": await finalize.service_unavailable(store),
        "fixtures_saved": await run.save_fixtures(store, result, sent) if result else 0,
    }  # fmt: skip
    recorded["spend_usd"] = round(sum(
        p["receipts"]["tokens"][k] * PRICE[k]
        for p in recorded["papers"].values() for k in PRICE
    ), 4)  # fmt: skip
    RECORDED.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n")
    return recorded


async def record(manifest: Path, indexes: list[int]) -> None:
    t2.LOGS.mkdir(parents=True)
    key = os.environ["OPENAI_API_KEY"]
    papers = {p["index"]: p for p in json.loads(manifest.read_text())["papers"]}
    temporal = subprocess.Popen(
        ["temporal", "server", "start-dev", "--headless", "--port", "7244", "--ui-port", "7245",
         "--db-filename", str(t2.LOGS / "temporal.db"), "--log-level", "warn"],
        stdout=open(t2.LOGS / "temporal.log", "w"), stderr=subprocess.STDOUT,
    )  # fmt: skip
    admission = subprocess.Popen(
        [str(t2.REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server", "--port", "8091",
         "--log", str(t2.LOGS / "reports.jsonl")], cwd=t2.REPO,
    )  # fmt: skip
    workers: list[subprocess.Popen] = []
    try:
        for _ in range(60):
            try:
                await Client.connect(t2.TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        for index in indexes:
            spend = json.loads(RECORDED.read_text())["spend_usd"] if RECORDED.exists() else 0.0
            if spend > MAX_SPEND_USD:
                print(f"stop: US${spend:.3f} spent", file=sys.stderr)
                break
            paper = papers[index]
            data = (manifest.parent / paper["file"]).read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            assert sha == paper["sha256"], "paper does not match the corpus manifest"
            bucket = f"seamb-{t2.RUN}-p{index}"
            await t2.store(bucket).put_if_absent(f"custody/{sha}", data)
            workers = [*t2.workers_for(bucket, f"p{index}"),
                       run.vlm_worker(bucket, f"p{index}", run.OPENAI, key)]  # fmt: skip
            code, _, seconds = await run.run_case(bucket, sha, data, f"req_{t2.RUN}_p{index}")
            recorded = await collect(t2.RUN, index, seconds)
            print(index, code, seconds, f"US${recorded['spend_usd']:.3f}", flush=True)
            for process in workers:
                process.terminate()
                process.wait()
            workers = []
    finally:
        for process in [*workers, admission, temporal]:
            process.terminate()
            process.wait()


async def main(argv: list[str]) -> int:
    if argv[0] == "--collect":
        for index in argv[2:]:
            await collect(argv[1], int(index), None)
    else:
        indexes = [int(i) for i in argv[1:]] or [i for i in range(1, 21) if i != 20]
        await record(Path(argv[0]), indexes)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
