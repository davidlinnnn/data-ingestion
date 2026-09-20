# Q04 current acceptance matrix

Current through P execution `ed393ad`; machine authority:
`evidence/current-acceptance-matrix.json`. A proven row applies only to its exact
producer, profile, runtime and acceptance policy. Historical evidence cannot
silently qualify a changed execution path.

## Fixture delivery

| Fixture | Scope | Fresh | Restored | Exact replay | Full graph/oracle | Q04 fresh index |
| --- | ---: | --- | --- | --- | --- | --- |
| native | 51 pages | unproven | unproven | unproven | unproven | unproven |
| WikiSkill `06` | 28 pages | unproven | unproven | unproven | unproven | unproven |
| YOLO `07` | 15 pages, M policy | **proven** | **proven** | **proven** | **proven** | **proven** |
| AIMA `08` | original 99–110 | unproven | unproven | unproven | unproven | unproven |
| ACL `09` | original 2–4 | **proven** | **proven** | **proven** | **proven** | **proven** |
| Keynote `10` | one page | **proven** | **proven** | **proven** | **proven** | **proven** |

YOLO M (`d1701d3`) passed all three modes with 15 pages and four required OCR
components, approved two-pair graph equivalence, `max_requests=1`, THP-disabled
workload descendants and 1,021 complete process samples. This is bounded fixture07
acceptance, not the original request20 cross-document warm qualification.

AIMA N completed 12 pages and nine required OCR components, but the original
consumer rejected 21 added image fields. The Q01 checkpoint-only reference has
no images. Offline source-pixel checks explain all additions and prove every
other projected field equal, and the user subsequently adopted the image supplement. Two PSS samples
remain unknown and the measurement observation-order assertion also failed.
Restored/replay did not run and no fresh index was promoted. See
[N results](pod-topology-v13/first-window-evidence/RESULTS.md) and the
[inactive proposal](diagnosis/aima-n/PROPOSAL.md).

ACL and Keynote retain their passes under their original producer/runtime
identities. Applicability to the current lifecycle producer is **unproven**.
Q03 AIMA source/oracle evidence remains a historical reference; current lifecycle
execution, reuse and interruption behavior require requalification.

## Cross-cutting gates

| Gate | Current status | Boundary |
| --- | --- | --- |
| Immutable source/producer/profile/method/oracle binding | proven | Exact retained run identities |
| Stage-impact dependency projection | proven | Existing local audit; new producer changes need their own impact record |
| Six-fixture current-producer matrix | unproven | Native/Wiki/AIMA and lifecycle applicability remain open |
| Current AIMA continuation/four algorithms | unproven | P content checks pass; final resource qualification remains incomplete |
| Current evidence-only compatible reuse | unproven | Q03 proof belongs to its original execution path |
| Real assembly/method invalidation | unproven | Native runtime not run |
| Old request original route | proven | ACL window c re-read retained Keynote binding |
| Changed profile rejects old request | unproven | Local compatibility only |
| Current required-relationship interruption/retry/replay | unproven | Q03 historical owned-child proof, not current lifecycle/Pod recovery |
| Fixed warm sequence and request20 recycle | unproven | Per-document assembly handoff reaps warm parser; original requirement unchanged |
| Original ACL/Keynote bounded process resources | proven | Exact small-fixture producer/runtime only |
| Integrated operating bounds | unproven | M proves fixture07 policy only; N attribution incomplete |
| Active telemetry-loss guard | unproven | Current runtime phase not run |
| Process drain/recovery | unproven | Current runtime phase not run |
| Pod drain/recovery | unproven | UID-fenced terminal cleanup proven; in-flight Pod loss/recovery not run |
| Supported-bounds report to #44 | unproven | Depends on remaining rows |

## Stop-cause and evidence record

- H: dropped rejecting sample and `worker-1.log` cleanup crash repaired in I.
  Recovered history indicates PSI cancellation; true Activity budget exhaustion
  is not demonstrated. The exact original trigger row remains unavailable.
- I: scratch/durable transport classification failure; evidence recovered.
- J/K: business cases complete but process attribution incomplete. Root runc
  initializer reads were traced to repeated execs, including readiness probes.
- L: persistent observer lanes and startup-only probe made all 290 process
  samples complete; real node PSI then stopped fresh. Concurrent THP allocation
  and direct reclaim are observed, but THP causality is not proven.
- M: all three bounded fixture07 cases and unchanged resource gates passed.
- N: completed AIMA business result, then consumer graph rejection and incomplete
  measurement contract. No PSI/OOM/deadline trigger; no automatic retry.

All historical failures, raw evidence, PVCs and prefixes remain retained. N's
41 sealed inventory entries / 42 archive files passed independent verification;
owned runtime is removed, Temporal idle and all 32 held Deployments still off.
See [M results](pod-topology-v12/first-window-evidence/RESULTS.md),
[N results](pod-topology-v13/first-window-evidence/RESULTS.md) and retained A–L
records under `sentinel/` and `pod-topology-v*/`.

## Next execution

O failed because oracle data were not projected; P repaired the projection and
completed all three AIMA business/content cases. P's final resource qualification
failed on one process-enumeration transition out of 961 samples, so fixture08
remains unproven as an integrated gate and no fresh index was promoted.
See [P results](pod-topology-v15/first-window-evidence/RESULTS.md).

Next repair the reproduced cross-document warm lifecycle defect and improve
transition observability, then test source projection, contracts, interruption
and cleanup and review before a new uniquely identified controlled runtime.
Do not reinterpret P's unknown PSS or weaken original request20/guard requirements.

#51 is not ready for integration/closure. Ticket updates remain unpublished drafts.
