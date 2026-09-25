# M pre-runtime review

Fixed point 10b4723; candidate d1cbaed, correction 4118a79.
Standards and Spec independently found the missing workload-memory-policy.json
transport allowlist entry. A real entrypoint->snapshot regression reproduced
unexpected evidence path, then passed after the M-only evidence contract fix.
The record is also required for successful qualification. ctypes prctl now has
explicit argument widths. Standards independently passed 12 transport+3 THP
tests; Spec independently passed the complete 128 tests. Both report no remaining
runtime blockers. Frozen source, full argv and offline contracts pass.

Only the workload process tree disables THP; no global sysfs, acceptance threshold
or historical evidence changes. The cause of L direct reclaim is still unknown.
One M experiment is authorized by the user's same-session continuation; no retry.
