# ACL fixture 09 Option A window c plan

**Status: PREPARED, NOT AUTHORIZED, NOT EXECUTED.** Window b remains the
immutable `PRECHECK_FAILED_NO_RUNTIME` attempt documented under
`sentinel/acl-option-a-window-b/`. Its phase, root, prefix and evidence location
are consumed and must not be reused or overwritten.

## New identity and scope

- Runner: `tests/pdf_processing/q04/sentinel/run_acl_option_a_c.py`
- Phase: `acl-option-a-window-c`
- Remote root: `/tmp/q04-option-a-20260918-c`
- Object prefix: `q04/option-a-20260918-c/`
- Local evidence: `/private/tmp/q04-acl-option-a-window-20260918-c`
- Bundle: `/private/tmp/q04-inputs-option-a-v7`
- Fixture and modes: fixture 09 fresh, restored/new request and exact replay only

The root, prefix and local evidence path are currently absent. The runner creates
a new run ID and frozen state only after a future authorization, reservation and
staging pass. It does not copy old registrations or a prior run ID. No warm,
resource, drain, other fixture, service scaling, publication, push, merge or issue
closure is in scope.

## Time and capacity gates

The lease is exactly 1,500 seconds. The launch budget enforces at least 1,125
seconds remaining for the 825-second workload and final 300-second cleanup. This
leaves 375 seconds before launch: at most 180 seconds for outer admission and up
to 195 seconds for reservation handoff, staging, digest verification and init.
No extension is proposed.

Outer admission observes at most 180 seconds and requires 60 continuous seconds
with at least 4.5 GiB available memory and full PSI avg10 equal to zero. Per-case
admission remains 60 seconds at 3 GiB. The active sampled cgroup ceiling remains
4 GiB, the active memory floor remains 1.5 GiB, telemetry gaps may not exceed
three seconds, and VM/cgroup OOM counters may not increase. All 32 historical
Deployments must retain their reviewed UIDs and `replicas=0`, `ready=0` before
and after; this runner never restores them.

Any identity, source, package, model, profile, bundle, graph/oracle digest,
request binding, capacity or health mismatch stops the attempt. A case failure
stops the matrix. There is no automatic retry. Cleanup covers every exit after
root ownership, captures evidence, releases the exact reservation and rechecks
T09a health plus all 32 held Deployments.

## Acceptance boundary

All three modes must complete and agree on the adopted exact graph, 40/69/21
quality coverage, six formulas, equation 2 as `TextItem`, two required OCR
results, captions, source evidence and full graph. Exact replay must retain the
fresh request identity. This would be bounded fixture 09 evidence only and would
not complete Q04 or #51.

## Exact future command

The command below is intentionally gated by a verbatim approval reference. It
must not be run until main records a new explicit runtime authorization for this
window and exports that authorization text as `Q04_APPROVAL_REFERENCE`.

```sh
cd /private/tmp/q04-acceptance
test -n "${Q04_APPROVAL_REFERENCE:?set to the verbatim new window-c authorization}"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/pdf_processing/q04 \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/q04/sentinel/run_acl_option_a_c.py --execute \
  --owner 'Q04 main task 01a0aa25-3a23-7fb2-b13c-6936f95ccbc7' \
  --approval-reference "$Q04_APPROVAL_REFERENCE"
```

Before execution, main must review the fixed runner commit and recheck the
container/boot identity, OOM counters, T09a health, 32 held Deployments, unused
root/prefix/evidence identities and free global qualification lock.
