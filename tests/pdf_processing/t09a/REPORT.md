# T09a / #44: partial qualification, open gates

The complete-result and evidence checks below produced useful bounded results.
**This is not an overall PASS.** The required AIMA associations remain unqualified,
the mixed warm sequence suffered three global OOM container kills, and the drain
test was interrupted after its replacement also suffered global OOM. No stable warm
resource envelope, converter continuity, configured-limit support or quality acceptance
is established. `processing_complete` is distinct from `quality_accepted` and
`canonical_accepted`; both acceptance fields remain false.

## Scope and results

The predeclared [plan](PLAN.md) used integrated T07 commit
`765d5483a61f8648f015e2f7f5538c54b62b6198`, five-page groups, one execution slot,
the existing ARM64 Linux runtime, and v3 `required_evidence_v1` through real Temporal
and the shared object store. PDFs, full parsed documents and crops remain private.
[Source metadata](evidence/sources.json) fixes original and derivative hashes,
page maps, inventories and reviewed regions. No whole AIMA book was parsed.

| Workload | Pages | Typed items / required OCR | Observed outcome |
|---|---:|---:|---|
| Native arXiv fixture | 51 | 1187 / 7 | Clean fresh complete; recovered warm output identical |
| WikiSkill | 28 | 526 / 11 | Full 188-cell source audit passed; warm outputs identical |
| YOLO | 15 | 281 / 4 | Full 60-cell audit passed with declared source U+0002 disposition; warm identical |
| AIMA original 99–110 | 12 | 612 / 9 | Original finalization failed on zero-area marks; evidence fix completes with unchanged raw document; source-quality gates open |
| ACL original 2–4 | 3 | 133 / 2 | Six equations, including TextItem equation 2, and audited typed text/captions/order passed |
| Keynote original 1 | 1 | 44 / 1 | All 27 source textboxes passed |

[Trial summary](evidence/trial-summary.json) records durations and full-document
digests. Fresh native took 140.79 s; WikiSkill 80.40 s; YOLO 52.24 s. These are
observations, not throughput commitments. Every successful result includes all
required OCR dependencies, source/page evidence integrity and retained typed content.
Each trial's JSON retains accepted plan/profile/producer, storage I/O observations,
Temporal scheduling/attempt history, native stage events, actual method/package/model
fingerprints, and OCR dimensions/scale/timing. Native stage sums are not wall time;
warm `metrics.json` counters can cover converter lifetime, so use per-operation
`native_events` for stage attribution. Historical reused stage artifacts describe
their original producer execution, not newly executed inference.

## Source-quality findings

AIMA source revision is `Artificial Intelligence - A Modern Approach (3rd Edition).pdf`;
original SHA-256 is `0609d012bf123d210c3587d1c1610074f5079217a996299123a2f7872f28a8e9`.
The contiguous 99–110 derivative hash is
`b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980`.
The raw assembled document digest remains
`148dc52eff91f8c4d991345fcb4d75ed3b3afacb938f85003f8651fae336502a`.

Original 103 ends a sentence with “second path”; original 104 continues with
“to Bucharest with cost”. Actual `#/texts/127` instead joins page-103 prose
charspan `[0,548]` to the page-104 margin label `DEPTH-FIRST SEARCH`, span
`[549,567]`. The expected continuation is retained separately at `#/texts/131`.
This verified association loss in contiguous context supersedes the hypothesis
that it was solely caused by a non-contiguous derivative. Raw JSON is unchanged.

The [four algorithm audits](evidence/evidence-08-quality.json) assess actual
retained content and relationships, not CodeItem count alone:

| Original page / figure | Actual disposition | Source sequence and relationship |
|---|---|---|
| 101 / 3.11 breadth-first | TextItems 43–63, including section-header 45; caption 64 retained | Complete sequence matches after whitespace-only comparison; declared CodeItem/caption relationship absent |
| 103 / 3.14 uniform-cost | Header merged into prior-page prose at TextItem 109; body CodeItem 113; caption 114 separate | Header's own provenance span plus body matches complete source sequence; code caption link absent |
| 107 / 3.17 depth-limited | CodeItem 300 links caption 301; U+0338 isolated as TextItem 299 | Caption relationship retained; complete symbol sequence differs from native transcript; source native layer itself emits U+0007 for a visual inequality |
| 108 / 3.18 iterative-deepening | TextItems 310–314, including isolated U+0338; figure description 315 is TextItem | Declared code/caption relationship absent; inequality sequence remains uncertain |

The raw split/merged text is retained. Source-native equality does not establish
indentation, execution semantics or mathematical fidelity. Both fresh and warm AIMA
audits keep the source-quality gate open.

## Narrow evidence fix and producer transition

The old producer rejected two in-page, zero-width combining marks at original
107/108. The fix accepts only positive-height, in-page, combining-only TextItems;
it preserves the raw zero-width geometry and emits full-page context with explicit
uncertainty. It does not claim a localized glyph crop, associate the mark with an
operator, change a type, or rewrite text. Zero-area regions cannot satisfy reviewed
formula overlap. Ordinary zero-width text, zero-height/reversed/outside regions,
and zero-width review annotations remain rejected.

The actual complete-result regression reused all native groups and assembly from
the failed AIMA request under a new accepted request. Raw-document equality,
both uncertainty observations and full-page recipes passed
([assertions](evidence/evidence-fix-checks.json)). The real Temporal/store
[geometry regressions](evidence/geometry-negatives.json) passed all 12 cases;
negative cases failed permanently on attempt 1. This qualifies the narrow evidence
behavior separately from the unresolved source associations.

Original native/WikiSkill/YOLO results retain the baseline producer fingerprints;
later evidence results retain the changed evidence producer. No historical result
was relabelled. The supported OCR render-scale-4 transition used a new request,
reused every native group and assembly, and produced 11 actual OCR reports at scale 4
with identical full document ([checks](evidence/profile-transition-checks.json)).
Exact-request replay after replacement is **unrun/deferred**, including replay of
the old failed AIMA request on its exact original producer.

## Resource and recovery gates

Fixed Activity limits were 5 GiB / 4 CPU; requests 256 MiB / 100m CPU;
scratch emptyDir size limit 2 GiB. Processing limits were 100 MiB source,
51 pages, 20M pixels/page, 540 s child and 30 s preflight; warm maximum requests 20,
startup 120 s, no-progress 180 s. Drain/TERM/reap/Pod grace was 30/5/5/60 s.
These were experiment settings, not qualified maxima or tuned recommendations.

The complete clean native sampling interval had 154 application-cgroup samples,
maximum gap 1.08 s, sampled current peak 1.844 GiB and scratch logical peak
125.4 MiB. Nineteen separate kubelet whole-Pod samples peaked at 1.738 GiB.
Different sampling frequencies explain why those observations need not order as
simultaneous measurements. They are not a bound on unseen spikes. The one-container
application cgroup is not substituted for whole-Pod memory. Kernel `memory.peak`
is lifetime-cumulative; sampled `memory.current` covers only its interval.

The mixed sequence WikiSkill → YOLO → AIMA → native → WikiSkill completed with
full JSON equality, **but not uninterrupted**. Same Pod UID
`07f37963-511d-4f1d-abe8-0886e9e4cb83` had three OOMKilled/137 restarts:

| Trial | Kernel OOM time UTC | Retried Temporal work |
|---|---|---|
| warm-1-07 | 14:35:49 | Assembly 1–15, attempt 2 |
| warm-3-native | 14:38:35 | Native group 36–40, attempt 2 |
| warm-4-06 | 14:40:56 | Native group 21–25, attempt 2 |

[Kernel attribution](evidence/oom-attribution.json) matches exact Pod/container IDs
and reports `global_oom`, `CONSTRAINT_NONE`. This supports node-wide OOM classification;
it does not establish a 5 GiB cgroup breach, a leak, or a sole competing workload.
Samplers died with containers, leaving missing tails of approximately 44, 98 and
86 seconds. Their peaks do not bound those trials. Actual parser observations show
no planned max-request recycle; converter continuity/recycle qualification failed.
The original harness continued after sampler loss; it now records sampler exit,
rejects incomplete/restarted measurement and quiesces before ending the sequence.
That guard correction is statically reviewed and typechecked, **not runtime-tested**.

The drain test stopped a real TableStructureModel child on page 6 after five durable
pages, then deleted its owned Pod gracefully. The old Pod disappeared after about
31.3 s and a different UID replaced it. The replacement suffered global OOM at
14:48:22 UTC. The controller was interrupted; its finally retained flock until all
owned Activity Pods disappeared. Independent CRI inventory confirmed no owned running
Activity containers. Latest retained workflow progress was `assembling`, 51 registered
pages; it is queued work, not a completed result. Final equality, the complete
attempt/reuse proof and old scratch-removal assertion are **not passed**.
[Partial controller record](evidence/drain-native-controller.json) and
[last workflow state](evidence/last-active-workflow.json) remain available.

Earlier API/interference trials are [explicitly excluded](evidence/interruptions.json).
Full raw host/node/cgroup series remain private with [hashes](evidence/private-observation-hashes.json).
[Measurements](evidence/measurements.json) expose gaps/restarts; legacy controllers
did not emit an affirmative continuity field, so the summary does not auto-qualify
their samples. Retained node-wide memory/load is not an exclusive-host experiment.

## Runtime attribution and next steps

All retained successful-trial Pod snapshots show CRI repo digest
`pdf-t08-runtime@sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`.
CRI image inspection resolves that repo digest and mutable `linux-v2` tag to the
same content ID `sha256:60b91ce18ac0ef8d4efdec17e79946278f44f62c9fc346b7e19214d8b8ad10ce`,
ARM64 Linux ([mapping](evidence/image-attribution.json)). The apparent ID discrepancy
is resolved for these observed Pods; it is not evidence of changed runtime bytes.
Unobserved intervals in the earlier interrupted trials remain excluded. Package,
model and module hashes are independently retained per accepted plan and native
artifact; the intentional evidence-code transition remains separate.

Main reconciliation should choose the smallest next work:

1. Diagnose retained node-global OOM records and competing memory before any new
   load; then requalify the same fixed warm sequence on an explicitly controlled
   capacity window with restart-aware continuous monitoring. Do not silently raise
   limits, tune recycle or infer a leak from these records.
2. Reconcile the AIMA source expectation gap: investigate the upstream association
   and algorithm type/caption handling in a separate scoped follow-up, or explicitly
   retain the unsupported quality gate. Preserve the raw typed graph either way.
3. Only after resource reconciliation, finish bounded drain/replay checks and the
   inference-containing full regression suite. Configured maxima, deadline exhaustion,
   long-run stability, production storage durability/HA and downstream canonical
   acceptance remain outside this evidence.

No push, merge, image mutation, broad parser repair or issue closure was performed.
See [review and validation](REVIEW.md) for passed and deferred checks.
