"""#155 C1: how well the Document Summary's verify step catches unsupported sentences, by planted
errors. From the kept sentences of a Seam B run (t5b-seam-b OUT_DIR), sample N; gpt-6-luna
rewrites each into one error of a type the program assigns in rotation (ERRORS; number only
for a sentence with a digit, since without one the planter cannot change a value); the planted
version goes through the production verify request (document_summary.verify_request, batched
with the rest of its Section's kept sentences, D4) on Sonnet 5.5, and so does the unaltered
batch. Caught = the planted sentence judged unsupported; false drop = an original judged
unsupported.

    set -a; . ~/.config/kp-dev/anthropic.env; . ~/.config/kp-dev/openai.env; set +a
    .venv/bin/python docs/validation/80/t5b-accuracy/run.py OUT_DIR SET_NAME \
        N|--rescore|--rejudge=BASE INDEX...

--rescore scores OUT_DIR/accuracy-SET_NAME.json again, without a request. --rejudge=BASE judges
the planted versions of OUT_DIR/accuracy-BASE.json again with the current verify request, no
planting, and reports each verdict that differs from BASE's (#164). A planted version
that is unchanged or a refusal of the planter (it starts with REFUSALS) is an invalid plant:
counted, but not in the catch rate.

Writes evidence-SET_NAME.json here (counts, rates with sample sizes, error types; no paper
text) and, under OUT_DIR, accuracy-SET_NAME.json (every case with text) and
spot-check-SET_NAME.json: every missed planted error, every original the judge called
unsupported and every sentence the pipeline rewrote or dropped, filled up at random to 30 cases
(C1). --rejudge also judges each sentence the pipeline dropped again: the original in its
Section's batch, and the rewrite alone when it is a sentence (#164).
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
REFUSALS = ("I can’t", "I can't", "I cannot")  # gpt-6-luna's, seen in the 2026-11-04 run
PRICE_PER_MTOK = {"input": 2.0, "output": 10.0}  # Sonnet 5.5, as t5b-seam-b


async def plant(luna: OpenAIChat, sentence: str, kind: str) -> str:
    prompt = (f"<sentence>{sentence}</sentence>\n\nRewrite the sentence with exactly one factual "
              f"error: {ERRORS[kind]}. Keep everything else, including its language and length, "
              "so that the error is subtle. Return only the rewritten sentence.")  # fmt: skip
    answer = await luna.complete({"messages": [{"role": "user", "content": prompt}],
                                  "response_format": PLANT})  # fmt: skip
    return json.loads(answer.content or "{}")["sentence"].strip()


async def verdicts(judge: OpenAIChat, document: dict, indices: list[int], sentences: list[str]):
    """The verdicts, the usage, and whether the answer wrote a reason before its verdict."""
    answer = await judge.complete(ds.verify_request(document, indices, sentences))
    content = answer.content or ""
    first = content.find('"reason"') < content.find('"supported"')
    return ds.parse_verdicts(len(sentences), content), answer.usage, first


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


def drops(summary: dict) -> list[dict]:
    """The sentences the pipeline dropped after a repair, each with the Section indices it was
    verified against and the batch its original was judged in."""
    document, record = summary["sections"], summary["record"]
    out = []
    for i, section in enumerate(record["sections"]):
        batch = [f.get("original") or f["text"] for f in section["fates"]]
        for n, f in enumerate(section["fates"]):
            if f["text"] is None:
                out.append({"paper": summary["paper"], "section_id": section["section_id"],
                            "indices": [i], "batch": batch, "n": n, "fate": f})  # fmt: skip
    by_id = {s["section_id"]: i for i, s in enumerate(document["sections"])}
    for f in record["overview"]["fates"]:
        if f["text"] is None and "rewrite" in f:
            indices = [by_id[e["section_id"]] for e in f["evidence"]]
            out.append({"paper": summary["paper"], "section_id": "(overview)", "indices": indices,
                        "batch": [f["original"]], "n": 0, "fate": f})  # fmt: skip
    return out


def valid(case: dict) -> bool:
    return case["planted"] != case["text"] and not case["planted"].startswith(REFUSALS)


async def judged(
    summaries: dict, sample: list[dict], plants: list[str] | None
) -> tuple[list[dict], dict, list[dict]]:
    """Every sampled case planted (plants[i] when given) and judged, the judge's usage with the
    answers that wrote a reason first, and, given plants, every pipeline drop judged again."""
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "answers": 0, "reason_first": 0}
    async with httpx.AsyncClient() as http:
        judge = OpenAIChat(http, "https://api.anthropic.com/v1", os.environ["ANTHROPIC_API_KEY"],
                           "claude-sonnet-5-5", 10, 300)  # fmt: skip
        luna = OpenAIChat(http, "https://api.openai.com/v1", os.environ["OPENAI_API_KEY"],
                          "gpt-6-luna", 10, 120)  # fmt: skip
        gate = asyncio.Semaphore(8)

        def count(u: dict, first: bool) -> None:
            usage["prompt_tokens"] += u.get("prompt_tokens") or 0
            usage["completion_tokens"] += u.get("completion_tokens") or 0
            usage["answers"] += 1
            usage["reason_first"] += first

        async def again(d: dict) -> dict:
            async with gate:
                document = summaries[d["paper"]]["sections"]
                v, u, first = await verdicts(judge, document, d["indices"], d["batch"])
                count(u, first)
                result = {"paper": d["paper"], "section_id": d["section_id"],
                          "original_supported": v[d["n"]][0], "rewrite_supported": None}  # fmt: skip
                rewrite = d["fate"]["rewrite"]
                if ds._is_sentence(rewrite):
                    v, u, first = await verdicts(judge, document, d["indices"], [rewrite])
                    count(u, first)
                    result["rewrite_supported"] = v[0][0]
                return result

        async def case(number: int, c: dict) -> dict:
            async with gate:
                kinds = [k for k in ERRORS if k != "number" or any(ch.isdigit() for ch in c["text"])]
                kind = kinds[number % len(kinds)]
                document = summaries[c["paper"]]["sections"]
                planted = plants[number] if plants else await plant(luna, c["text"], kind)
                batch = list(c["batch"])
                batch[c["n"]] = planted
                (planted_v, u1, f1), (original_v, u2, f2) = await asyncio.gather(
                    verdicts(judge, document, c["indices"], batch),
                    verdicts(judge, document, c["indices"], c["batch"]),
                )
                count(u1, f1)
                count(u2, f2)
                return {**{k: c[k] for k in ("paper", "kind", "indices", "text")},
                        "error": kind, "planted": planted, "changed": planted != c["text"],
                        "planted_supported": planted_v[c["n"]][0],
                        "planted_reason": planted_v[c["n"]][1],
                        "original_supported": original_v[c["n"]][0],
                        "original_reason": original_v[c["n"]][1]}  # fmt: skip

        cases = await asyncio.gather(*(case(n, c) for n, c in enumerate(sample)))
        dropped = [d for s in summaries.values() for d in drops(s)] if plants else []
        redropped = await asyncio.gather(*(again(d) for d in dropped))
    return list(cases), usage, list(redropped)


async def main(argv: list[str]) -> int:
    out, name, indices = Path(argv[0]), argv[1], [int(i) for i in argv[3:]]
    summaries = {}
    for index in indices:
        summary = json.loads((out / f"summary-{index}.json").read_text())
        if summary["record"]:
            summaries[index] = summary
    pool = [c for s in summaries.values() for c in candidates(s)]
    base = None
    if argv[2] == "--rescore":
        cases = json.loads((out / f"accuracy-{name}.json").read_text())
        before = json.loads((HERE / f"evidence-{name}.json").read_text())
        usage, redropped = before["judge_tokens"], before.get("pipeline_drops", [])
    else:
        if argv[2].startswith("--rejudge="):
            base = json.loads((out / f"accuracy-{argv[2].split('=', 1)[1]}.json").read_text())
        size = len(base) if base else int(argv[2])
        sample = random.Random(SEED).sample(pool, min(size, len(pool)))
        if base and [c["text"] for c in sample] != [c["text"] for c in base]:
            raise SystemExit("the sample differs from the base set's")
        plants = [c["planted"] for c in base] if base else None
        cases, usage, redropped = await judged(summaries, sample, plants)
    planted = [c for c in cases if valid(c)]
    caught = [c for c in planted if not c["planted_supported"]]
    dropped = [c for c in cases if not c["original_supported"]]
    by_error = {k: {"n": sum(c["error"] == k for c in planted),
                    "caught": sum(c["error"] == k for c in caught)} for k in ERRORS}  # fmt: skip
    evidence = {
        "set": name, "papers": sorted(summaries), "pool": len(pool), "sample": len(cases),
        "seed": SEED, "judge": "claude-sonnet-5-5", "planter": "gpt-6-luna",
        "valid_plants": len(planted), "invalid_plants": len(cases) - len(planted),
        "catch_rate": {"caught": len(caught), "n": len(planted),
                       "rate": round(len(caught) / len(planted), 3) if planted else None},
        "false_drop_rate": {"dropped": len(dropped), "n": len(cases),
                            "rate": round(len(dropped) / len(cases), 3) if cases else None},
        "by_error": by_error,
        "by_kind": {k: sum(c["kind"] == k for c in cases) for k in ("section", "overview")},
        "pipeline_drops": redropped,
        "judge_tokens": usage,
        "judge_usd": round((usage["prompt_tokens"] * PRICE_PER_MTOK["input"]
                            + usage["completion_tokens"] * PRICE_PER_MTOK["output"]) / 1e6, 3),
    }  # fmt: skip
    if base:
        evidence["changed"] = [
            {"case": i, "paper": c["paper"], "kind": c["kind"], "verdict": k, "now": c[k]}
            for i, (c, b) in enumerate(zip(cases, base, strict=True))
            for k in ("planted_supported", "original_supported")
            if c[k] != b[k]
        ]  # fmt: skip
    (HERE / f"evidence-{name}.json").write_text(json.dumps(evidence, indent=2) + "\n")
    (out / f"accuracy-{name}.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False))
    missed = [c for c in planted if c["planted_supported"]]
    spot = [{"why": "planted error not caught", **c} for c in missed]
    spot += [{"why": "original judged unsupported (false drop)", **c} for c in dropped]
    spot += [{"why": "rewritten or dropped by the pipeline", **r}
             for s in summaries.values() for r in revised(s)]  # fmt: skip
    # All of the above, even past SPOT_CHECK (C1); the rest of the cases fill up to it.
    rest = [c for c in cases if c not in missed and c not in dropped and valid(c)]
    fill = random.Random(SEED).sample(rest, max(0, min(len(rest), SPOT_CHECK - len(spot))))
    spot += [{"why": "random case", **c} for c in fill]
    (out / f"spot-check-{name}.json").write_text(json.dumps(spot, indent=1, ensure_ascii=False))
    print(json.dumps({k: evidence[k] for k in ("catch_rate", "false_drop_rate", "by_error")}))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
