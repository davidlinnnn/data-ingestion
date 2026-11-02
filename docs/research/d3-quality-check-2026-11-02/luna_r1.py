"""#153 B1: gpt-6-luna re-answers every picture of the 20-paper corpus with the round-1
picture-interpretation prompt (the method at 080e36b^, no reasoning_effort), for real errors
from a weaker prompt. Inputs come from the t4-seam-b buckets, so the requests equal the
shipped method's apart from the prompt and effort.

    env AWS_ACCESS_KEY_ID=kpdev AWS_SECRET_ACCESS_KEY=kpdev-secret HF_HUB_OFFLINE=1 \
        OPENAI_API_KEY=... .venv/bin/python \
        docs/research/d3-quality-check-2026-11-02/luna_r1.py OUT [PAPER ...]

Responses go to OUT (outside git, they quote third-party papers). Reruns skip saved answers.
Stops sending once the spend passes MAX_SPEND_USD.
"""

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[3]
T4 = REPO / "docs/validation/80/t4-accuracy"
sys.path.insert(0, str(REPO / "docs/validation/80/t4-seam-b"))
ROUND1 = "080e36b^"
METHOD = "src/kp_processing/methods/picture_interpretation/__init__.py"
# gpt-6-luna standard price per token (US$0.10/M in, US$0.50/M out).
PRICE = {"prompt_tokens": 0.10e-6, "completion_tokens": 0.50e-6}
MAX_SPEND_USD = 0.50


def load(name: str, source: str, path: str):
    spec = importlib.util.spec_from_loader(name, loader=None, origin=path)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = path
    exec(compile(source, path, "exec"), module.__dict__)
    return module


async def main(out: Path, papers: list[int]) -> int:
    t4 = load("t4acc", (T4 / "run.py").read_text(), str(T4 / "run.py"))
    source = subprocess.run(
        ["git", "show", f"{ROUND1}:{METHOD}"], cwd=REPO, check=True, capture_output=True, text=True
    ).stdout
    round1 = load("pi_round1", source, f"{ROUND1}:{METHOD}")
    out.mkdir(parents=True, exist_ok=True)
    key = os.environ["OPENAI_API_KEY"]
    spend = sum(
        sum(json.loads(p.read_text())["usage"].get(k, 0) * v for k, v in PRICE.items())
        for p in out.glob("*.json")
    )
    limit = asyncio.Semaphore(4)
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=5)) as client:

        async def one(paper: int, store, item: dict) -> None:
            nonlocal spend
            label = t4.item_label(paper, item["item_id"])
            path = out / f"{label}.json"
            if path.exists():
                return
            inputs = [await store.get(s["ref"]) for s in item["input_refs"]]
            body = {**round1.request(item, inputs), "model": "gpt-6-luna"}
            assert "reasoning_effort" not in body, "round 1 sent no reasoning_effort"
            async with limit:
                if spend > MAX_SPEND_USD:
                    return
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {key}"},
                )
            data = response.json()
            if response.status_code != 200:
                print(label, response.status_code, str(data)[:200], flush=True)
                return
            usage = data.get("usage", {})
            spend += sum(usage.get(k, 0) * v for k, v in PRICE.items())
            text = data["choices"][0]["message"].get("content") or ""
            path.write_text(
                json.dumps(
                    {
                        "label": label,
                        "paper": paper,
                        "item_id": item["item_id"],
                        "model": data.get("model"),
                        "usage": usage,
                        "text": text,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n"
            )
            print(label, f"US${spend:.4f}", flush=True)

        jobs = []
        for paper in papers or sorted(t4.runs()):
            store, items, _ = await t4.document(paper)
            jobs += [one(paper, store, i) for i in items if i["method"] == "picture-interpretation"]
        await asyncio.gather(*jobs)
    print(f"done: {len(list(out.glob('*.json')))} answers, US${spend:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]), [int(i) for i in sys.argv[2:]])))
