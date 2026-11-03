"""Seam B for #155: corpus papers through the real stack with the in-platform Document Summary
on Claude Sonnet 5.5 (Anthropic's OpenAI-compatible endpoint, B4); the VLM is t4's local
stand-in, so the summary is the only external request.

    set -a; . ~/.config/kp-dev/anthropic.env; set +a
    env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t5b-seam-b/run.py \\
        CORPUS_MANIFEST OUT_DIR [--fairness|--fairness-off BIG SMALL] INDEX...

Ports of its own (Temporal 7264/7265, fake_admission 8111, VLM stand-in 8112; S3 stand-in on
9100); it refuses to start when any is taken. Fairness is switched on in the dev server
(matching.enableFairness), except with --fairness-off.

Cases, each paper in a fresh bucket of this run:
  S  the document completes; its summary is success (or a recorded failure reason), each overview
     sentence cites at least one summarized Section, every summarized Section is listed in
     reading order, no published sentence lacks a verify, summary sends all ok
  C  a second request for the same document: no summary request, the summary reused
  F  (with --fairness) BIG starts; SMALL (a short paper, so its chunks come soon) starts once
     BIG's chunk Activities are scheduled. The DEV profile is copied with
     summary_concurrency_per_document FAIR_CONCURRENCY, so BIG's chunks queue behind the
     summary worker's slots, and a second inference worker runs. Measured: the BIG chunks that
     started while SMALL had a summary task in the queue (its summary_sections, then its first
     chunk to start, each from scheduled to started). Pass when BIG had at least MIN_BACKLOG
     chunks waiting as SMALL's summary_sections was scheduled and at most MAX_PASSED_BY started.
     --fairness-off is the negative control, fairness switched off in the server: pass when
     at least MIN_BACKLOG started, so the measurement can see a document waiting.

Per paper, evidence-INDEX.json keeps counts, timings, tokens, statuses and the headings of the
skipped Sections only (the papers are third-party). OUT_DIR (outside the repo) gets each summary's content and record.json, for the
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

import yaml
from temporalio.client import Client
from temporalio.service import RPCError

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
PRICE_PER_MTOK = {"input": 2.0, "output": 10.0}  # Sonnet 5.5, USD per million tokens (2026-10)
STOP_AT_USD = 40.0
SUMMARY = "document-summary"
FAIR_CONCURRENCY = 16  # paper 20's chunks, against the worker's 5 slots
MIN_BACKLOG = 3
MAX_PASSED_BY = 2  # tasks already dispatched to a poller when SMALL's chunk was scheduled


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


async def scheduled(client: Client, request_id: str, activity: str) -> bool:
    """Whether the workflow has scheduled the Activity."""
    try:
        history = await client.get_workflow_handle(request_id).fetch_history()
    except RPCError:  # not started yet
        return False
    return any(
        event.activity_task_scheduled_event_attributes.activity_type.name == activity
        for event in history.events
        if event.HasField("activity_task_scheduled_event_attributes")
    )


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
    fairness, fair = None, True
    if rest[:1] in (["--fairness"], ["--fairness-off"]):
        fairness, fair, rest = (int(rest[1]), int(rest[2])), rest[0] == "--fairness", rest[3:]
    indices = [int(i) for i in rest]
    key = os.environ["ANTHROPIC_API_KEY"]
    ports = (TEMPORAL_PORT, TEMPORAL_PORT + 1, ADMISSION_PORT, VLM_PORT)
    if busy := [port for port in ports if t5.taken(port)]:
        raise SystemExit(f"ports already in use: {busy}")
    t2.LOGS.mkdir(parents=True)
    out.mkdir(parents=True, exist_ok=True)
    if fairness:
        profile = yaml.safe_load(Path(t2.PROFILE).read_text())
        profile["runtime"]["summary_concurrency_per_document"] = FAIR_CONCURRENCY
        t2.PROFILE = str(t2.LOGS / "paper-pdf-dev-fairness.yaml")
        Path(t2.PROFILE).write_text(yaml.safe_dump(profile, sort_keys=False))
    papers = {p["index"]: p for p in json.loads(manifest.read_text())["papers"]}
    temporal = t5.subprocess.Popen(
        ["temporal", "server", "start-dev", "--headless", "--port", str(TEMPORAL_PORT),
         "--ui-port", str(TEMPORAL_PORT + 1), "--db-filename", str(t2.LOGS / "temporal.db"),
         "--log-level", "warn",
         "--dynamic-config-value", f"matching.enableFairness={str(fair).lower()}",
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
    if fairness:  # SMALL's parse must not wait for BIG's local enrichment (one slot a worker)
        workers.append(t5.worker(bucket, "s2", "inference", {}))
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
            # run_case blocks on the CLI subprocess, so BIG gets a thread and an event loop of
            # its own while this one watches its history.
            big_task = asyncio.create_task(
                asyncio.to_thread(asyncio.run, t4.run_case(bucket, big_sha, big_data, big_id))
            )
            begin = time.monotonic()
            while not await scheduled(client, big_id, "summary_chunk"):
                assert time.monotonic() - begin < 900, "BIG's chunks were never scheduled"
                await asyncio.sleep(1)
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
                        "small_spans": [{**s, **{k: s[k] + offset for k in ("scheduled", "started",
                                                                             "completed")}}
                                        for s in small_t["spans"]]}  # fmt: skip
            spans = evidence["small_spans"]
            (sections,) = [s for s in spans if s["activity"] == "summary_sections"]
            first = min((s for s in spans if s["activity"] == "summary_chunk"),
                        key=lambda s: s["started"])  # fmt: skip
            # SMALL waits in the queue for its sections, then for its first chunk.
            waits = [(t["scheduled"], t["started"]) for t in (sections, first)]
            waiting = [s for s in evidence["big_chunks"]
                       if s["scheduled"] <= sections["scheduled"] < s["started"]]
            passed_by = [s for s in evidence["big_chunks"]
                         if any(a <= s["started"] < b for a, b in waits)]
            evidence.update(fair=fair, big_waiting=len(waiting), passed_by=len(passed_by),
                            small_wait_s=round(sum(b - a for a, b in waits), 1))
            backlog = len(waiting) >= MIN_BACKLOG
            evidence["pass"] = (
                big_case[0] == 0 and small_case[0] == 0 and backlog
                and (0 <= len(passed_by) <= MAX_PASSED_BY if fair
                     else len(passed_by) >= MIN_BACKLOG)
            )  # fmt: skip
            name = "evidence-fairness.json" if fair else "evidence-fairness-off.json"
            (HERE / name).write_text(json.dumps(evidence, indent=2) + "\n")
            print("F", {k: v for k, v in evidence.items() if not k.endswith(("_chunks", "_spans"))},
                  flush=True)
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
