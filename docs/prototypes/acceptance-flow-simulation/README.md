# Acceptance flow simulation (#57)

**Question.** Do the rules of #57 group B converge to the right state under every interleaving of
submissions, updates, results, deletions, adoptions and rollbacks? The rules: Canonical Acceptance
as one transaction, no acceptance for a deleted Document, current-revision selection by (Source
Revision order, adoption sequence), a failed request when an enrichment item has no result, and a
sweep that refreshes existing Documents by the refresh scope declared with each adoption.

`sim.py` models the platform-database side only. No Temporal, no database, no dependencies.

```
.venv/bin/python docs/prototypes/acceptance-flow-simulation/sim.py [random runs] [seed]
```

## Verdict (2026-11-22, seed 57, 20,000 random runs, about 3 s)

- The acceptance transaction and the selection rule hold: the current revision never depends on
  the order in which results arrive. Replacing the rule with completion order fails 711 of 2,000
  runs.
- The sweep rule as first written (`v1`) is wrong: a rollback after 5 of 50 Documents were
  refreshed opens 50 requests; the corrected rule opens 5.
- The sweep needs a retry arm for a Document whose latest Source Revision failed, whatever the
  refresh scope, with a cap per adoption. Without the arm 766 of 2,000 runs leave such a Document
  uncounted; without the cap a failing refresh is reopened on every run.
- A rollback needs a withdrawn-version record that outlives the rollback's own adoption (`v3`).
  With the latest adoption's scope alone (`v2`), 3,721 of 20,000 runs end with a Document served
  from the withdrawn version.
- The sweep's "no active request for the Document" check is an economy, not a safety property:
  removing it fails 0 of 2,000 runs.

The mutation runs behind these numbers patch `World` from a throwaway script; they are not in this
directory.

## Not covered

Temporal and Kubernetes (the gate, CronJob overlap), database locks and transactions on either
engine, priorities and capacity, re-dispatch and stale attempts, a second media type, a Source
Revision rejected for a source cause. The simulation checks rules, not code: the acceptance
transaction (#251) and the sweep (#98) are not built.
