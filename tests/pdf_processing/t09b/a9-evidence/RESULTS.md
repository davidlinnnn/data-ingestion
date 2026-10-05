# T09b A9 native-trace stop

Run identity: `t09b-calibration-20260929-a9`. One execution, no retry.

A9 passed all 11 pre-inference gates and completed the 06, 07 and 08 workflows.
During the fourth (`native`) workflow, the MinIO native trace collector ended
prematurely. The outer controller recorded
`RuntimeError('native trace failed or ended prematurely')`, handed off a stop to
the supervisor, and the workload exited by interruption. The native workflow
and final 06 workflow did not complete, so A9 is not a group-5 replicate.

The observer recorded node full PSI avg10 0.00 and zero VM OOM kills throughout.
The last sampled available memory was 2,887,135,232 bytes, above the retained
1.5 GiB runtime floor. These facts exclude the configured memory guards as the
stop trigger but do not establish why the trace collector ended.

Cleanup proved the worker, parser and transport absent; UID-fenced cleanup
removed owned runtime objects, restored all held workloads to zero replicas,
and retained the Bound evidence PVC `t09b-calibration-a9-evidence-20260929`.
The trace session now includes the sanitized exception type and child exit code
in its failure, without retaining raw trace data. A fresh identity is required
for the next diagnostic run.
