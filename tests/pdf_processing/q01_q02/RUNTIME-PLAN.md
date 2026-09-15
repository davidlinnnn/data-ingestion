# Joint Q01 + Q02 runtime acceptance plan

This is a plan, not an executed result or authorization to change shared services.
Driver preparation is now implemented: see `DRIVER.md` for cases A–D and the
parameterized E matrix. Runtime admission and all measured outcomes remain open.
Authority: #48, #49 and specification #47. Q03 symbol decisions and Q04 broad
cross-fixture/recovery qualification are separate. One coordinating owner runs the
serial matrix; original sessions can assist with harness preparation but must not
submit competing heavy workloads.

## 1. Prepare the driver before reserving runtime

Extend the full-request Q01 driver into a separate combined acceptance harness.
Keep the original historical drivers/results intact. It must:

- Use actual `PDFProcessing` and production Activities for prepare, native groups,
  assembly, selection, actual selected OCR, evidence and finalization. No seeded
  upstream registrations in full-request scenarios.
- Take endpoints, bucket, private prefix, model cache, profile and fresh output
  directory explicitly. Run with bounded deadlines and cleanup of owned workers,
  port-forwards and children. Do not rely on the Q02 hardcoded local endpoints.
- Apply both continuation opt-in and Q02 selected-region relationship policy to
  the same frozen profile. BFS/uniform-cost selections are independently declared
  fixture qualification inputs, not runtime algorithm answer tables. Retain the
  existing source-bound reviews and captured original-source artifact references.
- Re-freeze the complete producer, runtime packages/models, helper hashes, profile,
  worker release and fresh request identities AFTER any production change. Do not
  reuse Q01's recorded Linux release or Q02's original producer manifest as-is.
- Resolve final document, evidence and relationships from shared storage; score
  the actual delivered corrected document using Q01's reviewed continuation and
  Q02's independent source-role/caption oracle. Check all required artifacts and
  unchanged false canonical/quality acceptance flags.
- Assert selected OCR count is greater than zero and each selected component has
  a completed, readable real OCR output. Empty selection is not proof of OCR.
  If the pinned chapter produces none, stop that acceptance claim and plan a
  separate explicitly declared source-bound case; never silently seed OCR.
- Record full histories, attempts, completed/reused stages, request/run/queue IDs,
  producer/profile hashes, object versions and artifact digests. Publish only
  metadata reports; keep PDFs, extracted text and page images private.

Use mocks/checkpoint replay and typechecking to validate driver assertions first.
The runtime driver's continuation oracle presently requires a merged item. That
matches this implementation; a future permitted separate-edge representation must
get its own independently justified oracle rather than relaxing checks silently.

## 2. Admission and bounded environment

Acquire the existing shared qualification lock and inspect actual capacity,
service health, bucket versioning, pinned input/model availability, architecture,
package fingerprints and owned queues before submission. Record CPU/memory,
page/pixel/group/concurrency limits and stop thresholds from the supported existing
configuration. Do not invent new sizing bounds from earlier sampled maxima.

Retain serial Activity admission initially. A local host worker connected to remote
Temporal/storage proves that topology only. For a cloud-native claim, run the
frozen producer in an isolated K8s worker environment and record image/Pod identity;
do not call a macOS worker run K8s qualification. Select and document the topology
before freezing the profile. Fail admission if the chosen environment cannot fit.
No historical Deployment pause is authorized by this plan. If more capacity is
needed, identify the concrete services/impact and obtain a new coordinated window.

## 3. Serial matrix and acceptance mapping

| Case | Required proof | Ticket |
| --- | --- | --- |
| A: fresh pinned AIMA 99–110 | New versioned full request; no imported group/assembly registrations; corrected continuation plus two independently scored relationships on final output; actual selected OCR and all required artifacts complete/readable | Q01, Q02 |
| B: new request, same frozen method | Checked group/assembly reuse reported by real execution; relation report bound to the new request and exact result; continuation/structure still pass; no false old-request reinterpretation | Q01, Q02 |
| C: exact-request retry | Durable replay returns correct stable complete identity and readable artifacts; no duplicate or prematurely complete delivery | Q02 |
| D: evidence-only policy variant | Freeze a new accepted request/profile with unchanged parse method and dependency contract, an explicitly different allowed evidence policy, and equal checked parse/assembly contracts; observe real reuse and changed evidence/final identity. Score the required two structures where selected coverage is promised | Q02 |
| E: final-boundary failures/unknown | Re-run the lightweight Q02 29-case matrix on the combined producer with parameterized isolated endpoints/prefixes. Required corrupt/missing outputs and missing OCR prevent complete; allowed unknown evidence persists before success. Clearly label these as seeded fault-injection cases | Q02 |

For B/D distinguish same-process warm use from fresh-process restoration. Include a
fresh worker/process boundary and verify checked store reuse; if warm behavior is
claimed, record a separate same-worker request. Merely comparing dependency dicts
is not runtime reuse. D may change `reject` to `allow_unknown` within selected
coverage while retaining the same source regions; it must still produce and score
the two required structures for this fixture, not use unknown mode to avoid them.

The initial combined method intentionally invalidates the historical baseline.
Do not resume old accepted workflows on new bytes. A comparison against an old
method needs its retained producer; do not build a fake baseline registration.

A full Pod drain/loss and six-fixture matrix remain Q04 responsibilities after
Q03. If any prerequisite acceptance/review exposes a recovery defect, record it
and fix/retest the affected boundary before closing the relevant ticket. Do not
claim Q04's complete matrix from these cases.

## 4. Stop, cleanup and report

Stop on resource/telemetry admission failure, unexpected policy fallback, missing
required OCR/relationship, mismatched producer, wrong continuation or corrupt
registration. Preserve failed trials separately. Clean up only this run's workers,
children/port-forwards; verify no owned work is still running, restore explicitly
authorized temporary changes, then release the lock. Keep persistent evidence.

Report A–E separately with PASS/FAIL/NOT RUN, topology and evidence links. Close
#48 only after its complete-delivery and reuse conditions pass; close #49 only
after full native/OCR/reuse plus publication conditions pass and main review is
reconciled. Publish/integrate through main coordination, then unblock Q03. Do not
close #44 or #51 from this window. If tests require production edits, re-freeze
identity and repeat only affected cases with preserved earlier evidence.
