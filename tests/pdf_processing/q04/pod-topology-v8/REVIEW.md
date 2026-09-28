# Pre-runtime code review

Fixed base: f0d40f7. Initial repair commit: 49eba63. Both reviewers read the
committed diff and compared H/I after normalizing window identities.

## Standards

One P1 finding: supervisor-interruption.json was missing from the I transport
ROOT_ALLOWED set. Real snapshot_program reproduction failed on that exact path;
final mirroring and fingerprint verification would block controller export.
Fixed with an I-only allowlist entry. The regression now drives interrupted
supervisor -> failed terminal seal -> real snapshot -> mirror finalize -> archive
fingerprint -> local tar verification. It was red before this correction and
green afterward. No documented-standard violations or substantive complexity
findings; version copies retain the historical frozen-source contract.

## Spec

No additional implementation blockers. Independently reran 104 tests and checked
source projection, full argv and unchanged producer/image/oracle/budgets. The
report's attribution-tail claim needed correction: original transport had 272
samples, but recovered PVC has 293 including positive cgroup PSI. Diagnosis now
records both scopes and retains uncertainty about task cause/capacity.

Standards re-review independently passed all six stop regressions and found no
remaining execution blocker in the correction. This review does not qualify
runtime behavior or close Q04/#51.
