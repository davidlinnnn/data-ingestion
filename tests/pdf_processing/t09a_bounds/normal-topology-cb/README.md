# CB: full mixed-warm trial with OCR NumPy hugepage policy

One new identity `t09a-bounds-20260927-cb`, prefix `t09a/bounds-20260927-cb/`,
using the existing worker1 placement and temporary observed 1 GiB object
limit. The only bundle content change from BU is producer `execution.py`,
which applies `NUMPY_MADVISE_HUGEPAGE=0` only to OCR subprocesses. PDFs,
oracles, models, render scale, sequence 06/07/08/native/06, 29 group requests,
request-20 recycle and formal memory/PSI/OOM/deadline gates are unchanged.
The earlier isolated diagnostic's extra VM total-PSI abort is not introduced.

The outer controller temporarily activates the 32 recorded Deployment
identities for this authorized normal-topology trial and restores them to
zero/no owned Pods after the single window. It restores object service to
512Mi/Ready, preserves evidence PVCs/prefixes, and never retries automatically.
The private-node observer sees only its subtree; its /proc pressure reading
is VM-wide, not an independent worker memory domain.

Local validation passed: exact command argument parsing and offline contract;
producer-only bundle delta; projected-workspace configuration/import gates;
29-request/request-20 scope; edited-bundle rejection; cleanup with a worker
log and missing stopped marker; complete cleanup marker case; both bounded
outer-guard handoff subprocess regressions. A preparation-only broad identity
replacement initially changed bundle identifier names and was corrected
before any runtime; the actual projected import/configuration check catches it.

Runtime status: FAILED_OBJECT_PSI; complete failure evidence and restoration verified. The full result, not these local checks, decides
whether this candidate qualifies. Historical runners and manifests are intact.
