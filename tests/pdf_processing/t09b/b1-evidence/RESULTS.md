# T09b B1 pre-admission result

Run identity: `t09b-calibration-20260929-b1`. One invocation, no retry.

B1 stopped before Kubernetes resources, workflows or inference were created.
The inner runner was invoked directly instead of through the retained outer
controller, so its identity gate correctly rejected the 32 normal-topology
Deployments while they were held at zero replicas. `workload_evidence` is
`NOT_STARTED`; no B1 Deployment, Pod or PVC exists and the B1 prefix was unused.

This is an orchestration defect, not group-10 execution evidence. The corrected
B2 entry point uses the retained outer controller, which owns the bounded
activation and restoration of those Deployments. B1 is never reused.
