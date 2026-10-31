# #131 Seam B: orchestration and inference queues

The CPU work splits into two task queues, each served by its own worker process (one
Kubernetes Deployment per queue, scaled on that queue's backlog):

| Queue | Worker serves | Activity slots per worker |
|---|---|---|
| `orchestration` | the workflow; `prepare`, `inventory`, `finalize`, `register_failure`, `report` | SDK default |
| `inference` | `parse_group`, `assemble` (docling) | 1, the one parser a worker holds |

Before the split, one worker took up to 100 Activities from a single queue while running one
docling call at a time: the rest waited inside that process, invisible to Temporal (empty
backlog, healthy heartbeats), unreachable by other workers, and ignoring priority.

## Scenarios and acceptance criteria

Written before the run. Setup: Temporal dev server with one read and one write partition per
task queue, the RustFS S3 stand-in, `tools/fake_admission`, the DEV profile, and every worker a
separate `kp-processing worker --queue …` process, as a pod would run it. Corpus papers by
index (third-party, not in git). A sampler polls every running workflow's pending Activities
(type, state, worker identity) and the `inference` activity backlog every 0.25 s.

| # | Scenario | Acceptance criteria |
|---|---|---|
| S1 | No hoarding: 1 orchestration + 1 inference worker; 3 papers started together | (a) at every sample at most 1 inference Activity is started; (b) at some sample an inference Activity is scheduled but not started while another runs; (c) the `inference` backlog reported by Temporal is above 0 at some sample; (d) all 3 complete |
| S2 | Spread: 1 orchestration + 2 inference workers; 4 papers together | (a) at every sample at most 1 started inference Activity per worker and at most 2 in total; (b) each inference worker completes at least one group; (c) all 4 complete |
| S3 | Priority: 1 orchestration + 1 inference worker; 3 bulk (`low`) papers, then 1 `normal` paper once the first group runs | (a) no bulk inference Activity starts while a normal one is scheduled and waiting; (b) the normal paper completes before the last bulk paper; (c) every normal group waits at most one bulk group's duration + 2 s |
| S4 | Orchestration is not blocked by inference: S1's papers 2 and 3 | `prepare` of every paper completes within 5 s of its start, while the inference worker is busy |
| S5a | Scale-down with grace (SIGTERM, `--shutdown-grace-s 120`): 2 inference workers, one gets SIGTERM while running a group | the running group completes on attempt 1; that worker starts no new Activity after SIGTERM; it exits once the group is done; the paper completes |
| S5b | Scale-down without grace (SIGTERM, grace 0) | the worker exits within 5 s; the cancelled group is retried on the other worker within 10 s of SIGTERM (not after the 60 s heartbeat timeout); the paper completes with `native` equal to an uninterrupted run |
| S6 | Regression | the full test suite passes; [t2-tracer-bullet](../t2-tracer-bullet/README.md) cases A–F still hold with one process per queue |

## Results

Run 999714, 2026-10-31, macOS arm64 (CPU only), Temporal CLI 1.9.1 dev server (Server 1.32.0), with
[scenarios.py](scenarios.py); papers by corpus index 1-4 (28, 22, 25 and 27 pages). All 18
criteria pass. Raw numbers: [evidence.json](evidence.json).

| # | Result |
|---|---|
| S1 | 157 samples: at most 1 inference Activity started at once; in 147 samples one ran while another waited as scheduled in Temporal; the `inference` backlog reached 2; all complete |
| S2 | at most 1 started per worker and 2 in total; the two workers ran 12 and 14 inference Activities; all complete |
| S3 | no bulk Activity started while a normal one waited; normal groups waited 0.87-5.43 s against a longest bulk group of 5.48 s; the normal paper finished 20.52 s before the last bulk paper |
| S4 | `prepare` completed 0.08-0.14 s after each start while inference was busy |
| S5a | the group running at SIGTERM completed on attempt 1 on the leaving worker; it started no new Activity and exited 0.04 s after that group finished (2.4 s after SIGTERM); the paper completed with `native` equal to S1's |
| S5b | the worker exited 0.09 s after SIGTERM; the cancelled group restarted as attempt 2 on the other worker 1.07 s after SIGTERM (no heartbeat timeout); `native` equals S1's |
| S6 | full test suite passes; [t2-tracer-bullet](../t2-tracer-bullet/README.md) A-F rerun with one process per queue: same outcomes, B again recovers from SIGKILL of the inference worker |

Negative control ([control.py](control.py) with [hoard_worker.py](hoard_worker.py)): S1 with
the inference worker's one-slot limit removed. One worker started all 3 papers' groups at once
(max started 3), Temporal's `inference` backlog stayed 0 in all 149 samples, and no Activity
ever waited in Temporal: S1 a, b and c fail. That is the hoarding the split removes, measured
rather than inferred.

The first run of the scenarios read Temporal event times as local time (UTC+8), which broke
S5's comparisons with the SIGTERM clock; this table is from the run after the fix.

Deployment settings this relies on: one read and one write partition per task queue
(priority is ordered per partition, see [priority.py](../t2-tracer-bullet/priority.py)), and
a pod termination grace period longer than `--shutdown-grace-s`.
