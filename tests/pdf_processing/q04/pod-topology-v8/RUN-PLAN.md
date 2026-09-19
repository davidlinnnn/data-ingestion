# I controlled diagnostic acceptance

Authorization: the user's 2026-09-20 handoff explicitly authorizes normal Q04
acceptance on the existing kind-internal-a2a-vs6-local cluster and namespace
pdf-t09a-validation. No new paid environment, threshold change, Deployment
restore or historical deletion is requested or authorized.

One run: q04-yolo-pod-cgroup-20260920-i, object prefix
q04/yolo-pod-cgroup-20260920-i/, unique I queues, Deployment and 1 GiB evidence PVC.
Run --offline-check, execute the full local command/ConfigMap/import/runtime
contract and interruption tests, then code review before --execute. The exact
command and scope digest are generated in RUNNER-MANIFEST.json. The committed
Deployment remains at zero until this authorized execution.

Reconfirm all 32 held Deployment UIDs and zero replicas before admission, during
the window and after cleanup. Reuse the pinned image/model and worker2 node.
Retain the same 4.5 GiB outer / 3 GiB per-case admission, 1.5 GiB runtime floor,
zero node full avg10, unchanged OOM, 4 GiB sample qualification, 5 GiB hard limit,
1s telemetry gap, 1500/825/300s budgets and existing oracle.

I differs from H only in identity and diagnostics/repair: save+flush before
rejecting; save terminal/post-cleanup samples before validation; sample both
node and cgroup PSI raw text plus memory.stat; timestamp outer stop and supervisor
interruption; restrict worker marker discovery to directories. No producer,
Activity retry policy, parser budget, fixture or threshold changes.

Fresh -> restored -> exact replay only while all preceding gates pass. Any
failure stops this window with no automatic rerun. Preserve the primary cause,
Temporal cancellation/history/result, rejection sample, worker/parser evidence,
terminal seal and readback; separate ingestion failure from cleanup completeness.
Always remove only owned runtime objects with UID fences, keep the evidence PVC
and object prefix, prove all held Deployments remain off, and do not publish to
GitHub: return a ticket-update draft for main to publish.
