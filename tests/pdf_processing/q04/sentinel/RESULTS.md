# Q04 process-mode Keynote sentinel result

**Stopped by the capacity guard during fresh; acceptance remains incomplete.**
Runtime source was exactly `18be1b3fbcb929921ec986a1a0bf93e4be995b4d`.
No runtime implementation or frozen profile was changed for this attempt.

## Window and scope

All timestamps below are UTC on 2026-09-16 (Taipei is UTC+8).

| Event | Time |
| --- | --- |
| Reservation/window started | 14:34:42.844 |
| First positive PSI sample | 14:36:59.808 |
| Worker stopped | 14:37:00.311 |
| Original replicas restored and healthy | 14:37:12.241 |
| Reservation released; manager finished | 14:37:12.577 |
| Independent final read-only verification | 14:39:08.880 |
| Reserved cleanup tail would start | 14:49:42.844 |
| Authorized hard deadline | 14:54:42.844 |

The lease lasted 149.733 seconds. Fresh identity, idle and runtime fingerprint
checks preceded the exact 20 Deployment pauses. The Linux coordinator's 112
packages and 17 model artifacts matched the frozen profile. Pre-admission had
61 samples across 60 seconds, minimum available memory 3,844,227,072 bytes.
The adapter also performed its own 60-second admission before fresh.
Only Keynote fixture 10 was processed; init captured the six frozen source objects.
Restored/replay, other fixture processing, invalidation, warm qualification and
Pod-mode drain were not executed. No Deployment was created.

## Failure and acceptance boundary

The 133 worker samples show maximum VM PSI full avg10 **0.18 > 0**,
minimum available memory **2.854 GiB > 1.5 GiB**, and maximum cgroup memory
**1.931 GiB < 3 GiB**. Global OOM-kill count stayed **28**; no cgroup OOM was
reported. The controller's original exception is `ValueError: VM PSI pressure`.
This is evidence of a pressure-guard stop, not an OOM or a memory-floor breach.

Run ID: `q04-96938e514fd84edeb9c2b353aa005c85`.
The only workflow was
`q04-96938e514fd84edeb9c2b353aa005c85-fresh-10-3cf2df798dfe4e1b808638ae31a58613`.
Its history records cancellation requested at 14:36:59.889855551 and Temporal
COMPLETED at 14:36:59.903180301. The application result was **failed**:
`processing_complete=false`, `canonical_accepted=false`, `registered_pages=0`,
`pages=1`, `steps=[]`, error category `infrastructure`, code
`activity_budget_exhausted`. Temporal COMPLETED describes lifecycle only.
That error after cancellation does not establish expiry of the 180-second budget.
No complete graph/oracle/delivery or restored/replay acceptance was obtained.

## Cleanup and restoration

All five adapter failure-cleanup outcomes (cancel, result task, worker stop,
publication audit, history) succeeded; phase cleanup reported no errors.
Worker PID 9592 stopped, parser PID 9625 was absent, and owned scratch was absent.
Owner cleanup additionally enumerated executions by the exact frozen run prefix,
including the submission/recording gap; the only execution was terminal and the
final Running query was empty. No complete publication existed for incomplete
request `q04-169485501dcf48469b9c90be69689bc9`.

The 20 original Deployment UIDs and replicas=1 were restored, each Ready=1.
Post-restore service checks covered all 11 validation namespaces; Temporal had no
Running executions and object health returned 200. Independent final verification
confirmed the release marker, absent reservation holder, available global lock,
no inference/worker PIDs, no scratch and unchanged global OOM count.
There is no outstanding cleanup or pause. No retry is authorized by this report.

## Evidence and reproduction boundary

`evidence/` contains resource metadata, original failure/cleanup outcomes and
sanitized identity/replica verification. `private-artifact-manifest.json` binds
original private files by SHA-256, including raw histories, staging/capacity,
health/fingerprint checks, logs and exact executed helper snapshots.
Original evidence remains at `/private/tmp/q04-keynote-window-20260916-a`;
remote staging is `/tmp/q04-keynote-18be1b3-20260916-a` on the coordinator.
Object prefix is `q04/keynote-18be1b3-20260916-a/` in bucket `t09a`.
The immutable capture `remote-evidence.tar` predates restoration/release; local
lease/final-check evidence records those later events. Raw Deployment specs,
full histories, profiles and PDF/source bytes are not published in Git.
Historical failures are retained. No LaTeX, canonical-schema or generic PDF
quality claim follows from this attempt. Mainline must review results and arrange
any separately authorized future capacity window.

## Offline validation

AST parsing, JSON parsing, the executed helper hashes and all 49 retained private
artifact size/SHA-256 records passed local verification. A final Pyright rerun
was unavailable (`No module named pyright` in the retained Python); no new
runtime behavior is inferred from static checks. The earlier 101-test adapter
suite remains historical evidence in `../PHASE-TWO-RESULTS.md`; it was not rerun
because it includes model inference and this authorization covered one sentinel.
