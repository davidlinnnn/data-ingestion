# ACL fixture 09 Option A window b

**PRECHECK FAILED BEFORE RESERVATION, ADMISSION, WORKFLOW OR INFERENCE.** The
authorized attempt stopped without retry. It provides environment, failure and
cleanup evidence only; it does not provide fresh, restored or exact replay
acceptance for fixture 09 and does not complete Q04 or #51.

## Attempt and frozen identity

- Executed runner commit: `9504e0e103666863a4040e207fd2cfcdfee7b985`
- Retained runtime source: `18be1b3fbcb929921ec986a1a0bf93e4be995b4d`
- Retained run ID: `q04-7b4f958ff3ac4e2da5b54dcaa66914b9`
- Retained object prefix: `q04/keynote-18be1b3-20260916-b/`
- Proposed new root: `/tmp/q04-option-a-20260918-b`
- Proposed new prefix: `q04/option-a-20260918-b/`
- Proposed phase: `acl-option-a-window-b`
- Attempt began: 2026-09-18 11:40:03.990 UTC
- Precheck failed: 2026-09-18 11:40:07.497 UTC
- Post-failure health check finished: 2026-09-18 11:40:08.855 UTC
- Retry count: zero

The coordinator Pod UID, container ID, restart count, start time, boot ID and PID
1 start ticks matched the reviewed post-Docker-restart baseline. VM and cgroup
OOM-kill counters were zero. Python 3.12.13, the Linux platform, 112 packages,
17 model artifacts, the retained producer, frozen profile, old bundle and old
state matched their pinned evidence. The new root and every new phase path were
absent.

## Precheck failure and acceptance boundary

The runner then performed its read-only guard that proves an accepted historical
request still resolves under its original prefix and profile. The retained
`processing-result.json` uses the existing v2 schema: its profile ID is
`source.profile`, while the complete profile and release are under
`provenance.profile`. The runner incorrectly read a top-level `profile` field and
raised `KeyError: 'profile'`.

This is a runner schema-assumption defect. It is not a capacity, PSI, OOM,
parser, fixture, graph or oracle result. The failure happened before the runner
claimed the new remote root, acquired the global qualification reservation,
wrote a capacity record, began outer admission, created frozen state, submitted
a workflow or started inference. Fresh, restored and exact replay therefore did
not run, and none may be accepted from this attempt.

The fix validates the original request ID, original source prefix, accepted
profile ID and release against `source.profile` and `provenance.profile`. A local
regression covers the real v2 shape and a changed release. It does not authorize
a second runtime attempt; any later attempt needs a new identity, reviewed runner
commit and separate authorization.

## Cleanup and held services

Because the new remote root was never claimed, there was no owned runtime state,
workflow, process, scratch directory, reservation or object prefix to remove. A
separate read-only probe confirmed the new root remained absent and the global
qualification lock was not held. VM and cgroup OOM-kill remained zero.

T09a Temporal was healthy and idle and object readiness returned 200 before and
after the failure. All 32 historical Deployments retained their reviewed UIDs
and stayed at `replicas=0`, `ready=0`. Their before and after snapshots are
byte-identical with SHA-256
`d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4`.
The runner performed no scale or restore operation.

## Evidence boundary

Original local evidence is retained without modification at
`/private/tmp/q04-acl-option-a-window-20260918-b`; the independent read-only
cleanup observation was appended as `final-cleanup-probe.json`. There is no
remote evidence archive because no remote root was created. Private package,
model and environment details remain outside Git. Sanitized facts and artifact
hashes are recorded in `evidence/summary.json`.

No production implementation or frozen profile changed. No issue was published
or closed.
