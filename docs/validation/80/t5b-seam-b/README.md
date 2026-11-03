# #155 Seam B: the Document Summary in the platform, on Claude Sonnet 5.5

`run.py` runs the corpus papers through the real stack with the DEV profile
(`tests/profiles/paper-pdf-dev.yaml`): Temporal dev server, the RustFS S3 stand-in,
`tools/fake_admission`, and one `kp-processing worker` process per queue. The summary worker
calls `anthropic/claude-sonnet-5-5` through Anthropic's OpenAI-compatible endpoint (B4); the VLM
is t4's local stand-in, so the summary is the only external request. Only the 20 public corpus
papers may be sent to the provider.

## Scenarios and acceptance criteria

| # | Scenario | Acceptance criteria |
|---|---|---|
| S | One paper, fresh bucket | exit 0; summary `success` (or a recorded failure reason); each overview sentence cites at least one summarized Section; every summarized Section listed in reading order; every published sentence verified; every summary send ok |
| C | A second request for the same document, same bucket | exit 0; no summary request; the summary reused; nothing new under `documents/` |
| F | BIG (paper 20, 16 chunks) and SMALL (paper 8, 12 pages); fairness on in the server; `summary_concurrency_per_document` 16 so BIG's chunks queue behind the worker's 5 slots | BIG had at least 3 chunks waiting when SMALL's `summary_sections` was scheduled; at most 2 BIG chunks started while SMALL had a summary task queued |
| F-off | F with fairness off in the server (negative control) | the same backlog; at least 3 BIG chunks started while SMALL waited, so the measurement can see a document waiting |

## Prompts: development set and freeze (C3)

The dev set (papers 2, 4, 20, 16, 6) ran first. One change came from it: verify and repair now
see the paper's title, so a sentence may name the paper's method by it. Before that change, a
Section that never names its own system ("The section never names the system SkillOpt") had its
sentence rewritten. The prompts were frozen at commit 2f3d78f. All 20 papers then ran on the
frozen prompts (run `frozen-1`, 2026-11-04); the figures below are from that run. Accuracy and
rewrite/drop ratios are reported for the 15 held-out papers, with the dev set listed separately.

## Result

S and C pass on all 20 papers. Every summary is `success`, status `unverified`. All 1,025
summary requests returned ok: none unavailable, invalid or refused. Each C took 0.6–1.9 s.

| | Held-out (15) | Dev (5) |
|---|---|---|
| Summary time, first summary Activity scheduled to overview completed: min / median / max | 22.6 / 29.6 / 45.6 s | 20.6 / 48.7 / 60.3 s |
| Document wall clock, min / median / max | 36.0 / 48.9 / 71.5 s | 31.3 / 71.5 / 88.7 s |
| Summarized Sections (with a sentence target) | 611 (436) | 164 (128) |
| Chunks | 119 | 51 |
| Section sentences kept / rewritten / dropped | 638 / 38 / 3 (rewritten 5.6 %, dropped 0.4 % of 679) | 231 / 20 / 3 (7.9 %, 1.2 % of 254) |
| Overview sentences kept / rewritten / dropped | 98 / 2 / 0 (2.0 % rewritten of 100) | 38 / 1 / 0 (2.6 % of 39) |
| Cost at US$2 / US$10 per million input / output tokens | US$4.84 | US$2.05 |

Requests and tokens per step:

| Step | Held-out calls | prompt / completion tokens | Dev calls | prompt / completion tokens |
|---|---|---|---|---|
| map | 118 | 433,316 / 69,005 | 51 | 191,277 / 24,461 |
| verify | 578 | 887,535 / 98,807 | 191 | 379,640 / 38,904 |
| repair | 43 | 57,415 / 13,154 | 24 | 45,976 / 8,051 |
| reduce | 15 | 79,487 / 11,456 | 5 | 29,451 / 3,980 |

Verify accounts for about 61 % of the prompt tokens: each Section's batch and each overview
sentence is judged against its Sections' full text (D4).

Per paper (`evidence-INDEX.json`):

| Paper | Set | Sections (with target) | Chunks | Requests | Summary s | Section kept / rewritten / dropped | Overview kept / rewritten / dropped | US$ |
|---|---|---|---|---|---|---|---|---|
| 1 | held-out | 46 (29) | 9 | 50 | 29.0 | 50 / 2 / 0 | 7 / 0 / 0 | 0.36 |
| 2 | dev | 29 (18) | 4 | 30 | 20.6 | 25 / 1 / 0 | 5 / 0 / 0 | 0.18 |
| 3 | held-out | 50 (31) | 8 | 53 | 29.6 | 40 / 3 / 0 | 7 / 0 / 0 | 0.33 |
| 4 | dev | 34 (25) | 11 | 54 | 48.7 | 41 / 5 / 0 | 7 / 0 / 0 | 0.40 |
| 5 | held-out | 52 (36) | 8 | 66 | 33.8 | 46 / 7 / 0 | 7 / 0 / 0 | 0.37 |
| 6 | dev | 30 (29) | 11 | 61 | 54.1 | 52 / 3 / 2 | 7 / 1 / 0 | 0.46 |
| 7 | held-out | 24 (17) | 6 | 35 | 26.3 | 26 / 3 / 0 | 5 / 0 / 0 | 0.22 |
| 8 | held-out | 29 (21) | 4 | 35 | 27.9 | 24 / 1 / 1 | 5 / 0 / 0 | 0.20 |
| 9 | held-out | 48 (37) | 8 | 61 | 31.7 | 49 / 4 / 0 | 7 / 0 / 0 | 0.34 |
| 10 | held-out | 43 (30) | 10 | 49 | 37.2 | 55 / 0 / 0 | 8 / 0 / 0 | 0.35 |
| 11 | held-out | 36 (26) | 7 | 42 | 29.6 | 32 / 1 / 0 | 6 / 0 / 0 | 0.28 |
| 12 | held-out | 31 (25) | 8 | 43 | 26.8 | 44 / 0 / 1 | 7 / 0 / 0 | 0.31 |
| 13 | held-out | 52 (38) | 11 | 67 | 40.8 | 57 / 4 / 0 | 9 / 0 / 0 | 0.43 |
| 14 | held-out | 22 (21) | 6 | 39 | 27.6 | 33 / 3 / 0 | 5 / 0 / 0 | 0.25 |
| 15 | held-out | 50 (34) | 8 | 62 | 38.4 | 39 / 6 / 1 | 6 / 0 / 0 | 0.39 |
| 16 | dev | 25 (18) | 9 | 38 | 29.9 | 38 / 2 / 0 | 6 / 0 / 0 | 0.28 |
| 17 | held-out | 33 (22) | 7 | 36 | 22.6 | 36 / 1 / 0 | 5 / 0 / 0 | 0.23 |
| 18 | held-out | 40 (22) | 6 | 40 | 31.5 | 28 / 2 / 0 | 4 / 1 / 0 | 0.25 |
| 19 | held-out | 55 (47) | 13 | 76 | 45.6 | 79 / 1 / 0 | 10 / 1 / 0 | 0.52 |
| 20 | dev | 46 (38) | 16 | 88 | 60.3 | 75 / 9 / 1 | 13 / 0 / 0 | 0.73 |

Paper 16 has 64 pages but 48k summarized characters: its appendix is mostly code listings and
plots, which a Section's text leaves out (v2 Q6).

## Fairness (F, F-off)

| | BIG chunks waiting when SMALL's `summary_sections` was scheduled | BIG chunks started while SMALL had a task queued | SMALL's time in the queue | Pass |
|---|---|---|---|---|
| F (fairness on) | 10 | 1 | 7.2 s | yes |
| F-off (fairness off) | 10 | 9 | 23.2 s | yes (the control sees the wait) |

With fairness on, dispatch alternates between BIG's and SMALL's chunks once SMALL's arrive: the
one BIG chunk that passed SMALL started 3.3 s after SMALL's chunks were scheduled, and the next
dispatched chunk was SMALL's. With it off, the queue is first in, first out: SMALL's
`summary_sections` waited 9.6 s behind BIG's queued chunks, and SMALL's chunks started only
after all 16 of BIG's had. So a small document's summary need not wait for a large one's, provided the
server has fairness on (the PROD Temporal configuration must set `matching.enableFairness`).

The F design took several runs to get right; the early runs are not evidence:
- The first runs started SMALL after BIG had finished, because `t4.run_case` blocks the event
  loop. BIG now runs on its own thread.
- Then SMALL's chunks came after BIG's backlog had drained: SMALL's parse waited for BIG's local
  enrichment on the one inference slot. The F case adds a second inference worker, and SMALL is
  the shortest paper.
- Measuring only SMALL's first chunk missed the wait in `summary_sections`, which is where
  fairness off makes SMALL queue.

## Cost (C3)

The dev-set run, the frozen 20-paper run, the F runs and the C1 judge calls came to about
US$21 of Claude tokens, under the US$40 stop. The gpt-6-luna planting (C1) cost under US$0.10.

## Not covered

- The PROD model (company VLM) is #137; the DEV model here is Claude Sonnet 5.5.
- A summary past its budget, and a chunk Activity retried after a worker loss, are covered at
  Seam A and in `tests/test_workflow.py`, not here.
