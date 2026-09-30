# T09b A6 controlled verification result

Run identity: `t09b-calibration-20260929-a6`. One execution, no retry.

## Result

A6 passed all 11 pre-inference gates and completed the fixed warm sequence:

| Trial | Registered pages | Full output comparison |
| --- | ---: | --- |
| warm-0-06 | 28 | equal |
| warm-1-07 | 15 | equal |
| warm-2-08 | 12 | equal |
| warm-3-native | 51 | equal |
| warm-4-06 | 28 | equal |

Every workflow completed with `processing_complete=true`, an accepted result and
no Temporal Activity failure, timeout or cancellation. The sequence used 29 groups
and recycled the parser once at request 20. Both parser generations exited, and
the worker stopped cleanly with no parser, scratch or sampler residue.

The controller's live post-run qualifier initially failed because it referenced
removed temporary Q04 paths. That original `qualification_failed` controller
record is retained. The repaired offline qualifier uses versioned document
digests and complete repo-held checks references; it classifies A6
`PASS_DIAGNOSTIC_ONLY`. A5 and A6 produced identical complete checks for all four
fixtures. The diagnostic qualifier does not select a final #45 configuration.

## Measurement

- Pod gate: PASS across 1,414 samples; maximum cgroup memory 2,866,294,784 bytes,
  maximum owned PSS 2,697,822,208 bytes, full PSI avg10 0.00 and zero OOM events.
- Node: 1,420 samples; minimum available memory 2,505,388,032 bytes, full PSI
  avg10 0.00 and zero VM OOM delta.
- Object service: 2,072 samples; maximum memory.current 1,073,479,680 of
  1,073,741,824 bytes, max-event delta zero, full PSI avg10 0.00, cumulative
  full-pressure delta 4,771 microseconds and zero OOM events.
- Traffic: all 9,563 client calls match 9,563 server attempts; server HTTP
  counters report 324,581,123 receive bytes and 3,614,672,367 transmit bytes.
  Two marker calls are excluded. These counters are HTTP-layer evidence, not
  total wire bytes.
- Publication input buffers are measured. Complete retained-read/native/parser
  buffer attribution remains pending.

The 192 `NoSuchKey` calls are normal unretried existence lookups. Each maps to
exactly one server 404. The reconciler accepts only that exact shape; other failed
or incomplete calls remain errors.

## Cleanup and scope

The runner exited zero. UID-fenced cleanup removed the A6 Deployment, Pod and
source ConfigMaps. All 32 held Deployments remain at zero replicas, and the object
service identity and health are unchanged. The Bound evidence PVC
`t09b-calibration-a6-evidence-20260929` is retained with UID
`a39556f1-6bc8-49a6-b715-05e9762d036e`.

A6 accepts the group-5 diagnostic baseline and its measurement path. Ticket #45
still requires the planned group-size comparison, complete buffering/checkpoint
metrics, recovery/repeated-work comparison and final selected-bound revalidation.
