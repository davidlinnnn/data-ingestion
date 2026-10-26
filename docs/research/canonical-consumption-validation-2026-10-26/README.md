# Canonical consumption validation (#55)

Evidence for the reporting, repair and change-discovery rules of the
[#55 design record](../../design/knowledge-platform-canonical-consumption.md)
(§5 and §7). Codex implemented and ran the experiments from briefs the main
line wrote; each round passed a reviewed rule mapping and a smoke test before
its full batches ran. Results were verified by `round2/verify.py` and
recounted independently.

## Round 1: PostgreSQL feed ordering (part A)

`part_a.py`, driven by `run_part_a.sh`, ran 8 writer processes × 400
transactions per seed against PostgreSQL 18.4, with rollbacks and 3-second
transactions, and two live consumers:

- Consumer A, a sequence-only cursor, missed 279, 276 and 297 of about 3,030
  committed rows per seed (about 9%).
- Consumer B, ordered by (`xid8`, sequence) and filtered below the snapshot
  xmin, missed and duplicated nothing. Its maximum delay, about 3 seconds,
  equals the longest open transaction.

See `part-a-results.md`. Before publication, `run_part_a.sh` and `part_a.py`
were changed to take the throwaway database password from
`PART_A_PG_PASSWORD` instead of a literal, to drop a local command wrapper and
to run from this directory; the experiment logic is unchanged. This is the
evidence behind A5 and
[ADR-0009](../../adr/0009-cursor-feed-change-discovery.md).

`part_b.py` and `MODEL.md` are the round-1 protocol model. Round 2 imports and
extends `part_b.py` without changing it. Its round-1 results
(`part-b-results.md`) are superseded: the round-1 brief's S1 predicate covered
every Document instead of deleted ones, and one injected corruption kept counts
equal, which a count-only heartbeat cannot detect by design. Round 2 corrected
both.

## Round 2: reporting and repair protocol

| File | Content |
|---|---|
| `round2/model.py`, `round2/scenarios.py` | The discrete-event model and the deterministic scenarios |
| `round2/MAPPING.md` | Design rule → code, invariant → exact predicate, fault → expected detection, scenario → expected verdict |
| `round2/SMOKE.md` | The last smoke test before the full batches (phase 1d) |
| `round2/phase2.py` | Full batches: 20 groups × 1,000 seeds plus 33 deterministic cells |
| `round2/REPORT.md` | Tables, witnesses and limits; every number is recomputed by `verify.py` |
| `round2/verify.py`, `round2/test_model.py` | Verifier (recompute, workload hashes, witness replay) and model unit tests |
| `round2/phase2/deterministic.jsonl`, `evidence.json`, `metadata.json` | Deterministic results, witness evidence, run metadata (the interpreter path is replaced by `{PROTOTYPE}`) |
| `round2/phase2/traces/` | The 125 traces `REPORT.md` links to |

Variants in the tables: V1 has no registration; V2 adds registration with
mark-and-sweep repair; V3 adds the digest heartbeat; V4 is the adopted design.
`V4-Ra` and `V4-Rb` remove one rule each; `N2`, `N12`, `N-fence` and
`N-viewexp` are negative controls.

## Not in git

`EXCLUDED.sha256` lists, with size and SHA-256, every file of the prototype
that is not committed, 197 MB in total:

- `round2/phase2/raw/*.jsonl`, the per-seed records `verify.py` reads;
- the round-2 phase 1 to 1d snapshots (`round2/phase1*`);
- the round-1 control and witness runs;
- traces not linked from the report.

They are kept in the maintainer's offline archive. To re-run `verify.py`,
restore `round2/phase2/raw/` and check it against the manifest, or regenerate
it with `round2/phase2.py`; the workloads are deterministic per seed, and
`REPORT.md` lists the workload hashes. Python 3.9 with the standard library is
enough for round 2; part A also needs Docker and psycopg (see `environment.json`).
