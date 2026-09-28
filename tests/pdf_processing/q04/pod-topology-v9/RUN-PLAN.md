# Single controlled J window

User authorization: initial Q04 handoff plus explicit "請執行修復" continuation,
including the proposed local repair, review and new single runtime. Use only
kind-internal-a2a-vs6-local / pdf-t09a-validation / existing worker2. No paid
infrastructure, historical deletion, held Deployment restore or threshold change.

Identity q04-yolo-pod-cgroup-20260920-j; prefix
q04/yolo-pod-cgroup-20260920-j/; unique J queues, Deployment and retained 1Gi PVC.
Commit reviewed source and generated ConfigMaps before execution. Recheck the
32 held Deployment UIDs/zero replicas, prior PVC identities and cluster health.
Run fresh -> restored -> exact replay while every preceding gate passes.

Unchanged: 4.5GiB outer / 3GiB per-case admission; 1.5GiB runtime available floor;
zero node full PSI avg10; unchanged OOM; 4GiB sampled cgroup qualification;
5GiB container limit; <=1s resource telemetry gaps; 2s transport pulls and 5s
receipt gap; 1500s window / 825s workload / 300s cleanup. The producer and its
Temporal Activity retry policy are frozen; no automatic window retry.

Stop at first failure. Keep live qualification failure separate from sealed
forensic export. Remove owned runtime with UID fences, retain J and historical
PVCs/prefixes, verify no owned Running workflow and all held Deployments off.
Preserve exact executed source/evidence; do not retry J. Return updated acceptance
matrix, uncertainty and unpublished #51 ticket text to main.
