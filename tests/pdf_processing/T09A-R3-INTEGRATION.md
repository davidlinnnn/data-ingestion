# Main reconciliation of T09a R3

Reviewed and integrated on 2026-09-14:

- R2 diagnosis: `b32bb583a5c134bb3863501974ee63d452c56f68`.
- R3 capacity-window evidence: `d1f148f52df9bc974e5693e74f4d21fe414fe252`.
- Production baseline remains `0b537d06476f0b547c8428b2e0bfda5f08dcfd3e`.

Main accepts the bounded resource/recovery evidence in [R3's report](t09a_r3/README.md).
This is not overall #44 completion: AIMA source quality remains open, and the
measurements do not establish a general production resource envelope. #45 remains
blocked pending #44 acceptance; no support scope or dependency is waived.

## Main checks

- All 61 R3 sealed file hashes matched, resolving paths relative to `t09a_r3`.
- Production `src` and `deploy` are unchanged from the integrated baseline.
  R3 does not modify the historical T09a or R2 snapshots.
- The matrix and execution proofs agree on six fresh complete results, five warm
  complete results, six exact replays and the new-request compatibility result.
  Complete processing retains `canonical_accepted: false`.
- All six replay final identities match their fresh baselines and every recorded
  replay step is reused. Warm observations contain 29 group requests: PID 50 for
  the first 20, PID 1902 thereafter, with the planned recycle counter advanced.
  Child lifecycle counters are distinct from Kubernetes container restarts.
- The drain controller proves five registered pages before injection, only range
  6–10 at attempt 2, all other groups at attempt 1, readable registered payloads,
  full-document equality, old runtime stopped and old scratch absent.
- The active-telemetry-loss guard is an expected failure/cleanup test. The first
  source-prefix failure and the rejected pressure admission remain separate from
  later successful trials; they are not counted as successful document processing.
- Recorded full suite: 10 passing tests. Recorded scoped Pyright: no errors or
  warnings. Existing independent review corrections and their limits were read.
- The final restoration audit records all 20 original Deployments desired/ready
  at one replica, healthy services, no owned Pods or running CRI containers on any
  node, and an available qualification lock. This is the captured end-of-window
  audit, not a new live cluster inspection.

These are code/evidence cross-checks, not a rerun of inference or fault experiments.
Original uncommitted main-checkout edits were preserved byte-for-byte as a git diff
through the fast-forward integration.

## Interpretation and next decision

The approved pause of twenty historical Deployments enabled this fixed serial
profile to pass fresh/warm, recycle, reuse/replay, telemetry-loss guard and bounded
drain/recovery checks. Sampled cgroup maximum 2.452 GiB and warm minimum VM
MemAvailable 1.583 GiB describe this arrangement; neither is a safe sizing bound.

The remaining product-quality decision is documented in
[R2 source options](t09a_r2/SOURCE_OPTIONS.md): versioned upstream association or
layout changes need their own compatibility and cross-fixture acceptance. Preserve
raw source evidence and the current AIMA RED cases. Successful equality/resource
checks do not resolve algorithm/caption/inequality or paragraph/margin semantics.

This reconciliation integrates locally. It does not publish, update GitHub tickets,
close #44, restart workers or change parser/profile/resource settings.
