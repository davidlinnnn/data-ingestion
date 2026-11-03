"""#155 C1: how well the Document Summary's verify step catches unsupported sentences, by planted
errors. From the kept sentences of a Seam B run (t5b-seam-b OUT_DIR), sample N; gpt-6-luna
rewrites each into one error of a type the program assigns in rotation (ERRORS); the planted
version goes through the production verify request (document_summary.verify_request, batched
with the rest of its Section's kept sentences, D4) on Sonnet 5.5, and so does the unaltered
batch. Caught = the planted sentence judged unsupported; false drop = an original judged
unsupported.

    set -a; . ~/.config/kp-dev/anthropic.env; . ~/.config/kp-dev/openai.env; set +a
    .venv/bin/python docs/validation/80/t5b-accuracy/run.py OUT_DIR SET_NAME N INDEX...

Writes evidence-SET_NAME.json here (counts, rates with sample sizes, error types; no paper
text) and, under OUT_DIR, accuracy-SET_NAME.json (every case with text) and
spot-check-SET_NAME.json: every missed planted error, every original the judge called
unsupported and every sentence the pipeline rewrote or dropped, filled up at random to 30 cases
(C1).
"""

import asyncio
import json
import os
import random
import sys
from pathlib import Path

import httpx

from kp_processing.methods import document_summary as ds
from kp_processing.ports.inference import OpenAIChat

HERE = Path(__file__).resolve().parent
SEED = 155
ERRORS = {
    "number": "change one number, quantity or percentage to a different value",
    "causation": "add a cause-and-effect claim the sentence does not make",
    "subject": "swap who or what the claim is about for another entity of the same kind",
    "scope": "widen the claim's scope (some -> all, one setting -> every setting)",
    "comparison": "add a comparison with another method, dataset or result",
}
PLANT = ds._schema("plant", ds._object(sentence=ds._STRING))
SPOT_CHECK = 30


async def plant(luna: OpenAIChat, sentence: str, kind: str) -> str:
    prompt = (f"<sentence>{sentence}</sentence>\n\nRewrite the sentence with exactly one factual "
              f"error: {ERRORS[kind]}. Keep everything else, including its language and length, "
              "so that the error is subtle. Return only the rewritten sentence.")  # fmt: skip
    answer = await luna.complete({"messages": [{"role": "user", "content": prompt}],
                                  "response_format": PLANT})  # fmt: skip
    return json.loads(answer.content or "{}")["sentence"].strip()


async def verdicts(judge: OpenAIChat, document: dict, indices: list[int], sentences: list[str]):
    answer = await judge.complete(ds.verify_request(document, indices, sentences))
    return ds.parse_verdicts(len(sentences), answer.content or ""), answer.usage


def candidates(summary: dict) -> list[dict]:
    """Every kept sentence with the Section indices it is verified against and its batch."""
    document, record = summary["sections"], summary["record"]
    out = []
    for i, section in enumerate(record["sections"]):
        kept = [f["text"] for f in section["fates"] if f["text"]]
        for n, text in enumerate(kept):
            out.append({"paper": summary["paper"], "kind": "section", "indices": [i],
                        "batch": kept, "n": n, "text": text})  # fmt: skip
    by_id = {s["section_id"]: i for i, s in enumerate(document["sections"])}
    for fate in record["overview"]["fates"]:
        if fate["text"]:
            indices = [by_id[e["section_id"]] for e in fate["evidence"]]
            out.append({"paper": summary["paper"], "kind": "overview", "indices": indices,
                        "batch": [fate["text"]], "n": 0, "text": fate["text"]})  # fmt: skip
    return out


def revised(summary: dict) -> list[dict]:
    """The sentences the pipeline rewrote or dropped, for the spot check."""
    out = []
    record = summary["record"]
    for section in record["sections"]:
        for f in section["fates"]:
            if "original" in f:
                out.append({"paper": summary["paper"], "heading": section["heading"], **f})
    for f in record["overview"]["fates"]:
        if "original" in f:
            out.append({"paper": summary["paper"], "heading": "(overview)", **f})
    return out


async def main(argv: list[str]) -> int:
    out, name, size, indices = Path(argv[0]), argv[1], int(argv[2]), [int(i) for i in argv[3:]]
    summaries = {}
    for index in indices:
        summary = json.loads((out / f"summary-{index}.json").read_text())
        if summary["record"]:
            summaries[index] = summary
    pool = [c for s in summaries.values() for c in candidates(s)]
    rng = random.Random(SEED)
    sample = rng.sample(pool, min(size, len(pool)))
    kinds = list(ERRORS)
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    async with httpx.AsyncClient() as http:
        judge = OpenAIChat(http, "https://api.anthropic.com/v1", os.environ["ANTHROPIC_API_KEY"],
                           "claude-sonnet-5-5", 10, 300)  # fmt: skip
        luna = OpenAIChat(http, "https://api.openai.com/v1", os.environ["OPENAI_API_KEY"],
                          "gpt-6-luna", 10, 120)  # fmt: skip
        gate = asyncio.Semaphore(8)

        async def case(number: int, c: dict) -> dict:
            async with gate:
                kind = kinds[number % len(kinds)]
                document = summaries[c["paper"]]["sections"]
                planted = await plant(luna, c["text"], kind)
                batch = list(c["batch"])
                batch[c["n"]] = planted
                (planted_v, u1), (original_v, u2) = await asyncio.gather(
                    verdicts(judge, document, c["indices"], batch),
                    verdicts(judge, document, c["indices"], c["batch"]),
                )
                for u in (u1, u2):
                    for k in usage:
                        usage[k] += u.get(k) or 0
                return {**{k: c[k] for k in ("paper", "kind", "indices", "text")},
                        "error": kind, "planted": planted, "changed": planted != c["text"],
                        "planted_supported": planted_v[c["n"]][0],
                        "planted_reason": planted_v[c["n"]][1],
                        "original_supported": original_v[c["n"]][0],
                        "original_reason": original_v[c["n"]][1]}  # fmt: skip

        cases = await asyncio.gather(*(case(n, c) for n, c in enumerate(sample)))
    planted = [c for c in cases if c["changed"]]
    caught = [c for c in planted if not c["planted_supported"]]
    dropped = [c for c in cases if not c["original_supported"]]
    by_error = {k: {"n": sum(c["error"] == k for c in planted),
                    "caught": sum(c["error"] == k for c in caught)} for k in ERRORS}  # fmt: skip
    evidence = {
        "set": name, "papers": sorted(summaries), "pool": len(pool), "sample": len(cases),
        "seed": SEED, "judge": "claude-sonnet-5-5", "planter": "gpt-6-luna",
        "planted_changed": len(planted),
        "catch_rate": {"caught": len(caught), "n": len(planted),
                       "rate": round(len(caught) / len(planted), 3) if planted else None},
        "false_drop_rate": {"dropped": len(dropped), "n": len(cases),
                            "rate": round(len(dropped) / len(cases), 3) if cases else None},
        "by_error": by_error,
        "by_kind": {k: sum(c["kind"] == k for c in cases) for k in ("section", "overview")},
        "judge_tokens": usage,
    }  # fmt: skip
    (HERE / f"evidence-{name}.json").write_text(json.dumps(evidence, indent=2) + "\n")
    (out / f"accuracy-{name}.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False))
    missed = [c for c in planted if c["planted_supported"]]
    spot = [{"why": "planted error not caught", **c} for c in missed]
    spot += [{"why": "original judged unsupported (false drop)", **c} for c in dropped]
    spot += [{"why": "rewritten or dropped by the pipeline", **r}
             for s in summaries.values() for r in revised(s)]  # fmt: skip
    # All of the above, even past SPOT_CHECK (C1); the rest of the cases fill up to it.
    rest = [c for c in cases if c not in missed and c not in dropped]
    fill = rng.sample(rest, max(0, min(len(rest), SPOT_CHECK - len(spot))))
    spot += [{"why": "random case", **c} for c in fill]
    (out / f"spot-check-{name}.json").write_text(json.dumps(spot, indent=1, ensure_ascii=False))
    print(json.dumps({k: evidence[k] for k in ("catch_rate", "false_drop_rate", "by_error")}))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
