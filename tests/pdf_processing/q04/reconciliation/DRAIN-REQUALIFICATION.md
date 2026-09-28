# Q04 drain requalification boundary

The machine-readable decision is
[`evidence/drain-requalification.json`](evidence/drain-requalification.json).
The R3 controller directly proved an owned Pod replacement: five pages retained,
only pages 6–10 retried, a new Pod UID replaced the exact deleted UID, the old CRI
container and scratch directory disappeared, and the completed graph equalled the
R3 fresh graph. Those records and their hashes remain unchanged.

The stage-impact audit marks group, assembly, selection, OCR, evidence and finalize
as directly changed from R3 to the integrated producer. The R3 injection method,
topology checks, telemetry shape, attempt-count oracle and cleanup pattern can be
reused to design a Q04 trial. Its registrations, outputs, final equality and
resource measurements cannot be counted as a Q04 pass.

Process mode remains a useful optional preflight. A pass there would prove actual
Temporal/shared-store worker-process recovery, but it cannot establish API UID,
CRI-container or `emptyDir` removal. It does not close the Pod recovery gate.

The minimum closing evidence for #51 is one newly approved native-fixture drain
with the integrated producer on a reviewed, newly owned Pod topology. It must use
an exact-UID delete precondition, preserve the first group, retry pages 6–10 only,
observe a distinct replacement UID and old runtime/scratch absence, retain VM and
old/new cgroup telemetry, and compare the checked final graph to the Q04 fresh
baseline. Failure must prove forbidden publication absence and owned cleanup.
Pod mode remains unqualified; this decision neither creates a Deployment nor
reassigns the gate to #46.
