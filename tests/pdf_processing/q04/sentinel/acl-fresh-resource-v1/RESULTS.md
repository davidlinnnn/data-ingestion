# ACL fixture 09 fresh-only resource calibration v1

**FAIL acceptance; PASS the bounded resource measurement and independent final
cleanup.** The single authorized fresh workflow completed all three pages and two
required OCR components without crossing the provisional 4 GiB sampled cgroup
ceiling. The consumer then rejected the output because its full graph differs from
the frozen reference and page 2 has 69 typed items instead of 68. No retry,
restored case or replay ran. This result does not complete Q04 or #51.

## Window and reviewed identity

- Runner commit: `3fde5e36e0e639112aec54d20c69f574b31247e7`
- Preparation commit: `2a2d8d8`
- Phase: `acl-fresh-resource-v1`
- Fixed path identity: `20260917`; actual execution date: 2026-09-18 Asia/Taipei
- Reserved interval: 2026-09-17 22:45:12.122–23:10:12.122 UTC
- Runtime launch: 2026-09-17 22:46:13.042 UTC
- Per-case admission passed: 2026-09-17 22:47:15.135 UTC
- Collector stopped after cleanup: 2026-09-17 22:47:36.039 UTC
- Runner finalization: 2026-09-17 22:47:40.849 UTC
- Independent post-release verification: 2026-09-17 22:49:25.720 UTC
- Retry count: zero

The preflight matched the reviewed Pod UID, container ID, restart count, start
time, boot ID and PID 1 start ticks. VM and cgroup OOM-kill counters were zero.
Python 3.12.13, 112 packages, 17 model artifacts, the producer, fixture-09
profile, bundle and frozen state matched with no package or model difference.
T09a was healthy and idle, object readiness returned 200, all new paths were
unused, and all 32 historical Deployments had their expected UIDs with
`replicas=0`, `ready=0` and no matching Pods.

The bundle SHA-256 remained
`b729891aa381ae25eef6ec2fbceefcdb43703d441762eafbb388627792833297`;
the frozen state SHA-256 remained
`6f83b29e73357e6576643948f18f0be2d461ae7285e433f2c810c5f8d4aca5b7`.

## Admission and active guards

Outer admission passed 61 samples over 60.714 seconds with 60.702 continuous
seconds and no reset:

| Measurement | Observed | Guard |
| --- | ---: | ---: |
| Minimum available memory | 9,480,679,424 B (8.830 GiB) | at least 4.5 GiB |
| Maximum cgroup usage | 2,189,733,888 B (2.039 GiB) | at most 4 GiB candidate |
| Maximum full PSI avg10 | 0 | 0 |
| VM/cgroup OOM-kill | 0 / 0 | unchanged at 0 / 0 |

The worker then passed per-case admission with 121 samples over 60.391 seconds:

| Measurement | Observed | Guard |
| --- | ---: | ---: |
| Minimum available memory | 9,336,369,152 B (8.695 GiB) | at least 3 GiB |
| Maximum cgroup usage | 2,321,952,768 B (2.162 GiB) | at most 4 GiB candidate |
| Maximum full PSI avg10 | 0 | 0 |

Across the complete worker lifetime, 163 guard samples recorded a maximum cgroup
value of 3,733,815,296 bytes (3.477 GiB), minimum available memory of
7,897,296,896 bytes (7.355 GiB), full PSI avg10 of zero, maximum gap of 0.508
seconds and unchanged VM/cgroup OOM-kill counters. The 4 GiB candidate ceiling,
1.5 GiB VM floor, PSI, OOM, telemetry and deadline guards did not fire.

## Fresh delivery and oracle boundary

Fresh request `q04-46a0bd74a5064bb1af1a6e912dbf8768` used a new versioned
fixture object, version `25106ff1-270d-4628-a18f-9f328b3d9d01`. Workflow
`q04-7b4f958ff3ac4e2da5b54dcaa66914b9-fresh-09-52c5a5c8d9d442b8a24c4d974a1f5320`
reached Temporal `COMPLETED` and returned `status=complete`,
`processing_complete=true`, three registered pages and two selected/registered
components. Both required component OCR steps returned `text_detected`. The
result retained `canonical_accepted=false`, as required before consumer review.

All delivery, provenance, page evidence, relationship binding, required-work and
OCR attribution checks before the full-reference comparison passed. The full
graph comparison then failed:

- expected graph SHA-256:
  `32e9eed4fa46748f5d8f509687a448f94633926ad826c59efc4ea93941cf7783`;
- actual graph SHA-256:
  `c4f4b0153258d03cc3e67f5bca3e8b9ccf13b16ceeb2a7963a49b110e6f8bff2`;
- changed collections: `body`, `groups`, `texts`;
- added/removed source-signature segments: zero / zero.

A read-only diagnostic over the retained durable output did not override that
rejection. It found all six reviewed equation IDs, equation 2 backed by a
`TextItem`, and three representation observations. Page 1 matched 40/40 typed
items and page 3 matched 21/21. Page 2 contained 69 items against the frozen 68,
so the full typed-coverage oracle failed. The extra item shifts later positional
comparisons; the retained graph and source evidence require review before any
reference update. Fresh is therefore **FAIL** despite the successful workflow
lifecycle and complete resource trace.

| Mode | Result | Evidence boundary |
| --- | --- | --- |
| Fresh | **FAIL** | Full graph and page-2 typed coverage differ from frozen oracle |
| Restored | Not run | Outside this fresh-only authorization |
| Exact replay | Not run | Outside this fresh-only authorization |

## Resource decomposition

The auxiliary collector retained 323 complete samples over 82.437 seconds. No
sample had missing or permission-denied fields. The maximum interval was 0.261
seconds against the 1-second contract. Sampling took 4.084 ms on average, 5.961
ms at p95 and 8.674 ms maximum; summed sample time was about 1.60% of the covered
wall interval.

| Point | cgroup `memory.current` | Owned PSS | Diagnostic residual |
| --- | ---: | ---: | ---: |
| Before worker | 2,248,318,976 B (2.094 GiB) | 78,110,720 B (0.073 GiB) | 2,170,208,256 B (2.021 GiB) |
| Sampled maximum | 3,851,812,864 B (3.587 GiB) | 1,996,055,552 B (1.859 GiB) | 1,855,757,312 B (1.728 GiB) |
| After owned cleanup | 2,281,771,008 B (2.125 GiB) | 115,320,832 B (0.107 GiB) | 2,166,450,176 B (2.018 GiB) |

At the sampled cgroup maximum, `memory.stat` recorded 1,644,310,528 bytes anon,
2,124,513,280 bytes file and 67,268,608 bytes kernel. The largest individual
process-class observations were parser PSS 1,345,460,224 bytes, owned-descendant
PSS 603,068,416 bytes, worker PSS 85,642,240 bytes and controller PSS
115,320,832 bytes. These class maxima are not simultaneous and must not be
summed. The parser's own guard reported peak RSS 1,398,568 KiB (1.334 GiB).

Cleanup `memory.current` was only 31.902 MiB above the before-worker sample. A
later independent sample was 2,205,659,136 bytes (2.054 GiB). The residual mostly
tracks shared file/cache/kernel charges and timing skew; it is diagnostic only.

`memory.peak` began at 3,457,347,584 bytes and ended at 3,937,529,856 bytes. It is
the shared cgroup's lifetime high-water mark and was never reset. It is **not**
reported as this run's peak. The run-scoped high-water observation is the
3,851,812,864-byte maximum of this run's `memory.current` series. This one trace
does not establish production sizing or a Pod limit.

## Cleanup and final verification

The phase-level cleanup succeeded: result-task settlement, worker stop,
publication audit and history capture were all `ok`; worker PID 799 stopped,
parser and scratch were absent, and sampler errors were empty. Attribution was
complete with no collector error.

The generic owner-cleanup command returned nonzero because it also scanned three
stale historical fixture-10 workflow files whose IDs were no longer present in
Temporal. This made the runner correctly retain `cleanup_verified=false` and
`measurement_passed=false`. That error did not identify a live resource from the
current attempt: the current fresh workflow was `COMPLETED`, and the same report
found no Running workflow, orphan, remaining owned cwd PID or scratch.

An independent post-release check then passed all current-run cleanup assertions:
the global and v1 driver locks were available; no owned process, Running owned
workflow or scratch remained; the exact reservation had a release marker; VM and
cgroup OOM-kill remained zero; boot/PID 1 and frozen-state identities were
unchanged; T09a was healthy and idle; object readiness was 200. All 32 historical
Deployments remained closed and no matching Pod existed. The before/after
Deployment snapshots are byte-identical with SHA-256
`d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4`.

## Evidence and remaining scope

Original and derived evidence is retained at
`/private/tmp/q04-acl-fresh-resource-20260917-v1`. The immutable remote capture is
`remote-evidence.tar`, 3,184,640 bytes, SHA-256
`403572ecd268e5abf47fe56430762b4274867bbca0e2da03ef1bbffa68eb985a`.
The original runner manifest SHA-256 is
`2782f41758d39ef15c083ecb33cba20efc6dd6acb9a56eabcdfda4279dffcd3c`.
The 21-file post-review manifest SHA-256 is
`98f7f4330906e80cc45710af6b5fa57b737058fd92eb18e02c277f4530dfeddb`.
Sanitized results and selected hashes are in `evidence/summary.json`; raw samples,
histories, documents, profiles and environment inventories remain outside Git.

The consumed phase, paths, reservation and driver-lock identity must not be
reused. A later task may review the page-2 graph/typed-item delta and narrow the
owner-cleanup audit to current owned IDs while retaining historical evidence.
There is no authorization here to change the frozen reference, production
processing, the 4 GiB candidate, or to run restored/replay/another fixture. No
issue was published, merged or closed.
