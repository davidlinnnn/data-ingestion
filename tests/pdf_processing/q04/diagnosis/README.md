# Q04 PSI diagnosis and capacity preparation

This directory contains the requested offline diagnosis and read-only capacity
proposal following the failed Keynote sentinel:

- [PSI-ANALYSIS.md](PSI-ANALYSIS.md) aligns worker, parser, Temporal and resource
  evidence, ranks falsifiable causes and records observation gaps.
- [CAPACITY-PROPOSAL.md](CAPACITY-PROPOSAL.md) proposes an exact 32-Deployment
  historical PDF pause scope and restoration order for later main approval.
- `replay_pressure.py` is a deterministic captured-trace check. It performs no
  service access or inference.
- `evidence/` contains sanitized event, capacity and identity snapshots.
- [`acl-v3-b-resource/`](acl-v3-b-resource/) diagnoses the later fixture-09
  active-cgroup rejection and defines the minimum next telemetry needed before a
  qualification ceiling or lifecycle change can be reviewed.
- [`yolo-matrix-a/`](yolo-matrix-a/) reconstructs the fixture-07 group-to-assembly
  timeline, corrects `parser_count` and stale-stage interpretation, compares the
  ACL attribution trace, and proposes a fresh-only attribution calibration without
  changing the current guard.

No workflow or inference ran, no service was paused, and no production or frozen
profile code changed during this phase.
