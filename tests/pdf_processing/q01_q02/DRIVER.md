# Joint runtime driver — prepared, not runtime qualified

> Runtime status update: see [2026-09-16 results](RUNTIME-RESULTS.md). Historical preparation findings below are retained; the bounded A–E matrix has now passed after the documented hash correction.

The driver and offline oracles are ready for capacity admission. No actual native,
OCR, Temporal or storage experiment was executed while preparing this driver.
Production remains the combined source inventory in `evidence/producer.json`.

## Full-request cases A–D

Use `runtime.py` here. Start each case in a new Python process on the same qualified
runtime environment, serially: `fresh`, `reuse`, `exact`, `evidence`. This provides
fresh-process checked restoration, not a same-process warm-state claim.

Required arguments:

- `--profile`: runtime-matching frozen Q01 opt-in profile. Continuation method/hash
  must already match; native package/model fingerprints must match that runtime.
- `--producer`: `evidence/producer.json` or a newly reviewed exact producer manifest.
- `--pdf`: original pinned contiguous AIMA derivative, SHA checked by driver.
- `--model-cache`, `--temporal`, `--endpoint`, `--bucket`: explicit runtime resources.
- `--prefix`: unused private namespace for fresh, identical for later cases.
- `--out`: a different nonexisting private directory per case.
- `--topology`: honest environment description, including immutable image/Pod or
  host identity. A host-worker result is not K8s qualification.
- `--case`: one of the four cases above.
- `--fresh-evidence`: fresh case's `accepted.json`, required for subsequent cases.
- `--timeout`: positive workflow time limit in seconds (default 1800).
- `--capacity-approved`: acknowledgement of an already coordinated window; this
  switch itself grants no authority to pause services or change resource limits.

Run with the actual qualified Python and source/dependency paths. `--help` is safe
before admission. Do not execute with `python -O`, since acceptance uses assertions.
The driver acquires the shared local qualification lock, creates a unique queue,
uses serial Activities, has a server workflow deadline and cancellation on local
wait failure, and shuts down its Worker context. In K8s, coordinate admission
externally as well: a Pod-local lock is not a cross-Pod lease.

It applies the independently frozen BFS/uniform-cost selected-region policy to
this fixture, retains source reviews, captures original-source bytes if required,
and records the final profile/release hash before submission. For evidence-only,
only the allowed unresolved disposition changes; both structures must STILL pass.
Old profiles/registrations are not rewritten. The acceptance output is written
only after final assertions succeed. Admission, workflow history and result logs
remain private and distinct from PASS output. On infrastructure timeout, cancellation
is requested; verify owned workers/children have exited before releasing the actual
capacity reservation. No automatic shared Deployment or data cleanup is performed.

Assertions cover corrected continuation plus the independent two-algorithm oracle
on the same delivered document, exact source/result binding, nonempty selected OCR
with real fresh Activity execution, readable durable output bytes, nonempty parsing
stage observations, expected checked reuse, stable exact-request final identity,
and changed evidence/final identity on new requests. Claims of actual reuse or OCR
remain NOT RUN until these commands execute successfully in the selected topology.

## Seeded fault matrix E

Use the separately retained `tests/pdf_processing/q02/runtime.py`. Connection
configuration is now explicit via environment variables:

`Q02_ENDPOINT`, `Q02_TEMPORAL`, `Q02_BUCKET`, `Q02_PREFIX`, `Q02_OUTPUT`,
`Q02_CAPACITY_APPROVED=1`; optional `Q02_TIMEOUT_SECONDS` (default 1800).

Credentials remain in the existing private AWS environment, never in evidence.
The prefix and output must be new; bucket versioning is checked. It runs serially
under the same local lock and bounded outer timeout. Its 29 scenarios still seed
upstream fixtures: report this as final-boundary fault injection, never as full
native/OCR processing. Run using the SAME combined producer as A–D. Historical
Q02 commands without these variables intentionally no longer submit a workload.

## Offline preparation evidence

`test_runtime_contract.py` tests positive joint delivery on actual corrected
checkpoint assembly and rejects original/corrupt output, empty OCR, missing
parsing stages, missing OCR stages and false reuse. Together with the two earlier
integration tests: 4 PASS. No model inference is performed.
Expanded production/driver/test typecheck: zero errors/warnings. CLI help was
checked without contacting services. Actual worker shutdown, admission capacity,
full native/OCR delivery and A–E outcomes remain to be measured.
