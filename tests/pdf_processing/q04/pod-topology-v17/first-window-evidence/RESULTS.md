# R — admission passed; workload did not start

Execution commit `3174174`, identity
`q04-warm-pod-cgroup-20260921-r`, ran once with no automatic retry. The outer
admission observed 48 samples over 60.85 continuous seconds. Minimum available
node memory was 7,945,109,504 bytes; node full-memory PSI, cgroup usage and OOM
counters stayed zero. These values prove admission only.

The controller created the immutable ConfigMaps, retained evidence PVC and
inactive Deployment, then rejected the Deployment identity before scale-up.
The Deployment returned by Kubernetes was
`q04-pod-cgroup-r-activities`, UID
`bc9c5e64-fa41-4048-8425-d8bc1ed554ef`, and matched the ownership record. The
validator nevertheless searched for `q04-pod-cgroup-p-activities`.

The proven root cause is Python keyword-default binding in the acceptance
harness. R loaded the private P engine before replacing its globals, so five
identity-sensitive functions retained P's Deployment or run-label defaults.
This is not a cluster-capacity, PSI, Activity, workflow or ingestion failure:
no Pod was started, no workflow was created and no inference ran. Resource
capacity for the intended warm sequence remains unknown because that workload
was not exercised.

Cleanup removed the R Deployment and both ConfigMaps with UID preconditions.
The PVC `q04-pod-cgroup-r-evidence-20260921-r`, UID
`a023602d-87e6-499b-9275-6abeb11f92ed`, remains retained in Pending state; it
was never mounted. Persistent channels closed, post-cleanup node PSI and OOM
were zero, and final health passed. An independent read-only check found no
R-owned Deployment, ConfigMap or Pod; all 32 held Deployments retained exact
UIDs and zero replicas; Temporal was healthy and idle; object health returned
200.

S fixes the loader boundary: it installs S topology before the shared engine
defines its functions, then restores the public P module. Regression tests bind
the real R failure shape and every affected Deployment/run-label default to S.
S uses a new identity, prefix, queues, Deployment and retained PVC. The 4 GiB
qualification guard, 5 GiB hard limit, PSI/OOM gates, memory floors and
1500/825/300 second deadlines are unchanged.

Disposition: **FAIL_ACCEPTANCE_HARNESS_IDENTITY_BINDING_WORKLOAD_NOT_STARTED**.
R proves no acceptance row and must not be retried. Q04 and #51 remain open.
The next controlled runtime is S, after review and a new explicit authorization
required by R's fail-stop/no-retry contract.
