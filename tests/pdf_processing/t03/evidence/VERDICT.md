# T03 recovery evidence

Implementation tests passed against the final immutable code snapshot. Mandatory
two-axis review is still pending; do not close the implementation ticket yet.
This report is not approval for production HA, warm lifecycle or canonical delivery.

## Proven against the isolated real services

- Real selected-provider checks passed: missing registration; committed corrupt or
  missing payload; malformed/duplicate manifests; two concurrent differing attempts
  return the same single winner; divergence records; retained orphan inventory;
  bounded/incomplete inventory; logical capacity threshold; actual write response
  loss after remote acceptance; zero-upload reuse; real invalid credentials/bucket;
  refused endpoint classified as transient storage rather than cache miss.
- Real Temporal synchronous Activities remain alive after start-to-close timeout.
  Explicit synchronization establishes retry-before-old-publication ordering. The
  retry wins the differing-output race and the old producer returns that winner.
  Activity acknowledgement loss reuses the registration. A separate terminal-failed
  Workflow stays failed even after its old attempt publishes reusable output; a
  new Workflow can reuse that output. Temporal's rejected late completion logs are
  expected evidence, not ignored execution errors.
- Production Processing, through real Temporal, reports configuration and committed
  integrity errors, including tampering between resolution and consumption, as permanent failures with exactly one Activity attempt and zero
  registered pages.
- Three real ten-page native PDF requests survived Activity Pod deletion during
  second-group processing, after payload upload but before registration, and after
  registration before Activity acknowledgement. In all cases the first five-page
  group was captured once. The second group had two capture starts for processing
  and upload loss, one for acknowledgement loss. Each accepted group records five
  inputs for each applicable page stage; assembly has zero repeated page inference.
  All ten independently specified literal page labels survived. Subsequent whole
  requests reused every operation with zero upload bytes and identical parsed-result
  references. The final upload-loss case added 11,194 orphan bytes; the observed live prefix
  retained 22,388 orphan bytes including the preceding qualification run.

- Final regression passed nine input/queue rejection cases and request-identity
  conflict; three-page literal native output and the exact historical 51-page
  document digest; all 14 operations reused after worker replacement with zero
  upload bytes. The unchanged two-page scanned baseline/capture/fresh-restore test
  passed in 34.010 seconds, with exact JSON equality and zero repeated page stages.
- All five accepted fault/native plans and their 23 operations match every frozen
  production source hash. Final workers use the immutable t03-package-qualified
  ConfigMap; code source and driver hashes accompany this evidence. Scratch was
  empty after the final run. Static type checking and whitespace validation pass.

## Measurement and fixture limits

Processing loss is signalled only after a real page-stage event. A tiny group may
finish before the external Pod deletion, so the test wrapper holds it before
publication. This covers native work plus unregistered-group recovery, not arbitrary
instruction-level kills. Capture starts and accepted stage inputs are measured;
exact native work completed before interruption is not observable.

Upload loss is between artifact PUTs, not a packet-level or multipart transmission
interrupt. The explicit old-alive timeout harness uses small byte producers so it
can independently verify late-attempt ordering without expensive inference. It
supplements the real PDF Pod tests. A failed preliminary harness run revealed that
sleep-based ordering could select either correct winner; it was replaced with
explicit synchronization, not a weakened production assertion.

Object-store application immutability uses conditional writes; the validation root
credentials can intentionally tamper with objects for corruption tests. Production
permissions/retention policy remain later deployment work. No object is repaired or
GC'd. Inventory is nontransactional, bounded, live-version-only, and reports a byte
lower bound rather than physical/PVC capacity. Exact orphan counts require quiescence.

The pinned MinIO and Temporal image IDs are recorded in runtime.json. Service PVCs
remain in `pdf-t03-validation`, with bucket `t03` and isolated prefixes. Worker-Pod
replacement does not establish storage-node, disk-loss, or HA durability. The pinned
Docling runtime is Linux ARM64; no cross-architecture or language claim is made.

## Integration notes

Store call shapes remain compatible. `StoreFailure(category, code)` and
`read_artifact` are additive; Processing adds the corresponding permanent/retryable
failure mapping. Execution changes only materialization integrity, group validation
and assembly coverage before publication. It does not change the child interface,
Workflow ordering, OCR selection, warm lifecycle, or stage-scoped method identity.
T04's Workflow tail and T05's child runner must retain these narrow validation and
error changes during integration. A merged branch must be revalidated separately.
