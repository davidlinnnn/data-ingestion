"""PROTOTYPE (#155), throwaway: the LLM half of the in-platform Document Summary, no Temporal,
no S3. Answers: does sections -> map -> verify -> repair -> reduce work through the existing
OpenAIChat transport against Anthropic's OpenAI-compatible endpoint (B4), and what are its
latency, tokens, rewrite and drop rates, and output on real corpus papers?

    set -a; . ~/.config/kp-dev/anthropic.env; set +a
    uv run python docs/prototypes/summary-pipeline-155/probe.py OUT_DIR ASSEMBLY.json...

OUT_DIR receives per-paper JSON and report.md. Both hold paper text: keep them out of git.
"""

import asyncio
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import httpx

from kp_processing.methods import document_summary
from kp_processing.ports.inference import OpenAIChat, ServiceUnavailable

BASE_URL = "https://api.anthropic.com/v1"
MODEL = "claude-sonnet-5-5"
CHUNK_CHARS = 8000
CHARS_PER_SECTION_SENTENCE = 1500
MAX_SECTION_SENTENCES = 8
MIN_SECTION_CHARS = 500
CHARS_PER_OVERVIEW_SENTENCE = 8000
OVERVIEW_SENTENCES = (5, 15)
CHUNKS_IN_FLIGHT = 4
CALLS_IN_FLIGHT = 8
REFERENCES = {"references", "reference", "bibliography", "works cited", "literature cited",
              "cited literature", "references and notes", "參考文獻", "参考文献", "參考資料"}
ACKNOWLEDGEMENTS = ("acknowledg", "致謝", "致谢", "誌謝")

CALLS: list[dict] = []
SEM = asyncio.Semaphore(CALLS_IN_FLIGHT)


def normalize(heading: str) -> str:
    heading = re.sub(r"^\s*([0-9]+(\.[0-9]+)*|[A-Z](\.[0-9]+)*|[IVXLC]+)[.)]?\s+", "", heading.strip())
    return re.sub(r"[\s:：.]+$", "", heading).strip().lower()


def schema(name: str, body: dict) -> dict:
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": body}}


def obj(**props) -> dict:
    return {"type": "object", "properties": props, "required": list(props),
            "additionalProperties": False}


STR = {"type": "string"}
STRS = {"type": "array", "items": STR}
MAP_SCHEMA = schema("map", obj(sections={"type": "array", "items": obj(id=STR, sentences=STRS)}))
VERIFY_SCHEMA = schema("verify", obj(supported={"type": "boolean"}, reason=STR))
REPAIR_SCHEMA = schema("repair", obj(quotes=STRS, sentence=STR))
REDUCE_SCHEMA = schema("reduce", obj(sentences={"type": "array", "items": obj(
    text=STR, sources={"type": "array", "items": {"type": "integer"}})}))


async def call(transport: OpenAIChat, step: str, tag: str, prompt: str, fmt: dict) -> dict:
    request = {"messages": [{"role": "user", "content": prompt}], "response_format": fmt,
               "max_tokens": 8000}
    for attempt in range(4):
        async with SEM:
            started = time.perf_counter()
            try:
                answer = await transport.complete(request)
            except ServiceUnavailable as exc:
                CALLS.append({"step": step, "tag": tag, "ok": False, "error": exc.reason,
                              "latency_s": round(time.perf_counter() - started, 2)})
                await asyncio.sleep(2 ** attempt * 2)
                continue
        usage = answer.usage
        record = {"step": step, "tag": tag, "latency_s": round(time.perf_counter() - started, 2),
                  "prompt_tokens": usage.get("prompt_tokens"),
                  "completion_tokens": usage.get("completion_tokens")}
        try:
            data = json.loads(answer.content or "")
            CALLS.append({**record, "ok": True})
            return data
        except json.JSONDecodeError:
            CALLS.append({**record, "ok": False, "error": "INVALID_JSON"})
    raise RuntimeError(f"{step} {tag}: no usable answer")


def section_xml(section: dict) -> str:
    return (f'<section id="{section["id"]}" heading="{section["heading"]}">\n'
            f'{section["text"]}\n</section>')


async def verify(transport, tag, sentence: str, evidence: list[dict]) -> dict:
    prompt = ("<sections>\n" + "\n".join(section_xml(s) for s in evidence) + "\n</sections>\n\n"
              f"<sentence>{sentence}</sentence>\n\n"
              "Is every claim in the sentence supported by the sections above? Judge only against "
              "their text: background knowledge, plausibility and other parts of the paper do not "
              "count. Paraphrase is fine; added numbers, causes, comparisons or generalisations "
              "that the text does not state are not. Answer supported, and in reason name the "
              "unsupported part in one sentence (or say why it is supported).")
    return await call(transport, "verify", tag, prompt, VERIFY_SCHEMA)


async def repair(transport, tag, sentence: str, reason: str, evidence: list[dict]) -> str:
    prompt = ("<sections>\n" + "\n".join(section_xml(s) for s in evidence) + "\n</sections>\n\n"
              f"<sentence>{sentence}</sentence>\n<problem>{reason}</problem>\n\n"
              "The sentence was judged not fully supported by the sections, for the problem "
              "given. First copy into quotes the passages of the sections that support any part "
              "of the sentence. Then rewrite the sentence with as few changes as possible so that "
              "every claim is supported by those quotes; never add a claim. If nothing in the "
              "sections supports it, return an empty sentence.")
    return (await call(transport, "repair", tag, prompt, REPAIR_SCHEMA))["sentence"].strip()


async def checked(transport, tag, sentence: str, evidence: list[dict]) -> dict:
    """verify, then repair once and re-verify; the sentence's fate and history."""
    first = await verify(transport, tag, sentence, evidence)
    if first["supported"]:
        return {"text": sentence, "fate": "kept"}
    rewritten = await repair(transport, tag, sentence, first["reason"], evidence)
    if not rewritten:
        return {"text": None, "fate": "dropped", "original": sentence, "reason": first["reason"],
                "repair": "empty"}
    second = await verify(transport, tag, rewritten, evidence)
    if second["supported"]:
        return {"text": rewritten, "fate": "rewritten", "original": sentence,
                "reason": first["reason"]}
    return {"text": None, "fate": "dropped", "original": sentence, "reason": first["reason"],
            "rewrite": rewritten, "second_reason": second["reason"]}


def target(chars: int) -> int:
    return 0 if chars < MIN_SECTION_CHARS else min(MAX_SECTION_SENTENCES,
                                                   math.ceil(chars / CHARS_PER_SECTION_SENTENCE))


async def run_chunk(transport, title: str, outline: str, chunk: list[dict], tag: str) -> list[dict]:
    wanted = [s for s in chunk if s["target"]]
    targets = "\n".join(f'- {s["id"]}: {s["target"]} sentence(s)' for s in wanted)
    prompt = (f"<paper_title>{title}</paper_title>\n<outline>\n{outline}\n</outline>\n\n"
              "<sections>\n" + "\n".join(section_xml(s) for s in chunk) + "\n</sections>\n\n"
              "Summarize each section listed below in the given number of sentences, in the "
              "language of the section. Each sentence must stand alone (no 'this section', no "
              "'the authors' without context), carry the section's most important facts, and "
              "state only what the section's own text says. Use the outline only to judge what "
              f"matters; never summarize other sections.\n\n{targets}")
    answer = await call(transport, "map", tag, prompt, MAP_SCHEMA)
    by_id = {s["id"]: s for s in wanted}
    results = []
    for entry in answer["sections"]:
        section = by_id.get(entry["id"])
        if section is None:
            continue
        fates = await asyncio.gather(*(
            checked(transport, f"{tag}/{section['id']}", sentence, [section])
            for sentence in entry["sentences"] if sentence.strip()))
        results.append({"id": section["id"], "fates": list(fates)})
    return results


async def paper(transport, path: Path) -> dict:
    started = time.perf_counter()
    raw = document_summary.request({"document_uid": path.stem}, [path.read_bytes()])["sections"]
    sections, skipped = [], []
    for s in raw:
        name = normalize(s["heading"])
        if not s["text"].strip():
            skipped.append({"heading": s["heading"], "why": "empty"})
        elif name in REFERENCES:
            skipped.append({"heading": s["heading"], "why": "references", "chars": len(s["text"])})
        elif name.startswith(ACKNOWLEDGEMENTS):
            skipped.append({"heading": s["heading"], "why": "acknowledgements",
                            "chars": len(s["text"])})
        else:
            sections.append({"id": f"S{len(sections) + 1}", "section_id": s["section_id"],
                             "heading": s["heading"], "text": s["text"],
                             "target": target(len(s["text"]))})
    chunks, current, size = [], [], 0
    for s in sections:
        if current and size + len(s["text"]) > CHUNK_CHARS:
            chunks.append(current)
            current, size = [], 0
        current.append(s)
        size += len(s["text"])
    if current:
        chunks.append(current)
    title = raw[0]["heading"] if raw else path.stem
    outline = "\n".join(f'{s["id"]} {s["heading"]}' for s in sections)

    gate = asyncio.Semaphore(CHUNKS_IN_FLIGHT)

    async def gated(i, chunk):
        async with gate:
            return await run_chunk(transport, title, outline, chunk, f"{path.stem}/c{i}")

    chunk_results = await asyncio.gather(*(gated(i, c) for i, c in enumerate(chunks)))
    by_id = {s["id"]: s for s in sections}
    summaries = {r["id"]: r["fates"] for chunk in chunk_results for r in chunk}
    numbered = []
    for s in sections:
        for fate in summaries.get(s["id"], []):
            if fate["text"]:
                numbered.append((s["id"], fate["text"]))
    total = sum(len(s["text"]) for s in sections)
    n_overview = max(OVERVIEW_SENTENCES[0], min(OVERVIEW_SENTENCES[1],
                                                round(total / CHARS_PER_OVERVIEW_SENTENCE)))
    listing = "\n".join(f"[{i}] ({by_id[sid]['heading']}) {text}"
                        for i, (sid, text) in enumerate(numbered, 1))
    prompt = (f"<paper_title>{title}</paper_title>\n<statements>\n{listing}\n</statements>\n\n"
              f"Write an overview of the paper in at most {n_overview} sentences, in the language "
              "of the statements, for a reader deciding whether to read it: the problem, the "
              "approach, the main results with their numbers, and limitations where stated. Use "
              "only information in the statements above. For each sentence, list in sources the "
              "numbers of the statements it draws on.")
    reduced = await call(transport, "reduce", f"{path.stem}/overview", prompt, REDUCE_SCHEMA)
    overview = []
    for i, sentence in enumerate(reduced["sentences"]):
        cited = sorted({numbered[n - 1][0] for n in sentence["sources"] if 1 <= n <= len(numbered)})
        if not cited:
            overview.append({"text": None, "fate": "dropped", "original": sentence["text"],
                             "reason": "no valid sources"})
            continue
        fate = await checked(transport, f"{path.stem}/overview/{i}", sentence["text"],
                             [by_id[c] for c in cited])
        overview.append({**fate, "evidence": [by_id[c]["section_id"] for c in cited],
                         "cited": cited})
    return {"paper": path.stem, "seconds": round(time.perf_counter() - started, 1),
            "native_chars": total, "sections": len(sections), "skipped": skipped,
            "chunks": [[s["id"] for s in c] for c in chunks], "overview_target": n_overview,
            "overview": overview,
            "section_summaries": [{"id": s["id"], "heading": s["heading"], "chars": len(s["text"]),
                                   "target": s["target"], "fates": summaries.get(s["id"], [])}
                                  for s in sections]}


def stats(result: dict) -> dict:
    fates = [f for s in result["section_summaries"] for f in s["fates"]]
    count = lambda xs, fate: sum(f["fate"] == fate for f in xs)  # noqa: E731
    calls = [c for c in CALLS if c["tag"].split("/")[0] == result["paper"]]
    by_step = {}
    for step in ("map", "verify", "repair", "reduce"):
        ok = [c for c in calls if c["step"] == step and c.get("prompt_tokens") is not None]
        lat = sorted(c["latency_s"] for c in ok)
        by_step[step] = {"calls": len(ok),
                         "prompt_tokens": sum(c["prompt_tokens"] for c in ok),
                         "completion_tokens": sum(c["completion_tokens"] or 0 for c in ok),
                         "latency_p50": lat[len(lat) // 2] if lat else None,
                         "latency_max": lat[-1] if lat else None}
    return {"paper": result["paper"], "seconds": result["seconds"],
            "native_chars": result["native_chars"], "sections": result["sections"],
            "chunks": len(result["chunks"]),
            "section_sentences": {f: count(fates, f) for f in ("kept", "rewritten", "dropped")},
            "overview_sentences": {f: count(result["overview"], f)
                                   for f in ("kept", "rewritten", "dropped")},
            "overview_target": result["overview_target"], "steps": by_step,
            "failed_calls": sum(not c["ok"] for c in calls)}


def report(results: list[dict], summary: list[dict]) -> str:
    lines = ["# PROTOTYPE #155 summary probe (paper text: keep out of git)", ""]
    for result, st in zip(results, summary):
        lines += [f"## {result['paper']}", "", "```json", json.dumps(st, indent=1), "```", "",
                  "### Overview", ""]
        for o in result["overview"]:
            mark = {"kept": "", "rewritten": " *(rewritten)*", "dropped": " **(dropped)**"}[o["fate"]]
            lines.append(f"- {o['text'] or o['original']}{mark} — {', '.join(o.get('cited', []))}")
        lines += ["", "### Sections", ""]
        for s in result["section_summaries"]:
            lines.append(f"**{s['id']} {s['heading']}** ({s['chars']} chars, target {s['target']})")
            for f in s["fates"]:
                if f["fate"] == "kept":
                    lines.append(f"- {f['text']}")
                elif f["fate"] == "rewritten":
                    lines.append(f"- {f['text']} *(rewritten from: {f['original']}; {f['reason']})*")
                else:
                    lines.append(f"- ~~{f['original']}~~ **dropped**: {f['reason']}")
            lines.append("")
    return "\n".join(lines)


async def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as client:
        transport = OpenAIChat(client, BASE_URL, os.environ["ANTHROPIC_API_KEY"], MODEL,
                               connect_s=10, total_s=300)
        results = []
        for arg in sys.argv[2:]:
            result = await paper(transport, Path(arg))
            results.append(result)
            (out / f"{result['paper']}.json").write_text(json.dumps(result, indent=1,
                                                                    ensure_ascii=False))
            print(json.dumps(stats(result)), flush=True)
    summary = [stats(r) for r in results]
    (out / "calls.json").write_text(json.dumps(CALLS, indent=1))
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    (out / "report.md").write_text(report(results, summary))


if __name__ == "__main__":
    asyncio.run(main())
