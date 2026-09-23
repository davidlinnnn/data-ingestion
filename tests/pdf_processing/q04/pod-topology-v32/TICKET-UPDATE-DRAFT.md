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

The native source review found five incorrect reading-order joins among its six
many-to-many components: AG connects text into the same column on the next page
across intervening source columns. The sixth component is a duplicate picture
label with unchanged local relations. The current native graph is rejected;
the remaining 23 native splits and six Wiki06 splits are not yet approved.
The v1 continuation rule is consistent with the invalid joins, but sole cause
is not proven without pre-merge elements. No historical reference, oracle or
acceptance threshold changed.

Subsequent local v2 diagnosis used the exact PDF and a pinned offline model
image. Replaying full native pre-merge checkpoints proved v1 made those six
invalid edges and v2 removes exactly those six with no additions. Full local
native and Wiki06 captures preserve all source fragments. Native now differs
from the retained reference by 32 ordered body-text splits; Wiki06 by six.
A diagnostic-only reconstruction of those exact splits matches all nine graph
collections for both fixtures. Local checkpoint restoration reproduced the full
native and Wiki06 capture documents byte for byte. All 38 splits were then
source-reviewed, including the seven with an intervening table, picture or
caption. A fixture-specific exact v2 graph oracle is now frozen; mutation
checks reject an additional source-preserving split and changes to text,
geometry, relationships, table cells or body order. This is an offline oracle
decision only. Fresh, restored, exact replay and affected warm/recovery rows
remain unproven until a new-identity controlled runtime passes. #51 remains open.

Before runtime, six-fixture offline projection found that v2 split one valid
AIMA page 5–6 continuation because a narrow page-margin picture appeared
between text parts in Docling reading order. A red regression reproduced this;
code review added a counterexample requiring a narrow picture inside the body
column to remain a blocker. Final v3 ignores only narrow pictures outside the
horizontal span of the wide body text on that page. Fresh local captures under
this source restore the exact AG AIMA document, while full native/Wiki06/YOLO
documents stay byte-for-
byte equal to the reviewed captures and ACL/Keynote full graphs equal their
references. The 38-split source review therefore remains applicable to v3;
the v3 method and exact fixture graph hashes are frozen. These are local
diagnostics, not a Q04 runtime PASS. The next runtime needs a new identity,
v3-bound bundle, local preflight review and one controlled attempt.

Commits: `d20ce3c` (fresh-process creation synchronization), `acc7557` (AF
evidence and AG preparation), `56d94fb` (AG runtime evidence).
