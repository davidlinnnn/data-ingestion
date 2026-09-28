# Warm continuity diagnosis — implementation repaired; AIMA path qualified

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

Q execution `q04-aima-pod-cgroup-20260920-q` subsequently qualified the repaired
four-request AIMA path under the unchanged resource gates. Three group captures
and native assembly restore used PID 131/start tick 16535575; all 949 attribution
samples were complete and the lifecycle ended only after the run. Fresh,
restored and exact replay all passed business, oracle and resource checks. See
`pod-topology-v16/first-window-evidence/RESULTS.md`.

Remaining qualification work:

1. Run the original 29-group cross-document sequence and request-20 recycle;
   Q's four-request AIMA path does not exercise that boundary.
2. Requalify the remaining current-producer fixtures and interruption/recovery
   rows under their reviewed identities and unchanged guards.

P remains a conclusive incomplete-measurement result. Q does not reclassify P or
the earlier failures. Original cross-fixture, 29-group/request20 and recovery
requirements remain unchanged.
