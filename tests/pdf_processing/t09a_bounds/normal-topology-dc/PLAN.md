# #44 initial operating-scope and object-service proposal

Status: APPROVED by the user on 2026-09-28; candidate qualification pending. Source integrated
at57fcc2e. Current cluster inventory checked2026-09-28.

## Initial supported scope

- One serial Activity worker in the existing kind cluster/namespace. Reliable
  native-text papers and bounded contiguous book chapters, with required figure
  OCR and the reviewed relationship/quality rules.
- Latest combined-source complete-window evidence covers WikiSkill28pages,
  YOLO15pages,AIMA12pages and native51pages,including a Wiki repeat. These named
  fixtures are the verified set. A new arbitrary file is not qualified solely
  because it meets admission caps. ACL/Keynote and recovery evidence remain
  valid for their original Q04 producer identities,not relabelled as new runs.
- Keep group size5,one document at a time,parser recycle after20requests,
  OCR intra-op4 and OCR-only NumPy policy. Worker CPU quota4,hard limit5GiB,
  sample guard4GiB. Existing deadlines: preflight30s,child540s,parser startup120s,
  no-progress180s,terminate/reap5s each.
- Existing trial admission caps:100MiB/file,51pages,20,000,000rendered pixels/page.
  These are rejection ceilings,not demonstrated successful capacity maxima.
  The four unique tested PDFs are308,913–1,817,841bytes. Broad100MiB/20M-pixel
  success claims remain unqualified. No arbitrary51pagePDF performance guarantee.
- Multi-document concurrency,whole books,scan-first/unreliable native layers,
  universal languages/PPT and high availability remain outside this initial
  candidate scope. Accepting this limited scope is an explicit #44 decision.

## Recommended permanent-setting candidate

Target: Deployment objects,namespace pdf-t09a-validation,existing pinned MinIO
image on worker2. One replica and existing object-data PVC (Bound,2Gi,RWO).
No data migration,deletion,prefix rewriting or volume expansion.

| Field | Current | Proposed |
| --- | --- | --- |
| memory request |128Mi|768Mi|
| memory limit |512Mi|1Gi|
| CPU request |100m|100m|
| rollout |RollingUpdate|Recreate during an idle maintenance window|
| explicit host memory.low overrides |none at rest|none|

The measured DB object peak was734,707,712bytes (~700.7MiB).768MiB is a candidate
scheduler request around that measured working set;1GiB is the already-trialled
cap. Neither value is a proof of sustainable capacity. Recreate makes the
single-instance rollout intentionally stop the old replica before bringing up
the replacement; expect a short object-service outage and drain ingestion first.
Keep storage contents/image/placement unchanged. No new paid environment.

This refines the earlier1GiB+768MiB-low proposal. DB installed low through
privileged host cgroup writes and a runtime override of the shared Burstable
systemd slice. That script is a reversible experiment,not a persistent
object-specific deployment owner. Do not turn it into a permanent reapply loop.
A Kubernetes request is scheduler accounting; it does not establish the same
memory.low setting or ancestor protection. Observe actual cgroups after rollout.

The candidate intentionally drops the experimental protection dependency. This
is a new,unqualified deployment configuration until the targeted validation
below passes. Existing CG proves a1GiB/no-low window with the earlier NumPy-only
source; DB proves the combined OCR source with low. Neither proves this exact
combination. The one required workload tests that specific remaining difference.

## Necessary validation and adoption

1. Source-controlled namespace-specific deployment overlay;validate its patch
   against the existing API with server dry-run. Local regression covers the
   fixed observer and restoration;reuse already-passed OCR tests unless changed.
2. In an idle maintenance window,record old deployment resources/strategy and
   apply the candidate. Verify effective leaf/Pod1GiB caps,health and readable
   existing objects. Replace the Pod once to verify desired settings survive
   a new Pod identity;PVC remains the same. Record actual low/min settings.
3. One new controlled mixed window with32historical Deployments temporarily on,
   exact existing sequence29groups/recycle20,full output/check equality and all
   business results complete. No constructor overrides,no automatic retry.
   Use the fixed auxiliary observer;its loss must stop this qualification.
4. For this initial final-qualification proposal,retain the stricter original
   zero-new-object-full-PSI gate alongside zero max/OOM,VM/worker avg10,
   memory floors,telemetry and existing deadlines. This is a declared proposed
   qualification contract;CS/DB functional verdicts remain historical unchanged.
5. Stop on failure,seal evidence,restore old object deployment settings and
  32off. No automatic increase of limits or guard relaxation. On success,
   retain the approved object desired settings and restore32off as the resting
   state. Publish exact conditions and a before/after configuration record.

Closure requires approval of this explicitly limited support scope,successful
qualification of the persistent candidate,complete cleanup/evidence and an
impact mapping for inherited Q04 recovery tests. If broader maximum-input or
arbitrary-document claims are required,#44 stays open for those specific tests.
A single window does not establish uptime,indefinite object-store growth or
universal reliability. Existing2GiPVC size is not a demonstrated usable capacity
or retention policy;storage expansion/retention remains a separate explicit
operating decision before approaching capacity. No new ticket is proposed.

## Approved decision

The user approved the limited initial scope and one qualification of the768Mi request /
1Gi limit native deployment candidate,without persistent host memory.low edits.
A successful qualification authorizes retaining this object configuration.
Failed qualification restores128Mi/512Mi and the recorded rollout strategy.
This decision changes the initial support contract and would make resource
settings permanent after PASS,so it is the critical decision reserved by the user.

## Sources

- Integrated evidence: tests/pdf_processing/t09a_bounds/normal-topology-db/first-window-evidence/RESULTS.md
- Existing trial implementation: tests/pdf_processing/q04/sentinel/object_memory_low_db.py
- Kubernetes requests/limits: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- Linux memory.low hierarchy: https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html
