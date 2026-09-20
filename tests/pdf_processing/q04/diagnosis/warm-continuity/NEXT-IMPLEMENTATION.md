# Warm continuity diagnosis — implementation not yet qualified

The committed reproduce.py drives actual Execution.child and WarmParser with a
small real newline-protocol subprocess, without models/inference. Current source
fails: capture → assembly restore → capture changes PID and resets the group
count. Assembly's fresh_child_handoff intentionally reaps the warm parser, which
conflicts with the original cross-document request20 sequence. This is separate
from P's process-membership observation gap.

A throwaway prototype is retained only in
`/private/tmp/q04-warm-continuity-prototype/pdf_processing`, outside source/runtime
bundles. It routes native checkpoint restoration through the warm interpreter,
keeps separate capture/restore converter instances, counts only capture groups
against the20-group recycle, and releases each conversion result before waiting
for the next request. A protocol-only29-group sequence uses two PIDs and one
planned recycle. This does not validate actual Docling conversion or memory.

Before adopting any production change:

1. Exercise real parse.execute capture→restore→capture mode switching with
   instrumented no-model converters; prove restoration cannot run page stages,
   model/cache/profile checks remain strict and prior results are released.
2. Test cancellation, deadline, shutdown and shared queue serialization using
   actual owned subprocesses; unconfirmed reaping must still fail closed.
3. Persist before/after process identity sets in a new measurement version.
   Unknown birth transitions stay unknown; do not widen the confirmed-exit rule.
4. Rebind stage-impact/source projections and review the minimal source change.
   Changed lifecycle invalidates inherited fixture runtime qualification.
5. Only then propose a new uniquely identified controlled runtime under existing
   resource/PSI/OOM/deadline limits. No unchanged P rerun and no automatic retry.

P is a conclusive incomplete-measurement result, not a successful acceptance.
Original fixture,29-group/request20 and recovery requirements remain unchanged.
