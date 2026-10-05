# A4: evidence transport race after two complete fixtures

Executed commit `de8b9e0`, identity `t09b-calibration-20260928-a4`. One
controlled execution; no retry. Readiness PSI, OOM, memory floor, worker cgroup,
deadline and cleanup stops remained strict. Runtime node PSI and object max events
were diagnostic telemetry.

## Result matrix

| Gate | Result |
| --- | --- |
| Local policy regressions and two-axis review | PASS |
| 11 pre-inference gates | PASS |
| Fresh fixture 06 | PASS: complete, 28 pages, 11 components |
| Fresh fixture 07 | PASS: complete, 15 pages, 4 components |
| Fresh fixture 08 | INTERRUPTED during finalize: 12 pages, 9 components |
| Native / final fixture 06 | NOT RUN |
| Full group/recycle/traffic qualification | NOT RUN |
| Cleanup and evidence sealing | PASS |

## Stop cause

The primary error was `ValueError('evidence transport extent changed')`. The
snapshot program recorded a file's size and then performed an unbounded 4 MiB
read. When an evidence file grew between those operations, the read could include
bytes beyond the recorded extent. The transport correctly rejected that
self-inconsistent envelope, but the inconsistency was created by the collector.

The controller raised the transport guard at epoch `1790610828.783444` and then
interrupted the supervisor. Temporal recorded the fixture-08 cancellation at
`2026-09-28T15:53:49.136254833Z` and completed the execution record 10 ms later
with business result `failed / activity_budget_exhausted`,
`processing_complete=false`. The Activity did not fail independently first.

The precise growing file is unknown because the rejected envelope was not retained
and the old exception did not include its path. The regression reproduces the
failure class by appending to `storage.jsonl` between `stat()` and `open()`. The
fix caps each read at the pre-read extent; the next snapshot transports the append.

## Resource evidence

Across 161 outer samples, node full PSI avg10 remained 0, VM OOM remained 0, and
minimum available memory was 2,896,240,640 bytes, above the 1.5 GiB runtime
floor. Object-service maximum memory was 988,205,056 bytes, object max-event delta
was 0, and object full PSI avg10 remained 0. A4 therefore does not test behavior
through a positive node-PSI interval, but it proves the A3 business failure was
not an inherent failure of fixtures 06 or 07: both completed after the former
guard point.

## Cleanup

Forensic export and terminal stop proof completed. All 32 recorded Deployments
are back at zero with matching UIDs, no owned Pod or trace container remains, and
object-service identity/configuration is unchanged. The A4 evidence PVC remains
Bound as `t09b-calibration-a4-evidence-20260928`, UID
`7d5227e9-6219-446a-9e5f-be2227cadc69`.

## Acceptance

A4 is not accepted as the T09b baseline. It completed only two of five fixtures
and did not reach parser recycle, final resource gate, traffic reconciliation or
qualification. A fresh identity is required after the transport-race fix; A4
evidence and prefix remain immutable.
