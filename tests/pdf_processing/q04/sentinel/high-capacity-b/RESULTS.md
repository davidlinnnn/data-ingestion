# High-capacity process-mode Keynote sentinel

**PASS for the bounded Keynote fresh/restored/replay sentinel.** This is not the
completion of Q04 or #51. No other fixture, warm/resource expansion or Pod drain
ran in this window.

## Window and identity

- Runtime source: `18be1b3fbcb929921ec986a1a0bf93e4be995b4d`
- Run ID: `q04-7b4f958ff3ac4e2da5b54dcaa66914b9`
- Object prefix: `q04/keynote-18be1b3-20260916-b/`
- Remote root: `/tmp/q04-keynote-18be1b3-20260916-b`
- Reserved interval: 2026-09-16 15:11:04.397–15:31:04.397 UTC
- Cleanup tail began no later than the reserved 15:26:04.397 boundary
- Actual finish and reservation release: 15:15:28.736 UTC
- Actual lease duration: 264.340 seconds
- Retry count: zero

The new state directory generated a new run ID, three new workflow IDs and a new
prefix. The original packages, 17 model artifacts, platform, Python and frozen
profile matched. The prior failed run was neither resumed nor overwritten.

## Capacity admission and active guards

The outer capacity-owner admission sampled 61 times for 60 continuous seconds.
Minimum available memory was 4,899,463,168 bytes (4.563 GiB), full PSI maximum
was zero, global OOM stayed 28, and maximum coordinator cgroup usage was
1,052,745,728 bytes. This passed the new 4.5 GiB precondition.

Runtime guards remained unchanged: 3 GiB case admission, 1.5 GiB active floor,
3 GiB cgroup ceiling, full PSI zero, unchanged VM/cgroup OOM and maximum
three-second telemetry gap.

| Mode | Accepted | Resource samples | Min available | Max cgroup | Max gap | Max PSI |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| fresh | yes | 142 | 3.135 GiB | 2.481 GiB | 0.512 s | 0 |
| restored | yes | 126 | 4.078 GiB | 1.483 GiB | 0.507 s | 0 |
| replay | yes | 123 | 4.321 GiB | 1.243 GiB | 0.522 s | 0 |

Raw worker samples include the final shutdown observations (144, 127 and 124
rows respectively). Across them, global OOM was always 28 and cgroup OOM-kill
was always zero.

## Delivery, oracle and reuse evidence

All three results have `status=complete`, `processing_complete=true`, one page,
one registered and selected component, and one complete registration. Their
accepted records have `verified=true`.

Each mode produced the same document SHA-256
`893af666a8dac763bd79ed217b3f2defe474af4b9bafed1acecafdf3de8b4c57`
and full reference graph SHA-256
`29a68d6fee00cc663c6cad6c230fc15b66ad98c43326817ba909a2aa3c4e9ba4`.
The oracle counts are 44 items, 27 text boxes, one picture and zero tables, with
the same type distribution in every mode.

Fresh executed group, assembly and component OCR without reuse. Restored reused
group and assembly and reran component OCR against the restored representation.
Replay reused all three stages. Replay used the exact fresh request ID
`q04-d135df990b884ba8aa5553f01aa708c1` and reproduced the fresh plan,
registration identities, document and graph. Restored used its own new request
and representation identities while producing the same document and graph.

`canonical_accepted=false` remains present in these successful parsed-delivery
results; this bounded harness does not claim downstream canonical publication.

## Cleanup and held services

All three owned Temporal workflows were terminal `COMPLETED`. Owner cleanup found
no Running execution, controller, orphan, remaining owned cwd process or scratch.
Workers for generations 1–3 stopped with their parser absent, scratch absent and
no sampler error. T09a Temporal was healthy and idle and object readiness returned
200 after cleanup. An independent post-run probe confirmed the release marker,
available global lock, no owned PID, no scratch and no Running workflow.

The 32 historical Deployments were already paused by main. This runner performed
no scale or restore operation. All 32 retained the expected UID and replicas=0
before and after the run; the sanitized snapshots are byte-identical with SHA-256
`d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4`.
They remain closed for main to manage.

## Evidence boundary

Original evidence is retained at `/private/tmp/q04-keynote-window-20260916-b`.
The immutable remote capture is `remote-evidence.tar`, SHA-256
`df8acbcaee9381af0ac094126f169b2227dd23e47650e5d76997ddc12befc33b`.
It contains all three accepted records, complete registrations, graph and content
checks, Temporal histories, resource samples and cleanup history. Raw documents,
profiles, histories and object payload details remain outside Git. The sanitized
summary and private-artifact hashes are in `evidence/summary.json`.

No production implementation or profile changed, no failed evidence was removed,
and no issue was closed. Main must review this sentinel before scheduling other
fixtures. Pod drain remains separate.
