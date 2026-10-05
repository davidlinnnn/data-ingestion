# T09b B2 group-10 diagnostic result

Run identity: `t09b-calibration-20260929-b2`. One execution, no retry.

## Result

B2 passed all 11 pre-inference gates and completed the fixed warm sequence:

| Trial | Registered pages | Full output comparison |
| --- | ---: | --- |
| warm-0-06 | 28 | equal |
| warm-1-07 | 15 | equal |
| warm-2-08 | 12 | equal |
| warm-3-native | 51 | equal |
| warm-4-06 | 28 | equal |

Every workflow completed with `processing_complete=true`, with no Temporal
Activity failure, timeout or cancellation. Group size 10 reduced the sequence
from A6's 29 groups to 16 and kept one parser generation, so no request-count
recycle occurred. The worker and parser stopped cleanly.

The post-run qualifier classifies B2 `PASS_DIAGNOSTIC_ONLY`. This proves the
candidate can preserve the complete output under this single diagnostic window;
it does not select the final #45 bound.

## Measurement

- Pod gate: PASS across 1,397 samples, maximum cgroup memory 3,213,393,920 bytes,
  zero OOM events and full PSI avg10 0.00.
- Node: 1,400 samples, minimum available memory 2,201,464,832 bytes and zero VM
  OOM delta.
- Object service: max-event delta zero, full PSI avg10 0.00 and cumulative full
  pressure delta 21,786 microseconds.
- Traffic: all 10,016 client calls match 10,016 server attempts; HTTP counters
  report 323,874,711 receive bytes and 4,095,841,710 transmit bytes. These are
  HTTP-layer counters, not total wire bytes.
- Publication input buffers are measured. Complete retained-read/native/parser
  buffer attribution remains pending.

The B2 runner took 520.27 seconds versus A6's 524.75 seconds. A single pair is
not enough to claim a performance win; OCR and other non-group work dominate the
sequence. Storage cost fields deliberately leave transmitted and committed PUT
bytes unknown because the available evidence cannot prove them.

## Cleanup and scope

The runner exited zero. UID-fenced cleanup removed the B2 Deployment, Pod and
source ConfigMaps. All 32 held Deployments were restored to zero replicas, and
the object service identity and health are unchanged. The Bound evidence PVC
`t09b-calibration-b2-evidence-20260929` is retained with UID
`30d9eba0-ec3a-4cbb-afbe-355f0535352b`.

B2 establishes the first group-10 diagnostic cell. Ticket #45 still requires the
planned matched-order repetitions, complete buffering/checkpoint metrics,
recovery/repeated-work comparison and final selected-bound revalidation.
