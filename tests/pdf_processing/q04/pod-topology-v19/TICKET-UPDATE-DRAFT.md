Q04 warm runtime T (`q04-warm-pod-cgroup-20260921-t`) ran once with no retry.
All admission and pre-inference gates passed. The first WikiSkill 06 Temporal
workflow completed normally with all 21 Activities completed, 28/28 pages and
11/11 components registered. It then stopped in the acceptance consumer because
the current graph differs from the retained reference and remains source-review
pending. No PSI, OOM, memory floor, deadline, Activity failure or supervisor
interruption caused this stop.

This exposed a harness scope mismatch: T was intended to qualify only the fixed
29-group sequence, request-20 recycle and resources while leaving Wiki/native
fresh-output equality unproven, but it required full fixture graph acceptance
before advancing. T therefore proves no warm-sequence row. The remaining cases,
recycle and integrated resource maximum were not reached.

Cleanup completed with UID-fenced removal of owned runtime and ConfigMaps. The T
evidence PVC remains Bound and retained; post-cleanup PSI/OOM are zero, object
health is 200, and all 32 held Deployments remain exact and off.

U fixes the scope mismatch without accepting an unreviewed graph. It permits the
warm measurement to continue only when source-region text, text metadata/original
text, complete picture/table/key-value/form payloads and page payloads remain
equal. It records Wiki/native as `NOT_ACCEPTED_WARM_MEASUREMENT_ONLY`; their
fixture acceptance and fresh-output equality remain unproven. Regression tests
reject source text, table-cell and provenanced-picture changes. No resource or
deadline threshold changed.

#51 remains open and is not ready for integration or closure.
