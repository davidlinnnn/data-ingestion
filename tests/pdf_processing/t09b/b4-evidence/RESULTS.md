# T09b B4 group-10 diagnostic result

Run identity: `t09b-calibration-20260929-b4`. One execution, no retry.

## Result

B4 passed all 11 pre-inference gates and completed the fixed warm sequence:

| Trial | Registered pages | Full output comparison |
| --- | ---: | --- |
| warm-0-06 | 28 | equal |
| warm-1-07 | 15 | equal |
| warm-2-08 | 12 | equal |
| warm-3-native | 51 | equal |
| warm-4-06 | 28 | equal |

Every workflow completed with `processing_complete=true`, with no Temporal
Activity failure, timeout or cancellation. The run used 16 groups, one parser
generation and no request-count recycle. B4 is `PASS_DIAGNOSTIC_ONLY`.

## Measurement and cleanup

- Pod resource gate: PASS across 1,384 samples; maximum cgroup memory
  3,338,715,136 bytes; zero OOM events and full PSI avg10 0.00.
- Node: minimum available memory 2,208,755,712 bytes; zero VM OOM delta.
- Object service: max-event delta zero, maximum full PSI avg10 0.00 and
  cumulative full-pressure delta 4,312 microseconds.
- Traffic: all 10,016 client calls match 10,016 server attempts.
- Runner duration: 517.67 seconds. It is a second group-10 sample, not a
  selected configuration or standalone performance conclusion.

UID-fenced cleanup removed the B4 Deployment, Pod and source ConfigMaps. Held
workloads were restored to zero replicas. The Bound evidence PVC
`t09b-calibration-b4-evidence-20260929` is retained.

The next planned matched-order cell is a fresh group-5 baseline. Complete
buffering/checkpoint metrics, recovery comparison and final selected-bound
revalidation remain required for #45 acceptance.
