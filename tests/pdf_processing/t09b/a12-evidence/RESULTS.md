# T09b A12 selected group-5 measurement result

Run: `t09b-calibration-20260930-a12`, prefix `t09b/calibration-20260930-a12/`.
One execution, no automatic retry. A12 is an instrumentation confirmation;
the original three matched normal-path pairs are unchanged.

All 11 pre-inference gates passed. The five complete documents and checks match
the accepted references; all five Temporal business results are complete.
There were 29 groups, recycle at request 20 and two parser generations.
Traffic reconciles 9,563 client calls with 9,563 server attempts, without ledger
gaps or direct trace loss. Server HTTP RX/TX: 324,582,061 / 3,614,679,831 bytes.

| Request | Largest application read chunk | Peak concurrent publication inputs |
| --- | ---: | ---: |
| 06 process-cold | 8,860,065 B | 22,934,707 B |
| 07 warm | 4,875,372 B | 14,460,723 B |
| 08 warm | 20,876,815 B | 28,896,640 B |
| native warm | 22,539,322 B | 70,573,839 B |
| 06 warm repeat | 8,860,065 B | 22,934,707 B |

Read chunk sizes measure individual body-read returns, not all simultaneously
retained reads, decoded graphs, SDK or native parser allocations. Publication
inputs measure the existing publication boundary. Neither is a full buffering
peak; the whole-Pod sampled peak was 3,017,080,832 B. Missing older read-chunk
telemetry remains unknown, not zero. Application read amplification was
6.17–12.24 across these requests; denominators and exact values are retained
in `storage-cost.json`.

No Pod/VM OOM; minimum VM available memory 2,606,751,744 B, largest sample gap
0.4124 s. Maximum object full PSI avg10 was 0.00; cumulative full PSI increased
4,493 us without a memory.events.max increment. Existing approved runtime
node-PSI telemetry policy was retained.

Cleanup removed owned runtime objects, restored all 32 held Deployments to zero
with no owned Pods and no restoration errors, and preserved the object service
identity/configuration. Evidence PVC `t09b-calibration-a12-evidence-20260930`
was checked Bound (UID `fa6cef70-30ac-4efb-b60c-93c46d492c56`). Raw evidence
and the new object prefix remain retained.

Status: **PASS_DIAGNOSTIC_ONLY**. Matched interruption recovery and remaining
coverage/affected-bound reconciliation are still required before closing #45.
