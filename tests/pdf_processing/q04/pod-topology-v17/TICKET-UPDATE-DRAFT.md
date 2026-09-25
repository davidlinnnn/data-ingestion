# #51 update draft — not published

Controlled execution R (`3174174`,
`q04-warm-pod-cgroup-20260921-r`) ran once and stopped before Pod scale-up. The
outer admission passed with 48 samples, 7,945,109,504 bytes minimum available
memory, zero node PSI and zero OOM. No workflow, Activity or inference started,
so R provides no ingestion or warm-sequence acceptance result.

The stop was an acceptance-harness identity-binding defect. Kubernetes created
and returned the expected R Deployment and UID, but the validator's Python
keyword default had been bound to P's Deployment name when the private engine
was loaded. The same early binding affected later Pod run-label and cleanup
defaults. The evidence therefore rejects capacity, PSI, Temporal and ingestion
as causes of this stop; capacity during the intended warm workload remains
unknown because the workload never ran.

Cleanup removed the R Deployment and ConfigMaps with UID preconditions. The
unused evidence PVC is retained. A separate live check found no R-owned runtime,
all 32 held Deployments exact and off, Temporal healthy and idle, object health
200, and zero post-cleanup node PSI/OOM.

The corrected S runner binds S topology before the shared engine defines its
identity-sensitive functions. It has a new run identity and object prefix,
keeps automatic retry disabled, and retains the existing 4 GiB/5 GiB resource
guards, PSI/OOM gates, floors and deadlines. Local regression and offline
contract checks pass. R will not be retried; S remains unexecuted pending the
new explicit authorization required after the fail-stop.

Q04 remains partially accepted only at the previously recorded bounded rows.
The original 29-group request-20 warm sequence, native/Wiki current-producer
matrix rows and the remaining recovery gates are still unproven. #51 is not
ready to close or integrate.

Evidence:
`tests/pdf_processing/q04/pod-topology-v17/first-window-evidence/RESULTS.md`

Matrix: `tests/pdf_processing/q04/CURRENT-ACCEPTANCE-MATRIX.md`
