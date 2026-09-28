# Q04 fixture 07 Pod topology v8 / I

I fixes H acceptance-tool evidence loss and cleanup-marker discovery. H and all
earlier runners/evidence remain immutable. Read [diagnosis](../diagnosis/yolo-pod-h-stop/DIAGNOSIS.md)
for recovered Temporal history, worker PSI samples and cancellation causality.

The versioned standalone runner follows this repository's frozen per-window
source-projection model. New modules use I identity only; shared frozen producer,
oracle and resource policy are unchanged. Existing v7 storage/model/gate documents
are referenced as historical contracts, not copied as new observations.

See [run plan](RUN-PLAN.md) and [local validation](OFFLINE-VALIDATION.md).
No Q04 PASS or ticket closure follows from preparing this candidate.
