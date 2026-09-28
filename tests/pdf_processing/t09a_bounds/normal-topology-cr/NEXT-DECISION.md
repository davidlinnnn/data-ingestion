# Proposed next step: one functional diagnostic, pending explicit decision

CR fixed policy persistence but still stopped on89us object full PSI with no
OOM/high/max event and~2.77GiB VM available. Real directory-allocation reclaim is
proved; neither harmlessness nor successful completion without cancellation is.
Repeating memory.low tuning is not supported by this evidence.

Recommended bounded diagnostic: use a fresh identity and the exact CR workload,
image,producer,bundle,32-on topology,temporary object1Gi,manager-owned768MiB low,
125s admission and existing ceilings/deadlines. Change only the object PSI stop:
retain cumulative full-total telemetry and direct traces, but stop on positive
object full avg10 rather than any nonzero cumulative full-total increase. Keep
VM/worker PSI guards, max/OOM events, memory floors, telemetry-loss and deadlines.
One attempt,fail-stop,no retry; restore manager/kernel values,object512Mi and32off.

This intentionally allows brief object PSI that rounds to0.00 avg10, so it is a
real criterion change for this diagnostic, not a correction to historical PASS/FAIL.
Local tests must prove the original CR89us sample is recorded and allowed only
under the explicit diagnostic mode, while positive avg10,OOM/max,low memory,
missing telemetry and deadline cases still stop. Review before execution.

Evaluate all five processing_complete/accepted results, complete document and
checks JSON against AI/AJ,29groups/request20 recycle/post-recycle completion,
maxima and stall totals, and complete restoration. A successful result answers
whether bounded functional work can finish despite brief object PSI. It does not
retroactively pass CR or close#44 under the original zero-event criterion; any
permanent operating-bound/acceptance revision remains a separate documented decision.

Alternative: retain literal zero object full-PSI as mandatory and stop this
candidate line. A different resource/topology configuration needs its own concrete
proposal; no evidence here selects a specific larger memory size or replacement
cluster. Hard memory.min or disabling kubelet is not proposed.

Authorization required because the user explicitly reserved acceptance-standard
changes for a concrete decision. No next diagnostic code or runtime is enabled.
