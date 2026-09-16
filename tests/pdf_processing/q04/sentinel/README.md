# Keynote sentinel history

A subsequent, separately authorized high-capacity process-mode sentinel passed
fresh/restored/replay. See
[high-capacity-b/RESULTS.md](high-capacity-b/RESULTS.md). The first failed run
below remains preserved and is not overwritten.

## First attempt — stopped by capacity guard

The single authorized process-mode attempt on 2026-09-16 stopped during fresh
when VM PSI full avg10 reached **0.18**, above the frozen maximum of **0**.
Restored and replay were not started. No retry or relaxed threshold was used.
All 20 approved Deployments were restored and verified healthy; the reservation
was released. This is not a sentinel or Q04 acceptance pass.

See [RESULTS.md](RESULTS.md) for timing, outcomes and evidence boundaries.
`lease.py` and `cleanup.py` preserve the exact one-window orchestration used.
They contain fixed consumed run paths and are not authorization for another run.

## Authorization history

`EXECUTION-BLOCKED.json` preserves an earlier automatic approval rejection before
CreateProcess: that attempt started no window and performed no mutation.
Subsequently the user directly authorized in this task one 20-minute Keynote
fresh/restored/replay sentinel, the exact T03–T07 20-Deployment pause set, fresh
identity/idle checks, unchanged capacity guards, a final five-minute cleanup
reserve, and restoration of original replicas and health on every exit.
That direct instruction explicitly superseded the preparation-only restriction.
Only the later, directly authorized attempt described here executed.
