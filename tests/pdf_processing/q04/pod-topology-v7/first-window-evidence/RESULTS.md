# Q04 YOLO Pod cgroup H window result

Status: **FAIL_VM_PSI_GUARD; no retry**.

The single authorized run used commit
`beb754d7aee116ea04878a966240f597375e0435`, run identity
`q04-yolo-pod-cgroup-20260920-h`, and authorization scope
`f5dffe42efd9bce7a6c70fee09512707a7e40e4f3f1040ba418c11806bae9aec`.
No second H run was attempted.

Outer admission passed for 61 continuous seconds with zero PSI, zero OOM and a
minimum 8,247,615,488 available bytes. Pod readiness, image/PVC identity,
durable directory setup and all 11 pre-inference gates passed. The new gate
successfully executed the complete reviewed-input contract against the H
runtime identity before workload.

Fresh fixture 07 then started. Temporal recorded one workflow. It closed with
the failed result `activity_budget_exhausted`, no canonical output and zero
registered pages. The local trace reached page-group parsing and LayoutModel;
restored and exact replay never started.

The outer controller stopped the window when a node-level full-memory PSI
sample became positive. Before that stop, 184 persisted controller samples had
zero PSI and OOM, at least 6,758,825,984 available bytes, and at most
1,674,448,896 worker-cgroup bytes. The 272 Pod-attribution samples also had
zero cgroup PSI and OOM. The exact rejecting node sample was evaluated before
the runner appended it, so its positive magnitude was not preserved. This is
an evidence-ordering limitation; it does not convert the strict PSI result to a
pass.

Cleanup removed the exact Deployment, ReplicaSet, Pod and ConfigMaps with UID
fences. The retained H PVC UID is `d05abeae-9b24-4c92-8431-a80e994187f9`
and PV UID is `f89b4353-6fe5-42e4-ac0d-a1e54aab53d1`. Final health, OOM and
PSI checks passed; all 32 held Deployments remained closed. Workload evidence
is incomplete for two reasons: the PSI stop interrupted processing, and the
workload cleanup then treated the sibling file `worker-1.log` as a
`worker-*` directory. That raised `NotADirectoryError` before it could write
and seal the terminal cleanup records. The outer UID-fenced cleanup still
proved the supervisor and Pod runtime absent.

This run does not qualify Q04. Repeating the same local-kind window without a
policy or environment change would be an uninformative retry. Any future
window must also restrict cleanup-marker discovery to directories and test the
coexisting `worker-N.log` path.
