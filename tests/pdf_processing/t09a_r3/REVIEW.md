# R3 review

## Standards

Independent review identified inadequate service readiness and missing restore
identity fencing. Both were corrected before the first pause: observed generation,
MinIO/Temporal health, captured UID and resource-version preconditions are checked.
A later collector finding was fixed by retaining memory-event counters separately
for old and replacement streams, sorted by sample timestamp. Final review also
caught prefix matching that assigned resumed-drain samples to the rejected drain;
exact trial/old/new filenames now prevent that cross-trial attribution.

## Spec

Independent review identified missing full-suite admission/resource monitoring and
unenforced preflight ordering; both were corrected before execution. Review caught
corrupted embedded fault scripts and insufficient model-active attribution before
that phase ran; remote scripts were restored and injection requires an active
native stage with matching sampled PID, persisted before mutation. The resumed
window requires a new preflight, preserves frozen run c, skips the already-passed
guard, and uses a unique drain trial name. No blocker remained in bounded rechecks.

Runtime proof is reported separately in README.md and evidence. Source quality is
not promoted to PASS by successful resource or equality checks.
