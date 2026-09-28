# #44 resumed round — capacity admission blocked

Baseline: `0b537d06476f0b547c8428b2e0bfda5f08dcfd3e`. Historical partial
snapshot `863d2d1` is preserved unchanged. **#44 remains PARTIAL/OPEN.**

## Actual acceptance matrix

| Item | This round | Evidence / remaining condition |
|---|---|---|
| Clean branch fast-forward and spec reconciliation | PASS | Integrated baseline; original evidence untouched |
| Retained OOM trace attribution | PASS as diagnosis | [Diagnosis](DIAGNOSIS.md), matched three global-OOM events, exhausted swap, aggregate service/Python RSS; no proven leak or 5 GiB breach |
| Current resource admission | FAIL / workload refused | [Admission log](evidence/admission-red.log); initial VM MemAvailable 1.635 GiB < provisional 3 GiB minimum |
| Capacity candidates and persistence impacts | READ-ONLY COMPLETE | [Candidates](evidence/capacity-candidates.json); main awaiting user authorization, no other namespace changed |
| Old drain reconciliation | CONFIRMED FAILED | [Business result](evidence/old-workflow-result.json): infrastructure/activity_budget_exhausted, 51 pages registered; no resume or termination by this round |
| AIMA association localization | REPRODUCED RED | [Rule replay](evidence/source-red.log), exact Linux rule hash and checkpoint digests; upstream merge cause reproduced |
| Other AIMA type/caption/inequality acceptance | OPEN | Present before assembly; complete root causes not isolated; [decision options](SOURCE_OPTIONS.md), no parser/profile changes authorized this round |
| R2 controller static correctness | PASS for reviewed changes | Scoped Pyright; independent Standards/Spec rechecks resolved identified findings |
| Restart-aware guard / cleanup runtime | PARTIAL / UNRUN | Actual admission rejection path exercised; model-active sampler failure and fault cleanup not yet exercised |
| Same fixed warm sequence / planned recycle | UNRUN | Must pass admission and small preflight; prior warm failure is not superseded |
| Long drain / replacement / complete proof | UNRUN | New gated-replacement controller prepared; prior failure remains a gate |
| Compatible old groups on new request | UNRUN | Prepared to reuse old 51 registered pages under new request/release, not poll old queue |
| Exact accepted-request replay after replacement | UNRUN | Prepared with same frozen release and required fresh baseline |
| Full regression suite in R2 harness | UNRUN | Integration's 10-test PASS does not substitute for this controller |
| Supported file/page/pixel/resource envelope | OPEN | No new inference measurements; admission threshold is not a support claim |

The old drain Workflow naturally closed at **2026-09-13 15:29:04 UTC**. Its Temporal
status is COMPLETED because the Workflow returned an explicit business failure.
This supersedes the old report's then-current `assembling`/queued snapshot, while
preserving that historical observation. Registered outputs remain in the original
object store. No old accepted request was executed on the integrated producer.

## Prepared controlled execution

Default run identity is `20260914-0b537d0-a`; `T09A_R2_RUN` chooses another identity
when explicitly creating another run. Queues, coordinator code/results and deployment
names are run-bound. The first setup freezes complete effective Pod specs, package,
profile, worker/gate and resolved immutable image identities before any apply.
Changed release bytes/settings require a new run identity. Original ConfigMaps,
requests and `t09a/evidence` are not overwritten.

All controller modes acquire `/private/tmp/data-ingestion-pdf-qualification.lock`.
Cleanup confirms absence of owned r2 Pods **and** running CRI containers, even when
admission fails. Initial/replacement Activity polling waits until a valid sample
exists; fresh/warm comparisons cannot silently skip missing baselines. Monitoring
checks VM OOM counters, headroom, Pod identity/restarts and samples through completion,
including final checks before acceptance. Warm cases also check between-trial Pod
identity and OOM counts. These implementation claims have static review; runtime
qualification is explicitly pending.

After main coordinates capacity, first rerun admission-only mode:

```sh
python3 tests/pdf_processing/t09a_r2/run.py admission
python3 tests/pdf_processing/t09a_r2/run.py preflight
```

Only after the small Keynote case is evaluated should the fixed fresh, warm,
compatibility, replay and fault windows proceed. Each window rechecks admission;
all expensive work stays serialized. Proposed sequence:

```sh
python3 tests/pdf_processing/t09a_r2/run.py fresh native 06 07 08 09 10
python3 tests/pdf_processing/t09a_r2/run.py warm
python3 tests/pdf_processing/t09a_r2/run.py compatibility
python3 tests/pdf_processing/t09a_r2/run.py replay native 06 07 08 09 10
python3 tests/pdf_processing/t09a_r2/fault.py
```

`full_suite.py` requires the retained prototype Python and holds flock while reaping
owned descendant processes. Do not run it during another qualification window.
Evaluate actual source oracles, planned-recycle observations, all registered-work
proofs and sampling coverage before labelling any runtime row PASS. A failure stops
the sequence for diagnosis, not automatic repetition or silent limit increases.

Current pending external action is main's user authorization for reversible pause
of historical T03–T07 Deployments. No namespace/PVC deletion or VM change is proposed.
The candidates' dynamic/external consumers cannot be completely excluded by a Pod
environment scan, and only main may reconcile their owners. T09a services, originals,
producer configs and data remain retained.
