# T09b A7 group-5 diagnostic result

Run identity: `t09b-calibration-20260929-a7`. One execution, no retry.

A7 passed all 11 pre-inference gates and completed the fixed 06/07/08/native/06
sequence. All five workflows have `processing_complete=true` and exact full
document/check comparisons. It used 29 groups, recycled the parser at request 20
and recorded two parser generations.

The diagnostic qualifier passed. All 9,563 client calls reconcile to 9,563 server
attempts. Node and Pod gates passed with zero OOM. Object full PSI avg10 remained
0.00; its `memory.events.max` delta was 8, a recorded diagnostic boundary rather
than an immediate stop under the approved policy.

UID-fenced cleanup removed the A7 runtime objects and restored held workloads to
zero replicas. The A7 evidence PVC is retained. A7 completes the B4→A matched
order; the remaining normal-path pair is fresh A→B.
