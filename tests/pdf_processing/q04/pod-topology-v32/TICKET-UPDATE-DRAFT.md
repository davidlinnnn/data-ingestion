Q04 acceptance update (draft; not posted)

The acceptance-tool defects are fixed. The controller now preserves the
rejecting sample before validation, cleanup ignores `worker-*.log` files, and
owned fresh-process creation/completion/reap are serialized with process
sampling. Regression coverage includes the original cleanup failure, rejecting
sample retention, lifecycle birth/exit, lock timeout, cancellation and the
double-cancellation races found in review.

AF completed all five workflows but correctly failed qualification because one
sample overlapped fresh-child birth. That isolated the missing birth-side lock.
AG then ran once with a new identity and no automatic retry. All 11
pre-inference gates and all five workflows passed; the 29-group sequence and
request-20 recycle completed. All 1,425 process/cgroup samples were complete,
with `process_attribution_complete=true`, `cgroup_resource_complete=true`,
`peak_sample_attribution_complete=true`, and `qualification_complete=true`.
No PSI, OOM, memory-floor, deadline, Activity, supervisor or ingestion stop
occurred. Maximum sample gap was 0.678278 seconds under the unchanged one-second
bound.

Cleanup passed and was independently checked: all 32 held Deployments remain
exact/off; AG Deployment, Pod and ConfigMaps are absent; and the retained AG
PVC is Bound at UID `7770d9d2-dc31-4981-9a2e-25fc2fc07a1c`. The raw
`terminal_stop_proven=false` field means the controller did not initiate a stop
after natural success. Exit code zero, `cleanup-complete.json`, the sealed
terminal manifest and absent owned runtime prove terminal cleanup.

AG proves the bounded sequence/recycle behavior and integrated resource bounds
for its exact producer/runtime. It does not close the complete warm row because
the reviewed contract explicitly leaves required Q04 fresh-output equality
pending. The current-producer six-fixture modes, changed-profile rejection,
process/Pod interruption recovery, telemetry-loss injection and the #44 bounds
handoff also remain open. #51 is therefore not ready to close or integrate.

A strict post-run comparison of the retained AG documents confirms why the
fresh-output gate cannot be promoted: Wiki06 has 496 current text nodes versus
490 in its retained reference, and native has 1,145 versus 1,119. Both retain
the exact source-region multiset, but their graph collections differ. This is
preserved for source review; it is not treated as output equality or silently
normalized. Re-running the same producer before that review would fail at the
same gate and add no acceptance evidence.

Commits: `d20ce3c` (fresh-process creation synchronization), `acc7557` (AF
evidence and AG preparation), `56d94fb` (AG runtime evidence).
