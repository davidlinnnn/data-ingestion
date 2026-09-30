# T09b A11 group-5 diagnostic result

Run identity: `t09b-calibration-20260929-a11`. One execution, no retry.

A11 passed all 11 pre-inference gates and completed the fixed
06/07/08/native/06 sequence. All five full documents and checks matched their
references and reported `processing_complete=true`. The run processed 29 groups,
recycled at request 20, and observed the required two parser generations.

Temporal reconciliation classified all five workflows as business-complete.
Traffic reconciliation matched 9,563 client calls to 9,563 server attempts with
no missing ledgers or direct trace loss. The object cgroup accumulated 1,335 us
of full PSI, while maximum object full PSI avg10 remained 0.00 and
`memory.events.max` did not increase. No Pod or VM OOM was observed.

The result is `PASS_DIAGNOSTIC_ONLY`: publication-input buffering is covered,
while the acceptance plan still requires the remaining full buffering/checkpoint
scope and the final matched group-10 B cell. UID-fenced cleanup removed A11
runtime objects, restored held workloads to zero replicas, and retained the
Bound A11 evidence PVC.
