# T10 / #46 bounded release verdict

**PASS for the declared local Processing Completion release package**, evaluated
2026-10-01 UTC / 2026-10-02 Asia/Taipei. Target is `dev`, baseline PR #66
`cf29cae13b5b84a0f859ac35e2586427e7d1a24b`. Parent #33 remains open.

Candidate image:
`docker.io/library/pdf-t10-core@sha256:7f7ff771e4411544d43a9fd60c6b6c0e6b2280351373f7ed47f28fa849082924`.
The cached qualified ARM64 base is digest `8ffaac39462e…`; the package was built
offline and imported into kind/containerd. Registry distribution is not qualified.
All 21 producer files exactly match the accepted #43/#44/#45 manifest; the image
also contains the final worker/operator/bootstrap/profile bytes. See
[RELEASE.json](evidence/RELEASE.json) for complete hashes, routes and measurements.

## Seven acceptance conditions

| #46 | Result and delivery |
| --- | --- |
| 1. Deployment consistency | `release.py` freezes one image, method/profile, limits/store binding and seven explicit queues. Inactive immutable ConfigMap plus Workflow/serial Activity Deployments; group5, one parser, recycle20, 30s drain/60s Pod grace. Startup checks exact runtime/packages/17 models and inherited per-supervisor THP disable. [Runbook](../../../deploy/pdf-processing/RUNBOOK.md) covers source bootstrap, deployment and recovery. |
| 2. Candidate evidence / uncovered interactions | D/E/F/G use the same final image. New serial-worker normal native/OCR completion, exact replay, input failure, assembly/finalize loss, container restart, reviewed-profile rollout and late old-route isolation/recovery pass. F's full AIMA document is exactly equal to the latest accepted #45 A12 full document, with all 12 pages/nine OCR components/required relationships complete. Source producer hashes preserve the remaining #43/#44/#45 evidence; full calibration is not repeated. |
| 3. Existing operational evidence | Actual running/completed/failed summaries retain stage, attempts/reuse, child lifecycle, timestamps and error category/code. Final manifests and checked artifact references are exportable. Existing bounded inventory reports registrations, orphan estimates and capacity status without deletion. No new observability system. |
| 4. Current object service | Reused real-store contract verifies conditional single winner, visibility, corruption/missing payload rejection, divergent/orphan outcomes, lost write ACK, intact reuse and bounded access/configuration/unavailable failures. UID-precondition enforcement was first proved on an owned disposable Pod. Quiescent MinIO Pod replacement took 0.769s against the retained 120s bound; Deployment spec/UID and PVC remain. Both synthetic and reviewed adopted references resolve afterward. Node/disk loss, HA, retention policy and production capacity remain gates. |
| 5. Integration handoff | Actual captured requests, completion/failure summaries, reviewed final manifest and adopted-reference inventory are in [RESULTS.json](evidence/RESULTS.json). [HANDOFF.md](../../../deploy/pdf-processing/HANDOFF.md) maps them to #31/#32. Processing Completion includes all required work; `canonical_accepted=false` and `quality_accepted=false` remain explicit. |
| 6. Cleanup / retained references | Exact container restart increases restart count while retaining Pod UID; owned scratch is removed and unrelated sentinel remains. Checked references resolve after worker and store restart. All owned Pods, running CRI containers, worker/parser/observer processes are absent. Historical Deployment specs/UIDs, PVC and object prefixes are preserved. No shared GC or checkpoint projection. |
| 7. Release verdict / downstream gates | This verdict, runbook, internal operator and sealed evidence define the bounded release. HTTP admission and canonical mapping/validation remain #31/#32; custody and migration follow #52/#57 and related tickets. No `main` publication, parent closure or full production-readiness claim. |

## Measured limits and qualification boundaries

The selected configuration and rejection limits remain those in
`../t09b/SUPPORTED-CONFIGURATION.md` and `SUPPORTED-BOUNDS.json`: group5/single
parser, 100MiB/51 pages/20M rendered pixels, four CPU threads, 5GiB hard worker
limit and 4GiB sample guard. These are not generic input support or capacity targets.
The runtime holds one business request at a time; fleet admission and capacity
remain with overall design #52/#54. Small manifest scheduling requests do not
reserve the monitored VM budget. Runbook preconditions remain mandatory.

D/E/F/G/H provide 1,573 continuously sampled rows; maximum gap 0.264s, minimum VM
available 5,647,552,512 bytes, maximum charged worker memory 1,764,216,832 bytes,
at most one parser, zero worker full PSI and zero VM/worker/object OOM. Node PSI
is retained telemetry under #45's approved policy (maximum observed avg10 0.36).
The old object container reached 1,073,414,144 of 1,073,741,824 bytes; cumulative
full PSI increased 682us in H while full avg10 stayed zero and max/OOM deltas stayed
zero. This near-limit measurement is retained, not described as headroom or HA.

The D prefix inventory lists 458 current objects / 86,731,397 bytes, 79 valid
registrations, 370 registered artifacts and 45,581 orphan bytes. Its 1GiB test
threshold is not exceeded. It is a non-atomic current-version prefix inventory;
historical versions and physical disk capacity are excluded. The retained PVC
declares 2GiB; that request does not establish a filesystem quota or free capacity.
The adopted references checked after restart number 22 synthetic / 45 reviewed.

This is interaction verification, not the #45 sustained 825-second calibration
window, a platform pressure test or a production capacity certification. All
source-reviewed original bytes were newly captured into the release prefix,
digest-checked and bound before profile B rendering; historical originals stay
where they were. Source review scope and original-page maps remain unchanged.

## Local validation and retained failures

Scoped typecheck: zero errors/warnings. All package tests pass. A broad isolated
local regression ran once: 33 of 41 modules / 77 tests in passing modules passed,
including all 25 current T09b modules / 60 tests. Eight historical Q02/Q03 modules
failed due to absent retained private fixtures, SDK environment dependencies or
an old pre-continuation-v3 assertion. All eight were rerun against the exact
unmodified `dev` baseline and fail identically. This is **not** a claim that the
whole historical suite is green. No historical test/evidence was rewritten to
hide those results; full native calibration and unavailable old checkpoint replay
were reused from accepted evidence.

[INDEX.json](evidence/INDEX.json) seals raw histories, manifests, node/object
samples and validation logs by path/digest/size. It retains attempts A–H, including
startup parser admission, missing inherited THP, fault-selector, ineffective PID1
injection, original-prefix, stale-reference and JSON evidence-format failures.
After fixes, only changed/uncovered interactions ran: D's normal/loss evidence,
E's restart, F's complete reviewed result, G's read-only graph/late-route recovery,
then H's storage-only continuation. H activated no PDF worker. Earlier prefixes
and evidence remain; there is no automatic run retry or production gate waiver.
