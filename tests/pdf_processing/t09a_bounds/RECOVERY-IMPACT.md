# OCR policy changes and inherited Q04 recovery evidence

Review date:2026-09-28. This record compares the accepted BH producer with the
combined production source integrated by PR62 at57fcc2e. It does not relabel
historical AS/AU/BE/BH executions as new-source or normal-32-on executions.

## Actual change and compatibility

The production diff after the already-reviewed b98f510 correction contains
only two OCR policy changes: d1ed706 sets NUMPY_MADVISE_HUGEPAGE=0 before OCR
child imports and preserves that environment when adding the lifecycle FD;
970f28c sets RapidOCR ONNX intra-op pools to4. Parser conversion, capture/restore,
continuation, models, crop geometry, graph rules, retry/publication order,
heartbeat, cancellation, deadlines and process-group reap logic are unchanged.
The earlier warm-child error-classification correction is covered separately
by [its impact record](../q04/POST-BH-PRODUCER-IMPACT.md).

The existing compatibility.dependencies boundary was inspected with retained
AH/AS/AU/BE/BH SOURCE-MANIFEST producer maps and the current DB profile. Changed
files are execution.py,ocr.py,warm_child.py; group,assembly,ocr and evidence
producer projections change. Selection/finalize direct producer projections
are unchanged, but their upstream input identities still propagate. No old
accepted request may be silently resumed under the new worker binding. Its
original route remains its original route; current requests use current
producer identities. No fingerprint bypass or new checksum scheme was added.

## Applicability and limits

| Gate | Retained proof | Effect of the OCR changes / present boundary |
| --- | --- | --- |
| Required relationship interruption and replacement/replay | AS, [v44 result](../q04/pod-topology-v44/first-window-evidence/RESULTS.md) | The interrupted evidence child and fail-closed publication/retry path are unchanged. OCR environment and threads alter allocation/execution cost; they do not change accepted-plan or complete-result publication. AS remains an original-source runtime observation. |
| Active telemetry loss | AU, [v46 result](../q04/pod-topology-v46/first-window-evidence/RESULTS.md) | Sampler staleness, controller cancellation and rejection of a completed-but-failed business result are unchanged. Current guard/handoff and observer-loss regressions supply local checks, not a new injected-loss runtime. |
| Worker-process drain/recovery | BE, [v56 result](../q04/pod-topology-v56/first-window-evidence/RESULTS.md) | Warm native parse, registered-group reuse, attempt2 retry, replacement and scratch cleanup are unchanged. The later OCR stage executes with new policies; BE is not a measurement of new-policy resource cost. |
| Activity Pod loss/recovery | BH, [v59 result](../q04/pod-topology-v59/RESULTS.md) | Deletion after five pages, old runtime absence, replacement attempt2 and publication logic are unchanged. Its finite300s budget and paused32 topology remain explicit; no new32-on recovery-capacity guarantee is inferred. |
| Successful current-policy OCR and full outputs | [actual OCR regression](ocr-thread-probe/production-regression/README.md), [DB result](normal-topology-db/first-window-evidence/RESULTS.md) | Real ONNX sessions used4 threads; full OCR component/crop comparisons passed. DB all five full document/checks equal accepted fresh AI/AJ references and29 groups/recycle20 completed. DB used managed low and had an auxiliary observer failure, so it cannot qualify the native permanent setting. |
| Current native object setting and normal32-on window | DD single execution, strict PSI failure | Rollout/replacement/readback passed;27us new object full PSI stopped the native window. Full business/resource/terminal qualification and permanent adoption failed. |

The existing OCR-child environment regression checks both direct and lifecycle
wrapped children, verifies the parent environment is preserved and confirms
non-OCR children keep their previous environment. Current-source targeted checks PASS: OCR wrapped/unwrapped environment;
fresh-child double cancellation/reap, isolation between two executions and
process-group cleanup; warm restore assertion classification and cancellation
before rebuild (six existing tests total). The first test commands had module/
class lookup errors; the corrected paths/classes ran these cases. The legacy
accepted-plan test could not import locally because botocore is absent from the
available venvs; it was not reported as a PASS. No dependency was installed.
The existing dependencies() contract was instead checked directly against all
five retained producer maps: [projection audit](recovery-dependency-impact.json)
PASS. Original-route rejection remains historical AK evidence plus unchanged
load-plan code, rather than a new execution of that legacy test.

DD passed rollout/replacement/readback, then stopped on27us new object full PSI.
Native ended with10/51 pages and processing_complete=false; no full window or
permanent native configuration is qualified. See [DD result](normal-topology-dd/first-window-evidence/RESULTS.md).


No unchanged full six-fixture or full recovery matrix is repeated. The initial
scope retains the selected recovery mechanisms proven by Q04, together with
this explicit source-impact assessment. It does not claim arbitrary failures,
concurrent recovery, intermittent reliability or measured recovery under32-on
resource contention. A change to capture/restore, retry/publication, lifecycle
or deadline rules requires new affected recovery proof; expanding the support
claim to normal-topology recovery capacity requires a distinct controlled
recovery execution.
