"""Seam B for #155: corpus papers through the real stack with the in-platform Document Summary
on Claude Sonnet 5.5 (Anthropic's OpenAI-compatible endpoint, B4); the VLM is t4's local
stand-in, so the summary is the only external request.

    set -a; . ~/.config/kp-dev/anthropic.env; set +a
    env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t5b-seam-b/run.py \\
        CORPUS_MANIFEST OUT_DIR [--fairness BIG SMALL] INDEX...

Ports of its own (Temporal 7264/7265, fake_admission 8111, VLM stand-in 8112; S3 stand-in on
9100); it refuses to start when any is taken. Fairness is switched on in the dev server
(matching.enableFairness).

Cases, each paper in a fresh bucket of this run:
  S  the document completes; its summary is success (or a recorded failure reason), each overview
     sentence cites at least one summarized Section, every summarized Section is listed in
     reading order, no published sentence lacks a verify, summary sends all ok
  C  a second request for the same document: no summary request, the summary reused
  F  (with --fairness) BIG starts; SMALL starts once BIG's first chunk Activity has started; pass
     when SMALL's summary_overview completes before BIG's does

Per paper, evidence-INDEX.json keeps counts, timings, tokens and statuses only (the papers are
third-party). OUT_DIR (outside the repo) gets each summary's content and record.json, for the
accuracy evaluation and the user's spot check. The run stops starting papers once the summary's
tokens priced at PRICE_PER_MTOK reach STOP_AT_USD (C3).
"""

import asyncio
import hashlib
import importlib.util
import json
import os
import sys
import time
from datetime import UTC
from pathlib import Path

from temporalio.client import Client

HERE = Path(__file__).resolve().parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


t5 = load("t5", HERE.parent / "t5-seam-b/run.py")
t4, t2 = t5.t4, t5.t2

TEMPORAL_PORT, ADMISSION_PORT, VLM_PORT = 7264, 8111, 8112
t2.TEMPORAL, t2.ADMISSION = f"127.0.0.1:{TEMPORAL_PORT}", f"http://127.0.0.1:{ADMISSION_PORT}"
t2.BASE_ENV.update(TEMPORAL_ADDRESS=t2.TEMPORAL, KP_ADMISSION_URL=t2.ADMISSION)
ANTHROPIC = "https://api.anthropic.com/v1"
PRICE_PER_MTOK = {"input": 3.0, "output": 15.0}  # Sonnet 5.5, USD per million tokens
STOP_AT_USD = 40.0
SUMMARY = "document-summary"


def cost(tokens: dict) -> float:
    return (tokens["prompt_tokens"] * PRICE_PER_MTOK["input"]
            + tokens["completion_tokens"] * PRICE_PER_MTOK["output"]) / 1e6  # fmt: skip


async def summary_timeline(client: Client, request_id: str) -> dict:
    """Seconds from the first summary Activity scheduled to summary_overview completed, and the
    per-Activity spans (scheduled, started, completed), relative to the workflow start, UTC."""
    history = await client.get_workflow_handle(request_id).fetch_history()
    origin = history.events[0].event_time.ToDatetime(UTC)
    scheduled, spans = {}, []
    started: dict = {}
    for event in history.events:
        at = (event.event_time.ToDatetime(UTC) - origin).total_seconds()
        if event.HasField("activity_task_scheduled_event_attributes"):
            name = event.activity_task_scheduled_event_attributes.activity_type.name
            scheduled[event.event_id] = (name, at)
        elif event.HasField("activity_task_started_event_attributes"):
            started[event.activity_task_started_event_attributes.scheduled_event_id] = at
        elif event.HasField("activity_task_completed_event_attributes"):
            sid = event.activity_task_completed_event_attributes.scheduled_event_id
            name, s_at = scheduled[sid]
            if name.startswith("summary_"):
                spans.append({"activity": name, "scheduled": s_at, "started": started.get(sid),
                              "completed": at})  # fmt: skip
    first = min((s["scheduled"] for s in spans), default=None)
    last = max((s["completed"] for s in spans if s["activity"] == "summary_overview"), default=None)
    seconds = round(last - first, 1) if first is not None and last is not None else None
    return {"seconds": seconds, "spans": spans}


async def summary_of(store, result: dict) -> tuple[dict, dict | None]:
    (enrichment,) = [e for e in result["enrichments"] if e["method_ref"]["id"] == SUMMARY]
    outcome = json.loads(await store.get(enrichment["result_ref"]))
    record = None
    if outcome["provider_artifact_ref"]:
        record = json.loads(await store.get(outcome["provider_artifact_ref"]))
    return {"enrichment": enrichment, "outcome": outcome}, record


def shape(found: dict, record: dict | None, sections: dict) -> dict:
    """Counts only: no paper text."""
    outcome = found["outcome"]
    content = outcome["content"] if outcome["outcome"] == "success" else None
    fates = [f for s in (record or {}).get("sections", []) for f in s["fates"]]
    overview = (record or {}).get("overview", {"target": 0, "fates": []})

    def count(items: list[dict]) -> dict:
        return {"kept": sum(bool(f["text"]) and "original" not in f for f in items),
                "rewritten": sum(bool(f["text"]) and "original" in f for f in items),
                "dropped": sum(not f["text"] for f in items)}  # fmt: skip

    summarized = [s["section_id"] for s in sections["sections"]]
    return {
        "status": [found["enrichment"]["status"], found["enrichment"]["status_reason"]],
        "outcome": [outcome["outcome"], outcome["reason"]],
        "sections": {"summarized": len(summarized), "skipped": [[s["heading"][:40], s["reason"],
                     s["chars"]] for s in sections["skipped"]],
                     "with_target": sum(bool(s["target"]) for s in sections["sections"]),
                     "chars": sum(len(s["text"]) for s in sections["sections"]),
                     "chunks": len(sections["chunks"])},  # fmt: skip
        "section_sentences": count(fates),
        "overview_sentences": {**count(overview["fates"]), "target": overview["target"]},
        "steps": (record or {}).get("steps"),
        "checks": {
            "overview_cites_summarized_sections": content is not None and all(
                o["evidence"] and all(e["section_id"] in summarized for e in o["evidence"])
                for o in content["overview"]),
            "sections_listed_in_reading_order": content is not None
            and [s["section_id"] for s in content["sections"]] == summarized,
        } if content is not None else None,
    }  # fmt: skip


async def run_paper(client, manifest: Path, paper: dict, out: Path, request_id: str, sha: str,
                    data: bytes, bucket: str) -> dict:  # fmt: skip
    code, result, seconds = await t4.run_case(bucket, sha, data, request_id)
    store = t2.store(bucket)
    evidence: dict = {"exit": code, "seconds": seconds}
    if code != 0:
        return evidence
    sent = [r for r in await t4.receipts(store, request_id) if r["method"] == f"{SUMMARY}@2"]
    found, record = await summary_of(store, result)
    plan_key = found["enrichment"]["result_ref"].split("/")[3]
    sections = json.loads(await store.get(f"documents/{result['request']['document_uid']}/items/"
                                          f"{plan_key}/sections.json"))  # fmt: skip
    evidence |= {"summary": shape(found, record, sections),
                 "timeline": await summary_timeline(client, request_id),
                 "receipts": t4.receipt_summary(sent)}  # fmt: skip
    (out / f"summary-{paper['index']}.json").write_text(json.dumps(
        {"paper": paper["index"], "content": found["outcome"]["content"], "record": record,
         "sections": sections}, indent=1, ensure_ascii=False))  # fmt: skip
    return evidence


async def main(argv: list[str]) -> int:
    manifest, out = Path(argv[0]), Path(argv[1])
    rest = argv[2:]
    fairness = None
    if rest[:1] == ["--fairness"]:
        fairness, rest = (int(rest[1]), int(rest[2])), rest[3:]
    indices = [int(i) for i in rest]
    key = os.environ["ANTHROPIC_API_KEY"]
    ports = (TEMPORAL_PORT, TEMPORAL_PORT + 1, ADMISSION_PORT, VLM_PORT)
    if busy := [port for port in ports if t5.taken(port)]:
        raise SystemExit(f"ports already in use: {busy}")
    t2.LOGS.mkdir(parents=True)
    out.mkdir(parents=True, exist_ok=True)
    papers = {p["index"]: p for p in json.loads(manifest.read_text())["papers"]}
    temporal = t5.subprocess.Popen(
        ["temporal", "server", "start-dev", "--headless", "--port", str(TEMPORAL_PORT),
         "--ui-port", str(TEMPORAL_PORT + 1), "--db-filename", str(t2.LOGS / "temporal.db"),
         "--log-level", "warn", "--dynamic-config-value", "matching.enableFairness=true",
         *t2.SEARCH_ATTRIBUTE_FLAGS],
        stdout=open(t2.LOGS / "temporal.log", "w"), stderr=t5.subprocess.STDOUT,
    )  # fmt: skip
    admission = t5.subprocess.Popen(
        [str(t2.REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server",
         "--port", str(ADMISSION_PORT), "--log", str(t2.LOGS / "reports.jsonl")], cwd=t2.REPO,
    )  # fmt: skip
    servers = [t5.stand_in(t4.StandIn, VLM_PORT)]
    bucket = f"seamb-{t2.RUN}-t5b"
    workers = [
        *t2.workers_for(bucket, "s"),
        t5.worker(bucket, "s", "vlm", {"KP_VLM_BASE_URL": f"http://127.0.0.1:{VLM_PORT}/v1",
                                       "KP_VLM_API_KEY": "none"}),
        t5.worker(bucket, "s", "summary", {"KP_SUMMARY_BASE_URL": ANTHROPIC,
                                           "KP_SUMMARY_API_KEY": key}),
    ]  # fmt: skip
    spent = {"prompt_tokens": 0, "completion_tokens": 0}
    failures = []
    try:
        client = None
        for _ in range(60):
            try:
                client = await Client.connect(t2.TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        assert client is not None
        store = t2.store(bucket)

        def load_paper(index: int) -> tuple[dict, str, bytes]:
            paper = papers[index]
            data = (manifest.parent / paper["file"]).read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            assert sha == paper["sha256"], "paper does not match the corpus manifest"
            return paper, sha, data

        if fairness:
            (big, big_sha, big_data), (small, small_sha, small_data) = map(load_paper, fairness)
            for sha, data in ((big_sha, big_data), (small_sha, small_data)):
                await store.put_if_absent(f"custody/{sha}", data)
            big_id, small_id = f"req_{t2.RUN}_f{big['index']}", f"req_{t2.RUN}_f{small['index']}"
            big_task = asyncio.create_task(t4.run_case(bucket, big_sha, big_data, big_id))
            begin = time.monotonic()
            while not any("/chunks/" in k or k.endswith("sections.json")
                          for k in await store.list_prefix(f"documents/doc_{big_sha[:16]}/")):
                await asyncio.sleep(1)  # fmt: skip
            await asyncio.sleep(3)  # BIG's chunk Activities are in flight
            small_started = round(time.monotonic() - begin, 1)
            small_case = await t4.run_case(bucket, small_sha, small_data, small_id)
            big_case = await big_task
            big_t = await summary_timeline(client, big_id)
            small_t = await summary_timeline(client, small_id)
            big_spans = [s for s in big_t["spans"] if s["activity"] == "summary_overview"]
            small_spans = [s for s in small_t["spans"] if s["activity"] == "summary_overview"]
            # Workflow-relative times: shift SMALL's by when it started after BIG.
            big_start = (await client.get_workflow_handle(big_id).describe()).start_time
            small_start = (await client.get_workflow_handle(small_id).describe()).start_time
            offset = (small_start - big_start).total_seconds()
            evidence = {"big": big["index"], "small": small["index"],
                        "small_started_after_s": small_started, "exits": [big_case[0], small_case[0]],
                        "big_overview_completed": big_spans[0]["completed"] if big_spans else None,
                        "small_overview_completed": (small_spans[0]["completed"] + offset
                                                     if small_spans else None),
                        "big_chunks": [s for s in big_t["spans"] if s["activity"] == "summary_chunk"],
                        "small_chunks": [{**s, **{k: s[k] + offset for k in ("scheduled", "started",
                                                                              "completed")}}
                                         for s in small_t["spans"]
                                         if s["activity"] == "summary_chunk"]}  # fmt: skip
            evidence["pass"] = (
                big_case[0] == 0 and small_case[0] == 0
                and evidence["small_overview_completed"] is not None
                and evidence["big_overview_completed"] is not None
                and 0 <= evidence["small_overview_completed"] < evidence["big_overview_completed"]
            )  # fmt: skip
            (HERE / "evidence-fairness.json").write_text(json.dumps(evidence, indent=2) + "\n")
            print("F", {k: v for k, v in evidence.items() if not k.endswith("_chunks")}, flush=True)
            failures += [] if evidence["pass"] else ["F"]

        for index in indices:
            if cost(spent) >= STOP_AT_USD:
                print(f"stopping before paper {index}: USD {cost(spent):.2f} spent", flush=True)
                break
            paper, sha, data = load_paper(index)
            bucket_i = f"{bucket}-{index}"
            for worker in workers:  # one bucket per paper: the workers follow it
                worker.terminate()
                worker.wait()
            workers = [
                *t2.workers_for(bucket_i, f"p{index}"),
                t5.worker(bucket_i, f"p{index}", "vlm", {
                    "KP_VLM_BASE_URL": f"http://127.0.0.1:{VLM_PORT}/v1", "KP_VLM_API_KEY": "none"}),
                t5.worker(bucket_i, f"p{index}", "summary", {
                    "KP_SUMMARY_BASE_URL": ANTHROPIC, "KP_SUMMARY_API_KEY": key}),
            ]  # fmt: skip
            store_i = t2.store(bucket_i)
            await store_i.put_if_absent(f"custody/{sha}", data)
            evidence = {"run": t2.RUN, "paper": {k: paper[k] for k in ("index", "sha256", "pages")}}
            evidence["S"] = await run_paper(client, manifest, paper, out, f"req_{t2.RUN}_s{index}",
                                            sha, data, bucket_i)  # fmt: skip
            s = evidence["S"]
            if s["exit"] == 0:
                spent = {k: spent[k] + s["receipts"]["tokens"][k] for k in spent}
                summary = s["summary"]
                s["usd"] = round(cost(s["receipts"]["tokens"]), 3)
                s["pass"] = (
                    summary["status"][0] in ("unverified", "failed")
                    and (summary["outcome"][0] != "success" or all(summary["checks"].values()))
                    and s["receipts"]["incomplete"] == 0
                    and s["receipts"]["requests"] >= 1
                    and 0 < (s["timeline"]["seconds"] or -1) <= 900
                )  # fmt: skip
            before = set(await store_i.list_prefix(f"documents/doc_{sha[:16]}/"))
            request_c = f"req_{t2.RUN}_c{index}"
            code, result_c, seconds = await t4.run_case(bucket_i, sha, data, request_c)
            sent_c = await t4.receipts(store_i, request_c)
            reused = [e["reused"] for e in result_c.get("enrichments", [])
                      if e["method_ref"]["id"] == SUMMARY]  # fmt: skip
            evidence["C"] = {"exit": code, "seconds": seconds, "external_receipts": len(sent_c),
                             "summary_reused": reused,
                             "objects_added_under_documents": len(set(await store_i.list_prefix(
                                 f"documents/doc_{sha[:16]}/")) - before)}  # fmt: skip
            evidence["C"]["pass"] = (code == 0 and not sent_c and reused == [True]
                                     and evidence["C"]["objects_added_under_documents"] == 0)  # fmt: skip
            (HERE / f"evidence-{index}.json").write_text(json.dumps(evidence, indent=2) + "\n")
            print(index, json.dumps({c: {k: evidence[c].get(k) for k in
                                         ("pass", "seconds", "usd")} for c in ("S", "C")}),
                  f"spent USD {cost(spent):.2f}", flush=True)  # fmt: skip
            failures += [f"{c}{index}" for c in ("S", "C") if not evidence[c].get("pass")]
    finally:
        for process in [*workers, admission, temporal]:
            process.terminate()
            process.wait()
        for server in servers:
            server.shutdown()
    print("failed:", failures or "none", f"spent USD {cost(spent):.2f}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
