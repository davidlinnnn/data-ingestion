# K retained failure — remaining kubelet observer

Executed source commit 730cef2 once. 11 pre-inference gates passed. Three
Temporal executions completed with processing_complete=true and 15/15 pages;
all fresh/restored/exact-replay case records verified. The integrated gate failed
candidate qualification evidence incomplete, leaving only a pending fresh index.
No window retry or acceptance-rule change occurred.

Two persistent observer lanes removed controller exec churn, but the unchanged
Pod readinessProbe still ran an exec every two seconds. Attribution has 9/1,021
incomplete rows: three same-hash runc PermissionError process records, four
FileNotFoundError process records, and process-coverage transitions. Counts of
process issues do not equal disjoint sample counts. The reduced error count does
not promote K or prove the identity of every disappearing process.

Node full PSI remained zero. Maximum attribution cgroup current was
1,773,219,840 bytes; minimum outer MemAvailable was 6,539,943,936 bytes. The stop
was the final attribution assertion, not a pressure guard or Activity budget.
Readiness-probe recurring exec was an omitted caller in the initial root-cause
repair; L addresses it with an identical startup probe plus the same runtime
mount check in the persistent sample program. No PSS exemption is introduced.

Automatic forensic export retained 77 inventory entries. Independent size/hash,
exact file-set and tar byte verification passed before evidence was committed.
outer-cleanup.json confirms both local channels closed, owned runtime removed
with UID fences, terminal and post-cleanup OOM proof, and retained evidence PVC.
Post-run read-only checks confirm all previous PVC UIDs unchanged, 32 exact held
Deployment UIDs at zero, idle Temporal/object service, and no owned Pod/workflow.
K files and original source remain immutable. See runtime-diagnosis.json,
temporal-reconciliation.json, outer-cleanup.json and post-run-readonly.json.
