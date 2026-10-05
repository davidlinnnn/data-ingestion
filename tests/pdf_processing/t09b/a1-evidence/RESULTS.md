# A1 controlled attempt: stopped before workflow

Executed source commit: `0f8cf8f`. Run identity:
`t09b-calibration-20260928-a1`. This is a failed baseline attempt, not ingestion
or performance acceptance. There was one controller execution; no automatic retry.

| Gate | Result |
| --- | --- |
| Local regression before execution | 26 passed |
| Native HTTP trace readiness/remote stop | Passed after separately diagnosed missing-awk fix |
| Live capacity admission | Passed; retained admission.json |
| Created Deployment identity | Failed: historical DH keyword default |
| Pod preflight / workflow / PDF inference | Not started |
| Functional output / grouping comparison / recovery cost | Not measured |
| A1 native trace stop | Local and remote stopped; expected TERM exit 143 |
| 32 historical Deployments | Restored to zero replicas, no owned Pods |
| A1 Deployment and ConfigMaps | Deleted with UID preconditions; absence rechecked |
| A1 evidence PVC | Retained, Pending, UID 2d31187d-befa-4efa-b8c1-9cccd40289c6 |
| Object service | Same Pod/PVC/configuration; healthy, no rollout or rollback |

## Cause and fix

`validate_created_deployment` captured `t09a-bounds-dh-activities` in its keyword
default while importing the historical engine. Later rebinding globals to T09b
did not update that default. The newly created T09b Deployment therefore failed
the identity check before a worker Pod or workflow started. Related Pod/cleanup
functions retained the same historical defaults.

The regression invokes the real Deployment checker and reproduced the same
exception locally. The fix seeds T09b topology before defining the guarded
engine, then tests the Deployment check and related function signatures.
All 26 regressions pass after the fix; Standards and Spec reviews found no
actionable defects in it. A1's frozen manifests remain unchanged and intentionally
do not match the repaired source. Do not reuse A1 or refresh its manifests.

This failure supplies no inference-capacity result and no performance comparison.
The next controlled run must use a new identity, output directories, prefix and
PVC plus freshly prepared manifests. Existing safety/quality gates remain unchanged.
Full buffering attribution and comparative/recovery calibration remain open.

## Evidence and cleanup caveat

Selected controller/admission/cleanup evidence is retained here. Full raw evidence
remains at `/private/tmp/t09b-controller-20260928-a1`,
`/private/tmp/t09b-calibration-20260928-a1` and
`/private/tmp/t09b-calibration-20260928-a1-object`.

The earlier failed native-only diagnostic left a timeout zombie PID 350 in the
unchanged object container after targeted cleanup; its mc child is absent and
the zombie has zero address space. This is recorded separately in
native-lifecycle-evidence/RESULTS.md and is not represented as fully absent.
The corrected diagnostic and A1 trace both proved their own remote stop.
