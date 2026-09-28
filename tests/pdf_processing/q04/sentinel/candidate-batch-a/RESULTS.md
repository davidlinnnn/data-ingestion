# Candidate batch A result

## Outcome

The authorized six-document batch stopped during the first fixture, YOLO 07
fresh, with **`FAIL_GRAPH_GATE`**. Processing completed all 15 pages and four
required OCR components. The fixed graph gate expected
`b270e1818bdeecf5f88cc83766c8ab3fa1e89a1586fb0cacbfbf049614a8c276`
and observed
`80c435fc8dc171c6da52a1353195b7221ad2449a518c326efbb0193d9828587d`.
The gate classified the difference as `SOURCE_REVIEW_REQUIRED` and the batch
stopped as planned.

YOLO restored and exact replay did not run. ACL, Keynote, AIMA, WikiSkill, and
the native 51-page paper did not run. There was no retry, no fresh-index
acceptance, and no publication or issue-state change.

## Retained identities

| Evidence | Identity |
| --- | --- |
| batch | `candidate-batch-20260919-a` |
| YOLO phase | `yolo-lifecycle-a` |
| batch state | `/private/tmp/q04-candidate-batch-20260919-a/batch-state.json`, SHA-256 `f6b607f008354b4b69a62a36bd174bb3e157af18acebe43132d169d61d1686ce` |
| retained archive | `/private/tmp/q04-yolo-lifecycle-20260919-a/remote-evidence.tar`, 9,287,680 bytes, SHA-256 `5c183da78740cb68cc7114dc06a4e2a7bd890b17c7f7637dd69adc8495bb9bc9` |

The frozen and source states remained unchanged. The source-review diagnosis is
in [`../../diagnosis/yolo-lifecycle-a/ANALYSIS.md`](../../diagnosis/yolo-lifecycle-a/ANALYSIS.md),
with the machine-readable runtime result in
[`../../diagnosis/yolo-lifecycle-a/evidence/runtime-summary.json`](../../diagnosis/yolo-lifecycle-a/evidence/runtime-summary.json).
That summary records and enforces the SHA-256 identity of all seven loose files
used for admission, cleanup, health, frozen-state, lease, and held-Deployment
claims. The analyzer also binds candidate `inputs.json` at
`67eba79d6125c536ab728edb4f7d8ee070d8aead49384f4afc3a48c78267d420`
and verifies the historical method payload against its recorded digest.

## Admission, resources, and cleanup

Outer admission passed its 60-second capacity/PSI/OOM requirement. Active guard
samples stayed below the fixed 4 GiB boundary, with a maximum of 4,273,446,912
bytes, zero PSI, and zero OOM events. The complete 250 ms diagnostic stream
observed a short 4,403,523,584-byte peak. It recorded the required warm-to-fresh
handoff and no warm/fresh overlap. The run is still a graph-gate failure, and the
250 ms peak must remain visible in later resource review.

Offline attribution now places that sole violating sample in group 3 while one
warm parser serves its third sequential request; it is not an overlap,
assembly, or OCR peak. The detailed retained-data decision is
[`../../diagnosis/yolo-lifecycle-a/RESOURCE-DECISION.md`](../../diagnosis/yolo-lifecycle-a/RESOURCE-DECISION.md).
Both the fixture-local equivalence candidate and the `max_requests=1` resource
candidate remain inactive pending main approval.

Cleanup verified no remaining owned process, workflow, or scratch and released
the reservation. The 32 historical Deployments remained closed, kept their
expected UIDs, and were byte-identical before and after. They were not restored.

Issue #51 remains open. This result neither publishes the batch nor treats any
unrun fixture or mode as accepted.
