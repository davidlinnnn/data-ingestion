# #136 capacity and freshness: V2 and V8

`run.py` drives the real stack on its own ports: Temporal dev server (Server 1.32.0, one
task-queue partition so that priority holds, with the correlation search attributes
registered), the RustFS S3 stand-in, `tools/fake_admission`, and one `kp-processing worker` per
queue. The orchestration, vlm and summary workers run on the host; every inference worker runs
in its own container from the `Dockerfile` here (linux/arm64, `--cpus 4 --memory 5g
--memory-swap 5g`), whose cgroup memory the harness samples every second. Both external
services are local stand-ins: the VLM stand-in answers each request after 3 s (#133), and the
summary stand-in is t5's under the provisional contract. After #155 the summary runs inside
the platform, and this stage's numbers change with it.

The workers run the DEV profile `tests/profiles/paper-pdf-dev.yaml`: `paper-pdf@1`'s methods
and runtime with DEV components, without `memory_guard_gib` and `receipt_retention_days`, and
with `status_report_budget_s` 1 instead of 60 (it matters only while admission is unreachable,
which it never was). The guard is `paper-pdf@1`'s `memory_guard_gib` (4 GiB).

Machine: Apple M5 Pro (6 performance and 12 efficiency cores); Docker Desktop VM with 18 CPUs
and 23.4 GiB. Papers are third-party and stay under `~/archive`; the JSON files here hold
timings, counts, memory samples and metric summaries only. Raw logs and metric scrapes stay in
`/tmp/seamb-<run>`.

## Cases and acceptance criteria

| # | Case | Acceptance criteria |
|---|---|---|
| V2 | One paper, one inference container: the 64-page paper (16), the one with the most pictures (20), a typical one (11) | exit 0; outcome `complete`; no Activity timed out; memory samples taken; `memory.peak` in (0, 5 GiB]; no OOM kill. Samples over the 4 GiB guard are recorded |
| K | Paper 16; the inference container is killed (SIGKILL) once at least half of the local items are registered, then started again | outcome `complete`; 0 < registered at kill < local items; one local enrichment per local item; enrichments reused after the restart = registered at kill; statuses equal V2's for paper 16 |
| V8 | Five normal papers (11, 17, 3, 4, 1) and one low (2) started at once; one orchestration worker and three inference containers | all `complete`; VLM requests in flight in [1, 28]; queue age for each of the four queues in both tiers; no bulk inference Activity starts while a normal one waits, with a negative control (one normal paper taken for bulk must show hits); no starvation, with a negative control (below); every normal paper's processing complete in (0, 600] s |

Starvation: every normal paper's second inference Activity starts after submission and before
any normal paper finishes parsing, so no paper waits for another to be parsed whole. The
second, because the first may land on an idle worker before the papers contend. The low paper
is the negative control: it waits behind normal work, so its second inference Activity must
start after the first normal parse is done.

Queue age in the tables is each Activity's first attempt, started minus scheduled, from
workflow history. The `kp_processing_queue_age_seconds` histogram measures the same interval
inside the Activity and has values on every worker (`metrics` in each JSON); its buckets are
too coarse for a p95.

## Results (2026-11-03, image `sha256:5623c9b8…`)

All pass.

### V2

| Paper | Pages | Wall clock | prepare | parse | enrich | finalize | Parse s/page | VLM requests (peak in flight) | Memory peak | Over guard | Timeouts |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 16 | 64 | 104.0 s | 0.2 s | 61.8 s | 41.4 s | 0.3 s | 0.96 | 52 (4) | 3.18 GiB | 0 of 103 | 0 |
| 20 | 50 | 110.6 s | 0.2 s | 78.8 s | 31.0 s | 0.2 s | 1.58 | 38 (4) | 3.21 GiB | 0 of 110 | 0 |
| 11 | 20 | 64.0 s | 0.1 s | 48.1 s | 15.5 s | 0.1 s | 2.40 | 17 (4) | 2.42 GiB | 0 of 63 | 0 |

Stage times are the status stages (running to succeeded reports). Memory peak is cgroup
`memory.peak`; `memory.current` stayed at or under 3.04 GiB and anonymous memory at or under
2.58 GiB. The limits read inside the container were `cpu.max 400000 100000`, `memory.max
5368709120`, `memory.swap.max 0`.

### K

The container was killed 67.7 s in, with 6 of paper 16's 11 local items registered. The
restarted worker's `enrich_local` (attempt 2) reused those 6 and enriched the other 5; outcome
`complete` in 126.9 s, statuses equal to V2's (code 59, formula 44 disputed, picture
interpretation 32, picture OCR 8, table status 3, document summary 1). Memory peaks 3.07 GiB
before the kill and 1.33 GiB after.

### V8

| Paper | Tier | Pages | Processing complete | Parse groups | Parse s/page (Activity time) | Longest group |
|---|---|---|---|---|---|---|
| 11 | normal | 20 | 164.3 s | 4 | 4.0 | 37.7 s |
| 17 | normal | 22 | 157.0 s | 5 | 2.0 | 14.3 s |
| 3 | normal | 25 | 190.0 s | 5 | 5.5 | 48.5 s |
| 4 | normal | 27 | 173.4 s | 6 | 4.3 | 88.1 s |
| 1 | normal | 28 | 174.3 s | 6 | 3.3 | 43.3 s |
| 2 | low | 22 | 186.8 s | 5 | 1.0 | 7.5 s |

- Queue age: inference normal p50 5.6 s, p95 30.0 s, max 43.3 s; inference bulk p50 0.002 s,
  max 159.1 s (its groups wait behind normal work); orchestration, vlm and summary p95 at most
  0.05 s in both tiers.
- Priority: no bulk inference Activity started while a normal one waited; the control saw 8.
- Starvation: normal papers' second inference Activities started 10.6-66.0 s in; the first
  normal parse finished at 147.6 s; the low paper's second started at 165.3 s.
- VLM: 69 requests, at most 8 in flight.
- Memory: peaks 2.59, 2.97 and 2.63 GiB; no sample over the guard; no OOM kill; no timeout.
- Metrics: every `kp_processing_*` metric and the Temporal SDK's `temporal_*` metrics have
  values on the worker endpoints; the orchestration worker's Temporal endpoint holds 24
  status-stage durations (six papers × four stages).

Parsing is slower than in V2: the three containers take 12 of the VM's 18 CPUs, most of which
run on efficiency cores. A `cpu.stat` read by hand during one V8 run (not in the JSON) showed
each container throttled in 25-42 % of its CPU periods, so each used its full 4 CPU quota.

## Against #93 §7 and §8, for #78 and #88

| Parameter | #93 | Measured | For |
|---|---|---|---|
| t_page | 10.5 s (#84 DEV median) | 0.96-2.40 s alone; 2.0-5.5 s with three containers | #88: the PROD CPU scenario table scales with t_page; #78: worker counts |
| Five normal papers on three workers (§8.3) | last paper's parse done at 7 min, end to end ≈ 9.5 min with 1 min for accept and publish | last normal paper processing complete at 3.2 min | #78: three inference workers hold the 10-minute target on the processing side; the 5-worker fallback is not needed |
| VLM concurrency | ≤ 20 effective, configured ceiling 28 | ceiling 20 (1 vlm worker × 5 slots × c 4); at most 8 in flight in V8 | #78: 28 came from the six tier queues, which #131 replaced with priority keys |
| R, VLM requests per document | ≈ 30 | 17-52 alone; 69 for the six V8 papers | #88: depends on the paper's pictures and formulas |
| CPU worker memory | 4 GiB guard | peak 3.21 GiB | #78: 4 GiB request, 5 GiB limit |
| Enrichment stage budget | p50 2 min, hard 4 min | 15.5-41.4 s | VLM stand-in at 3 s per request |
| Timeouts | none expected | none | Nothing to hand back to #93's batching decision |

Also for #78:

- The status-stage durations come from the Temporal workflow meter, which adds `namespace`,
  `service_name`, `task_queue` and `workflow_type` to `stage` and `tier`; the internal
  Activities' series of the same name carry `stage` and `tier` only. Queries aggregate by
  `stage` and `tier`.
- Alert on `temporal_workflow_task_execution_failed`: a bug in workflow code leaves the
  workflow running and retrying its task rather than failing it.
- The orchestration worker disables eager Activity execution: eager Activities skip matching,
  so they would carry no priority and no queue age.
- The search attributes `DocumentUid`, `SourceRevisionId` and `TraceId` need registering as
  Keyword in the company namespace (#137).

The 10-minute target is "searchable within 10 minutes"; Retrieval does not exist yet, so only
the processing side, from the start request to the Processing Result, is measured here.

The measurements give no reason to change `paper-pdf@1.yaml`'s `runtime`, whose timeouts and
retries the DEV profile shares. The longest inference Activity (88.1 s) is well inside
`start_to_close_s.inference` (900 s), and its heartbeat keeps it inside the 60 s heartbeat
timeout.

## Run notes

- The first V2 attempt failed at worker start (`NoSuchBucket`): the harness created the bucket
  after starting the workers, which probe it. It now creates it first.
- The first starvation control used each paper's first inference Activity. In one run the low
  paper's first group took an idle worker 0.4 s in, before the papers contended, so the check
  now uses the second.
- One V8 run flagged the low paper's first group as starting while paper 11's waited. Both were
  scheduled at 0.26 s (paper 11's 1 ms earlier) and the low one started at 0.31 s on an idle
  worker: history records the schedule before the task reaches matching, and an idle worker
  takes whichever task arrives first. The check now counts a normal task as waiting 1 s after
  its schedule. Priority orders waiting tasks only; it neither reserves workers nor preempts.

## Papers

| Index | File | Pages | sha256 |
|---|---|---|---|
| 1 | 01-2608.27454v1.pdf | 28 | `65afc6e12f6f707483fe1b79a97ab67c03abf4b4992f82fde03eb7b8d9ad4a69` |
| 2 | 02-2603.02766v1.pdf | 22 | `61cc0e44c3489a82435ce1b3c9e8d7db5cd21798e18c8c204b0f99b124baa615` |
| 3 | 03-2603.25158v5.pdf | 25 | `9f3f43101583a993b9a82905d790fb2dd57c60b37897187a0706c047bd0b58b0` |
| 4 | 04-2605.23904v2.pdf | 27 | `87f7f0f323b1671e9202b3ebb1596e909e507c71ecd1b360b0075a5ee1727fe3` |
| 11 | 11-2508.19828v5.pdf | 20 | `c206af4e792e9550f2aaec8a6c4d9b141d1ddcb587e781d7866870c8f3e4dd4f` |
| 16 | 16-2505.22954v1.pdf | 64 | `217c1ac0884312b897648027bdfd6745f4b790b522cab8a61fea32faf0752943` |
| 17 | 17-2506.10943v1.pdf | 22 | `eb3e7a5a10d352058f15bbd9a3f20069b21f7da7aac28d1a148595a8463c6331` |
| 20 | 20-2505.03335v1.pdf | 50 | `605f35a5cd02c809e107db127d74d54b46b8e26a015d8b6549567554379b6625` |

Image: `kp-processing:t7`, `sha256:5623c9b8234d1d9db479c16eb34e91bf76a2795d6e0dcb0288b4c5dba5400889`.

## Run

```sh
docker build --platform linux/arm64 -f docs/validation/80/t7-capacity/Dockerfile -t kp-processing:t7 .
env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t7-capacity/run.py v2 <corpus manifest> 16
env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t7-capacity/run.py kill <corpus manifest> 16
env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t7-capacity/run.py v8 <corpus manifest> 11,17,3,4,1 2
```

The kill case compares its statuses with `v2-16.json`, so V2 on the same paper runs first. V8
needs Docker Desktop with at least 16 GiB.
