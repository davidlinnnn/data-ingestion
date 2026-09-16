# Q04 Keynote capacity proposal

Status: **review only; no pause or sentinel is authorized**. Existing PSI,
memory, cgroup, OOM, telemetry-gap and time limits stay unchanged. This proposal
does not inherit the Q03 trial D or prior Q04 pause authorization.

## Read-only findings

At 2026-09-16 14:53:24 UTC, the shared Linux VM had 7.748 GiB total and
2.363 GiB available memory, full PSI avg10 0, global OOM count 28 and no cgroup
OOM. The coordinator had no matching PDF inference or qualification process.
All eleven PDF Temporal namespaces were healthy with zero Running workflows and
all eleven object readiness endpoints returned 200.

The Kubernetes Metrics API is unavailable. A read-only CRI point sample found
2,415,050,752 bytes (2.249 GiB) of working set across the 32 active historical
PDF Deployments proposed below. This is an estimate, not guaranteed reclaim.
The T03–T07 subset accounts for 1.347 GiB; the additional integration, S1, T01,
T02 and T08 services account for 0.902 GiB. Current available memory plus that
point estimate is about 4.61 GiB. Q03 trial D actually admitted at a minimum
4,859,904,000 bytes (4.526 GiB), zero PSI and OOM 28, so the combined scope is a
reasonable way to seek comparable headroom.

| Scope | Active Deployments | Current working set |
| --- | ---: | ---: |
| Prior Q04 T03–T07 set | 20 | 1.347 GiB |
| Additional historical set | 12 | 0.902 GiB |
| Proposed combined set | 32 | 2.249 GiB |

The exact current UID, resourceVersion, replicas, readiness and per-container
working-set observation are in
[`capacity-candidates.json`](evidence/capacity-candidates.json). All 32 are
currently replicas=1 and Ready=1. Resource versions are evidence timestamps,
not reusable preconditions; every field must be re-read immediately before an
approved window.

## Exact proposed scope

- `pdf-integration-0913`: `objects`, `temporal`, `workflows`
- `pdf-s1-warm-lifecycle`: `objects`, `temporal`
- `pdf-t01-validation`: `objects`, `temporal`
- `pdf-t02-validation`: `objects`, `temporal`, `workflows`
- `pdf-t03-validation` through `pdf-t07-validation`: `activities`, `objects`,
  `temporal`, `workflows` in each namespace
- `pdf-t08-validation`: `objects`, `temporal`

T09a services and every coordinator stay running. Zero-replica Deployments,
application services, Kubernetes system services, PVCs and completed Pods remain
outside scope. No Deployment is created or deleted.

## Proposed go/no-go and restoration procedure

Before any future mutation, main must approve a new owner, 20-minute interval,
new remote run root and new object prefix, plus this exact current Deployment
set. The capacity owner then:

1. Acquires the local and coordinator global qualification locks and creates the
   new reservation. Rechecks the T09a coordinator UID, exact runtime/profile,
   unused root/prefix, no matching parser/harness process, eleven Temporal idle
   queries and object health.
2. Re-reads every candidate. Abort before mutation if its UID changed, replicas
   are not 1, Ready is not 1, or a namespace is not idle. Save full private
   originals; publish only sanitized UID/replica evidence.
3. Stops compute first using compare-and-scale: integration and T02 `workflows`,
   plus T03–T07 `activities` and `workflows`. Wait for both Pods and CRI
   containers to disappear.
4. Stops the 20 `objects`/`temporal` Deployments across integration, S1, T01–T08
   and again verifies Pod/CRI absence. Coordinators and T09a remain available for
   control, health, Temporal and object storage.
5. Samples capacity for 60 continuous seconds. The frozen runtime gate remains
   MemAvailable at least 3 GiB, full PSI avg10 exactly zero, unchanged VM/cgroup
   OOM and at most a 3-second gap. For this enlarged plan, use **4.5 GiB minimum
   available** as the additional capacity-owner go/no-go target; abort and restore
   if it is not met. This adds headroom without weakening or changing runtime
   processing guards.
6. Only after a separately approved sentinel may the new Keynote fresh,
   restored and replay cases run under the original profile and production code.
   Reserve the final five minutes for cleanup.
7. On every exit, stop/cancel only owned work and prove no owned Running workflow,
   parser, scratch or incomplete complete-registration. Restore backing services
   first (`objects`, `temporal`), wait Ready=1 and health, then restore workflow
   and activity workers. Recheck all original UIDs and replicas, eleven Temporal
   namespaces idle, eleven object endpoints 200, and release the reservation only
   after cleanup and restoration both pass.

If the enlarged scope cannot sustain the 4.5 GiB planning target and zero PSI,
do not widen the pause set. If the same sentinel still triggers PSI with that
headroom, stop service-pause experiments and separately plan a Docker VM memory
increase or dedicated Linux validation environment; either may require restart
coordination.
