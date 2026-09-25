# Q04 AH v3 warm candidate

Status: **completed bounded warm/resource runtime; full #51 acceptance pending**.
See [the independently verified result](first-window-evidence/RESULTS.md).
AH has a new run identity
`q04-warm-pod-cgroup-20260924-ah`, object prefix
`q04/warm-pod-cgroup-20260924-ah/`, and retained evidence PVC
`q04-pod-cgroup-ah-evidence-20260924-ah`. The existing kind cluster and
`pdf-t09a-validation` namespace were reused. The committed topology began
inactive at zero replicas; the one controlled execution completed and cleaned
up its Pod, Deployment and ConfigMaps.

The private bundle `/private/tmp/q04-inputs-warm-continuation-v3-ah` differs
from the retained AG bundle only at `producer.continuation.py` and
`base_profile.method.continuation`; its derivation is checked before inference.
All six source PDFs, original PDFs, references, oracles, other producer files,
and frozen test files retain their AG hashes. The unchanged 29-group sequence,
request-20 recycle, 250 ms process samples, one-second attribution gap, node
and Pod pressure guards, OOM guard, memory floors, and deadlines still apply.
Automatic retry remains disabled.

Unlike AG's measurement-only native/Wiki path, AH requires every output to
match an exact v3 graph digest. Native and Wiki06 use the source-reviewed
38-split [oracle](../diagnosis/continuation-v3/EXACT-ORACLE.json). YOLO's
exact digest equals the retained AG warm document whose two reviewed split
regions passed its fixture-local validator. AIMA's exact digest equals the AG
warm document and still runs the independent source-image supplement; ACL and
Keynote must equal their historical reference graphs. The ordinary consumer
then checks all selected work, page evidence, OCR, relationships, and source
identity through durable storage reads. None of these local comparisons
promotes a runtime row on its own.

Local AH adapter checks passed in the pinned runtime image: all six exact graphs,
method and graph mutations, bundle derivation, complete startup arguments,
projected workspace imports, inactive topology, interruption sealing and
cleanup with a `worker-1.log` sibling. The inherited supervisor interruption
regressions pass on the host. The [source manifest](SOURCE-MANIFEST.json),
[inactive topology](WORKER.yaml), [runtime manifest](RUNTIME-INTEGRATION-MANIFEST.json),
and [runner manifest](RUNNER-MANIFEST.json) bind the executable plan.
Independent code review and live admission passed. The
fresh/restored/replay matrix and other #51 recovery gates remain separate
until proven.
