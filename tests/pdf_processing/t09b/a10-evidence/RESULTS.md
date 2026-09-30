# T09b A10 native-trace reader stop

Run identity: `t09b-calibration-20260929-a10`. One execution, no retry.

A10 passed all 11 pre-inference gates and reached the fourth (`native`)
workflow. The MinIO trace reader then raised `ValueError` while its child
process was still running (`exit=None`). The outer controller interrupted the
supervisor, so A10 is incomplete and is not a group-5 replicate.

Node full PSI avg10 remained 0.00, VM OOM kills remained zero, and the final
available-memory sample was 3,492,294,656 bytes, above the retained 1.5 GiB
runtime floor. The configured memory guards did not trigger the stop.

Cleanup proved the worker, parser and transport absent; UID-fenced cleanup
removed owned runtime objects, restored all held workloads to zero replicas,
and retained the Bound A10 evidence PVC. The trace reader now reports a fixed
processing-stage code with the exception type, while continuing to discard raw
trace records. A fresh identity is required for the locating run.
