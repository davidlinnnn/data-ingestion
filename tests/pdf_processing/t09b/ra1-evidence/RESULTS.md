# RA1 stopped before inference

Identity: `t09b-calibration-20260930-ra1`; one run, no automatic retry.
Runtime source: `88237c4`. Ten pre-inference gates passed; `workload_imports`
failed with `ValueError: warm authorization scope changed`. No workflow,
inference or object write started. This is not a recovery-cost observation.

The projected preflight imported the recovery coordinator but its retained
function still imported `validate_scope` directly from `warm_pod_window_r`.
That validator correctly rejected the new recovery scope. The previous local
projection check only exercised `--help` and coordinator imports, so it missed
execution of the real gate. The new RA2 regression invokes that exact gate
in the rendered workspace: it first reproduced the same ValueError, then passed
after changing the validator binding and reported native/11-group contract.
Historical RA1 runner, projection and original evidence are unchanged.

Cleanup disposition: `CLEANED_WITH_PVC_RETAINED_WORKLOAD_NOT_STARTED`, final
identity/health verified. All 32 held Deployments restored to zero with no owned
Pods and no restoration errors. Object service identity/configuration unchanged.
Evidence PVC `t09b-calibration-ra1-evidence-20260930` remains Bound, UID
`a2d80323-3380-4d82-bf8f-195c6f2e45a8`. Raw controller/runtime evidence remains
under the original `/private/tmp` paths and PVC. No OOM/capacity failure is
identified by this pre-inference stop; no recovery or capacity pass is claimed.

Next run uses a new RA2 identity/prefix after the gate regression and review.
