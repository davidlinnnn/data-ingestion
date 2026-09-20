# Warm continuity diagnosis — implementation repaired, runtime not yet qualified

The committed `reproduce.py` drives actual `Execution.child` and `WarmParser`
with a small real newline-protocol subprocess, without inference. Before the
repair, capture → native restore → capture changed PID and reset the group count
because `Execution.child` sent every restore through `fresh_child_handoff`.
That contradicted the original cross-document request-20 sequence. This is
separate from P's process-membership observation gap.

The repaired source routes native checkpoint restoration through the warm
interpreter, keeps separate capture/restore converter instances, counts only
capture groups against the 20-group recycle, and releases each conversion result
before waiting for the next request. Scanned restore retains the existing fresh
child handoff. A protocol-only 29-group regression now uses two PIDs and one
planned recycle. Cancellation reaps the current process before rebuilding it,
and a corrupt restore checkpoint remains a non-retryable
`integrity/checkpoint_validation_failed` failure.

The pinned `pdf-checkpoint-prototype:linux-v2` image also completed an offline,
one-page capture → restore → capture check with one PID. Both captures ran all
five page models; restore reported only `checkpoint_load` and zero document
assembly, model initialization, or page-model inputs. The two captures produced
the same document digest. This validates real Docling mode switching, but it is
not the six-fixture resource/runtime qualification.

Completed checks:

1. The original red reproduction now passes: native restore preserves the PID
   and only captures advance the request-20 counter.
2. Focused adapter, lifecycle, continuity, identity, and Q telemetry tests pass
   (31 tests).
3. Q telemetry persists exact before/after process identity sets.
   Unknown birth transitions stay unknown; do not widen the confirmed-exit rule.
4. Standards review found no issue. Spec review found and the repair preserved
   restore integrity classification across the warm entrypoint.

Remaining qualification work:

1. Rebind stage-impact/source projections to the repaired producer. The changed
   lifecycle invalidates inherited fixture runtime qualification.
2. Run one uniquely identified six-fixture controlled runtime under the existing
   resource, PSI, OOM, and deadline limits. Do not rerun P unchanged and do not
   retry automatically.

P is a conclusive incomplete-measurement result, not a successful acceptance.
Original fixture,29-group/request20 and recovery requirements remain unchanged.
