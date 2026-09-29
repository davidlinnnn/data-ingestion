# T09b B5 group-10 diagnostic result

Run identity: `t09b-calibration-20260929-b5`. One execution, no retry.

B5 passed all 11 pre-inference gates and completed the fixed
06/07/08/native/06 sequence. All five full documents and checks matched their
references and reported `processing_complete=true`. The run processed 16 groups
with one parser generation and no request-count recycle.

Temporal reconciliation classified all five workflows as business-complete.
Traffic reconciliation matched 10,016 client calls to 10,016 server attempts
with no missing ledgers or direct trace loss. The object cgroup accumulated
5,237 us of full PSI and five `memory.events.max` boundary events; maximum
object full PSI avg10 remained 0.00 and no Pod or VM OOM occurred.

The result is `PASS_DIAGNOSTIC_ONLY`: B5 completes the final A11→B5 matched
normal-path pair. Publication-input buffering is covered, while the acceptance
plan still lists full buffering/checkpoint and recovery coverage as pending.
UID-fenced cleanup removed B5 runtime objects, restored held workloads to zero
replicas, and retained the Bound B5 evidence PVC.
