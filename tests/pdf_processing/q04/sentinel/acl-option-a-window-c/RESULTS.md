# ACL fixture 09 Option A window c

**PASS for the bounded fixture 09 fresh, restored/new-request and exact-replay
window.** This is not completion of Q04 or #51. No other fixture, warm/resource
phase, Pod drain, publication or production change ran.

## Window and identity

- Runner commit: `857f0a6f1764ee95a06e6d4b63ccf8b2c095ea55`
- Runner SHA-256 staged in the coordinator:
  `f24a45f2c0452065654b7a90386299575e2d6db39d76a49cb9d84338e1d11a50`
- Run ID: `q04-41aad36cffde419b95f92ba48b8abf26`
- Phase: `acl-option-a-window-c`
- Object prefix: `q04/option-a-20260918-c/`
- Remote root: `/tmp/q04-option-a-20260918-c`
- Reserved interval: 2026-09-18 12:18:48.234–12:43:48.234 UTC
- Outer admission completed: 12:19:51.935 UTC
- Cleanup began: 12:23:27.652 UTC
- Finish and reservation release: 12:23:31.932 UTC
- Actual duration: 283.697 seconds
- Retry count: zero

The runner created a new run ID, state and versioned source objects. It did not
copy historical registrations or reinterpret an old request. The retained old
Keynote request still resolved under its original prefix and its original
`native-v1` profile/release before the new root was claimed. The old frozen state
SHA-256 remained
`6f83b29e73357e6576643948f18f0be2d461ae7285e433f2c810c5f8d4aca5b7`.
The new state remained
`2a3264316e0a859b2a490b3724af09c2df16959b35d9c8116b02e078f50f0636`
through cleanup.

## Capacity and active guards

Outer admission passed without reset after 61 samples and 60.664 continuous
seconds. Minimum available memory was 9,208,561,664 bytes (8.576 GiB), maximum
coordinator cgroup use was 2,279,366,656 bytes (2.123 GiB), full PSI stayed zero,
and VM OOM-kill remained zero.

Per-case admission stayed at 3 GiB/60 seconds. The active cgroup ceiling stayed
at 4 GiB, the active memory floor at 1.5 GiB, full PSI at zero and the telemetry
gap bound at three seconds.

| Mode | Accepted samples | Raw samples | Min available | Max cgroup | Max gap | Max PSI | OOM |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| fresh | 169 | 170 | 7.071 GiB | 3.676 GiB | 0.508 s | 0 | VM/cgroup 0 |
| restored | 129 | 130 | 8.085 GiB | 2.486 GiB | 0.508 s | 0 | VM/cgroup 0 |
| replay | 124 | 125 | 8.305 GiB | 2.276 GiB | 0.508 s | 0 | VM/cgroup 0 |

## Delivery, oracle and reuse evidence

All three records have `verified=true`, `status=complete`,
`processing_complete=true`, three registered pages, two selected/registered
components and complete required OCR. Each produced the exact adopted document
SHA-256
`ff3cdcb6142e7046f5e248827548a1cd303f68c9317b2488d9dd251805c3f506`
and full graph SHA-256
`c4f4b0153258d03cc3e67f5bca3e8b9ccf13b16ceeb2a7963a49b110e6f8bff2`.
The shared checks record contains 134 items, two pictures, no tables and six
reviewed equation occurrences. Consumer verification passed the adopted
40/69/21 page-item oracle for processed pages 1–3, mapped to original pages 2–4.

Equation 2 is preserved as `#/texts/94`, label `text`, with its equation text and
page-2 provenance. The other equation occurrences retain their actual types;
all six have source-reviewed regions. Both selected pictures completed OCR with
`text_detected`. The result includes two captions, 14 typed relationships and
five dependency records, and preserves the three documented representation
uncertainties without rewriting their text.

Fresh used a new request and ran group, assembly and both OCR components without
reuse. Restored used a distinct new request over the same versioned source,
reused group and assembly, and reran both required OCR components. Exact replay
used the exact fresh request ID, source version, plan, registrations, document,
relationships and content evidence; group, assembly and both OCR components were
all reused. The restored document and graph also equal fresh despite its distinct
request/plan identities.

`quality_accepted=false` and `canonical_accepted=false` remain explicit. This
window proves the fixed fixture09 qualification contract and does not make a
general PDF-quality or canonical-publication claim.

## Cleanup and held services

All three owned Temporal workflows are `COMPLETED`. Workers for generations 1–3
stopped with parser and scratch absent and no sampler errors. Owner cleanup found
no controller, orphan, unexpected process, remaining scratch, Running workflow
or cleanup error.

The 32 historical Deployments retained the reviewed UIDs and stayed at
`replicas=0`, `ready=0`. Before and after snapshots are byte-identical with
SHA-256
`d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4`.
The runner did not restore them.

An independent post-run read confirmed the release marker, dead reservation PID,
free global lock, no process with cwd under the owned root, no Running workflow,
phase-complete marker, empty phase-cleanup errors, healthy Temporal, object
readiness 200 and unchanged zero VM/cgroup OOM-kill counters.

## Evidence boundary

Original local evidence is retained at
`/private/tmp/q04-acl-option-a-window-20260918-c`. The immutable remote capture is
4,894,720 bytes with SHA-256
`6eae970bc2811073bd0b80bc4e20f78eebc1ec28f7921580f382068bbc474596`.
It contains accepted/results/checks/documents, registrations, graph/content
evidence, Temporal histories, raw resource samples, worker stop records and
cleanup evidence for all three modes. The independent post-run probe SHA-256 is
`2222ea62e4fbe16f40bbb8d461df08fd0b956ed9a7e426304832ac82a33fbd13`.
Private raw profiles, documents, histories and telemetry stay outside Git;
sanitized facts and artifact hashes are in `evidence/summary.json`.

The earlier argument-validation failure record remains unchanged. No issue was
published or closed, and no push or merge occurred. Main must independently
review this bounded PASS before scheduling any other fixture or Q04 phase.
