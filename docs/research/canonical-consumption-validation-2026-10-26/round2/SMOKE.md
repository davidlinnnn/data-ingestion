# Round 2, phase 1d — smoke

**Only seeds 0–4. No full batches.** 30 protocol checks passed. Round 1 is untouched; phase-1, phase-1b and phase-1c code/results are preserved under their phase prefixes.

**90 random runs: 74 PASS, 16 FAIL, 0 UNKNOWN.** S2/S3 are measurements, not failures. L0 bounds fail; other bounds stay UNKNOWN. L1–L5 are evaluated only at quiescence.

## Findings and deviations

- **Harness bug fixed:** phase-1 mapping specified a 90-tick deadline for snapshot transfers and restart on timeout; the V4 replacement path omitted it. Every protected view now has an active deadline from capture time, late pages cannot complete it, and retry takes a new view. All affected smoke cells were rerun.
- **Replacement expiry fence added:** candidate entries use their original fact version and view capture time in the same expired-tombstone predicate as reports, before stamping W. A rejected candidate aborts the atomic replacement and requests a fresh view. N-viewexp removes exactly these two guards; N12 retains its expired-reference acceptance mutation.
- **SC24 matches:** V4 PASS; N-viewexp produces S1_flipback. The stale original page arrives at t135, after the original v2 tombstone expiry at t132. V4 had discarded that view at t100 and replaced it from current state at t101. The control installs the stale included v1 and flips enforcement.
- **SC20r/SC20u separate announced restore from silent drift:** the runbook repairs announced restores for all four variants; a silent equal-count rewind has no gate or repair request, so count-only V1/V2 fail L2 while V3/V4 repair via digest.
- **NC3 dropped by the main-line decision:** its never-registered mirror key is not reachable through V4 register-before-write. The replacement fence appears redundant given pending-before-write, W tombstones and the expiry fence. NC2/N-fence is masked by its tombstone. V4 keeps its fence; testing N-fence with 1,000 seeds on each of all three workloads is reserved for phase 2 and was NOT run here.
- **Silent drift can immediately reverse an earlier enforcement judgment before a heartbeat repairs it.** W-drift has no operator gate. Those fact-based reversals remain failures under the unchanged invariants, even if the run later converges. The observed V4 results for all three workloads are in the tables below.

## V4 headline

W-real: 5/5 PASS, 0 fact-based flip-backs; W-rewind: 5/5 PASS, 0 fact-based flip-backs; W-drift: 1/5 PASS, 4 fact-based flip-backs. All five V4 runs under each workload reach quiescence. W-drift failures remain failures despite final L1–L5 convergence.

**Deterministic matrix: 33/33 cells match; 0 deviations.**

## Random verdicts

| Workload | Variant | Seed 0 | Seed 1 | Seed 2 | Seed 3 | Seed 4 |
|---|---|---|---|---|---|---|
| W-real | V1 | PASS | PASS | PASS | PASS | PASS |
| W-real | V2 | FAIL (L0) | PASS | FAIL (L0) | FAIL (L0) | PASS |
| W-real | V3 | PASS | PASS | PASS | PASS | PASS |
| W-real | V4 | PASS | PASS | PASS | PASS | PASS |
| W-rewind | V1 | PASS | PASS | PASS | PASS | PASS |
| W-rewind | V2 | PASS | PASS | PASS | PASS | PASS |
| W-rewind | V3 | PASS | PASS | PASS | PASS | PASS |
| W-rewind | V4 | PASS | PASS | PASS | PASS | PASS |
| W-drift | V1 | FAIL (S1_flipback) | PASS | PASS | PASS | FAIL (S1_flipback) |
| W-drift | V2 | PASS | PASS | FAIL (S1_flipback) | FAIL (S1_flipback) | FAIL (S1_flipback) |
| W-drift | V3 | FAIL (S1_flipback) | PASS | FAIL (S1_flipback) | FAIL (S1_flipback) | FAIL (S1_flipback) |
| W-drift | V4 | FAIL (S1_flipback) | PASS | FAIL (S1_flipback) | FAIL (S1_flipback) | FAIL (S1_flipback) |
| W-real | V4-Ra | PASS | PASS | PASS | PASS | PASS |
| W-real | V4-Rb | PASS | PASS | PASS | PASS | PASS |
| W-real | N2 | PASS | PASS | PASS | PASS | PASS |
| W-real | N12 | PASS | PASS | PASS | PASS | PASS |
| W-real | N-fence | PASS | PASS | PASS | PASS | PASS |
| W-real | N-viewexp | PASS | PASS | PASS | PASS | PASS |

## Invariants — seeds with a failure

Quiescent is the denominator for L1–L5. Zero in an unevaluated property is not a pass. Current V1 is the fair two-step design; the old atomic model is excluded.

| Workload | Variant | Quiescent | S1 | S1_flipback | S7 | L0 | L1 | L2 | L3 | L4 | L5 | Raw / liveness-gate / restore-gate / fact flips | UNKNOWN |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| W-real | V1 | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 / 1 / 0 / 0 | 0 |
| W-real | V2 | 2/5 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 1 / 1 / 0 / 0 | 0 |
| W-real | V3 | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 / 1 / 0 / 0 | 0 |
| W-real | V4 | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 / 1 / 0 / 0 | 0 |
| W-rewind | V1 | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 / 1 / 3 / 0 | 0 |
| W-rewind | V2 | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 / 1 / 5 / 0 | 0 |
| W-rewind | V3 | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 / 1 / 5 / 0 | 0 |
| W-rewind | V4 | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 / 1 / 5 / 0 | 0 |
| W-drift | V1 | 5/5 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 / 1 / 0 / 2 | 0 |
| W-drift | V2 | 5/5 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 / 1 / 0 / 3 | 0 |
| W-drift | V3 | 5/5 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 / 1 / 0 / 4 | 0 |
| W-drift | V4 | 5/5 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 / 1 / 0 / 4 | 0 |
| W-real | V4-Ra | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 / 1 / 0 / 0 | 0 |
| W-real | V4-Rb | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 / 1 / 0 / 0 | 0 |
| W-real | N2 | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 / 1 / 0 / 0 | 0 |
| W-real | N12 | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 / 1 / 0 / 0 | 0 |
| W-real | N-fence | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 / 1 / 0 / 0 | 0 |
| W-real | N-viewexp | 5/5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 / 1 / 0 / 0 | 0 |

## Late landings — mean / p95 / max per run

Counts are source entries: two-source Wiki writes can add two. `late_landings` counts each initially admitted source once if eligibility or revision drifts after check/register. Already-invalid sources (e.g. Rb) are separate. `S2_at_write` / `S3_at_write` retain all original boundary observations. `late_transactions` counts affected document/page transactions. None fails a run. Bound-hit observations are censored.

| Workload | Variant | late_landings | late_S2 | late_S3 | late_transactions | already_invalid_landings | S2_at_write | S3_at_write |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| W-real | V1 | 7.00 / 11 / 11 | 1.20 / 2 / 2 | 6.40 / 10 / 10 | 6.60 / 10 / 10 | 0.00 / 0 / 0 | 1.20 / 2 / 2 | 6.40 / 10 / 10 |
| W-real | V2 | 5.60 / 11 / 11 | 1.40 / 4 / 4 | 4.80 / 10 / 10 | 5.40 / 10 / 10 | 0.00 / 0 / 0 | 1.40 / 4 / 4 | 4.80 / 10 / 10 |
| W-real | V3 | 4.60 / 7 / 7 | 1.80 / 4 / 4 | 3.80 / 6 / 6 | 4.40 / 6 / 6 | 0.00 / 0 / 0 | 1.80 / 4 / 4 | 3.80 / 6 / 6 |
| W-real | V4 | 6.40 / 9 / 9 | 1.80 / 3 / 3 | 5.40 / 8 / 8 | 6.00 / 8 / 8 | 0.00 / 0 / 0 | 1.80 / 3 / 3 | 5.40 / 8 / 8 |
| W-rewind | V1 | 7.00 / 11 / 11 | 1.20 / 2 / 2 | 6.40 / 10 / 10 | 6.60 / 10 / 10 | 0.00 / 0 / 0 | 1.20 / 2 / 2 | 6.40 / 10 / 10 |
| W-rewind | V2 | 5.60 / 11 / 11 | 1.40 / 4 / 4 | 4.80 / 10 / 10 | 5.40 / 10 / 10 | 0.00 / 0 / 0 | 1.40 / 4 / 4 | 4.80 / 10 / 10 |
| W-rewind | V3 | 4.60 / 7 / 7 | 1.80 / 4 / 4 | 3.80 / 6 / 6 | 4.40 / 6 / 6 | 0.00 / 0 / 0 | 1.80 / 4 / 4 | 3.80 / 6 / 6 |
| W-rewind | V4 | 6.40 / 9 / 9 | 1.80 / 3 / 3 | 5.40 / 8 / 8 | 6.00 / 8 / 8 | 0.00 / 0 / 0 | 1.80 / 3 / 3 | 5.40 / 8 / 8 |
| W-drift | V1 | 7.00 / 11 / 11 | 1.20 / 2 / 2 | 6.40 / 10 / 10 | 6.60 / 10 / 10 | 0.00 / 0 / 0 | 1.20 / 2 / 2 | 6.40 / 10 / 10 |
| W-drift | V2 | 5.60 / 11 / 11 | 1.40 / 4 / 4 | 4.80 / 10 / 10 | 5.40 / 10 / 10 | 0.00 / 0 / 0 | 1.40 / 4 / 4 | 4.80 / 10 / 10 |
| W-drift | V3 | 4.60 / 7 / 7 | 1.80 / 4 / 4 | 3.80 / 6 / 6 | 4.40 / 6 / 6 | 0.00 / 0 / 0 | 1.80 / 4 / 4 | 3.80 / 6 / 6 |
| W-drift | V4 | 6.40 / 9 / 9 | 1.80 / 3 / 3 | 5.40 / 8 / 8 | 6.00 / 8 / 8 | 0.00 / 0 / 0 | 1.80 / 3 / 3 | 5.40 / 8 / 8 |
| W-real | V4-Ra | 7.40 / 9 / 9 | 2.60 / 3 / 3 | 6.40 / 8 / 8 | 7.00 / 8 / 8 | 0.00 / 0 / 0 | 2.60 / 3 / 3 | 6.40 / 8 / 8 |
| W-real | V4-Rb | 5.80 / 8 / 8 | 1.80 / 3 / 3 | 5.00 / 7 / 7 | 5.20 / 8 / 8 | 3.20 / 8 / 8 | 2.80 / 6 / 6 | 7.80 / 9 / 9 |
| W-real | N2 | 6.40 / 9 / 9 | 1.80 / 3 / 3 | 5.40 / 8 / 8 | 6.00 / 8 / 8 | 0.00 / 0 / 0 | 1.80 / 3 / 3 | 5.40 / 8 / 8 |
| W-real | N12 | 6.40 / 9 / 9 | 1.80 / 3 / 3 | 5.40 / 8 / 8 | 6.00 / 8 / 8 | 0.00 / 0 / 0 | 1.80 / 3 / 3 | 5.40 / 8 / 8 |
| W-real | N-fence | 7.00 / 11 / 11 | 2.80 / 4 / 4 | 6.00 / 10 / 10 | 6.20 / 10 / 10 | 0.00 / 0 / 0 | 2.80 / 4 / 4 | 6.00 / 10 / 10 |
| W-real | N-viewexp | 6.40 / 9 / 9 | 1.80 / 3 / 3 | 5.40 / 8 / 8 | 6.00 / 8 / 8 | 0.00 / 0 / 0 | 1.80 / 3 / 3 | 5.40 / 8 / 8 |

## Repair snapshots per seed

Starts are per Build, summed per seed; p95 is nearest-rank. Bound-hit costs at 30,000 events are censored. Transient mismatch means absent before the next heartbeat in a fork suppressing new repairs. The fork retains existing repairs and copies state/RNG; removed repair work can change subsequent RNG consumption. Only heartbeat starts are classified as transient mismatches.

| Workload | Variant | Seed 0–4 | Mean | p95 | Transient / all starts | Transient / heartbeat starts |
|---|---|---|---:|---:|---:|---:|
| W-real | V1 | 15, 14, 21, 19, 14 | 16.60 | 21 | 31/83 (37.35%) | 31/72 (43.06%) |
| W-real | V2 | 3058, 20, 2473, 2468, 18 | 1607.40 | 3058 | 23/8037 (0.29%) | 23/8029 (0.29%) |
| W-real | V3 | 20, 24, 22, 21, 20 | 21.40 | 24 | 27/107 (25.23%) | 27/100 (27.00%) |
| W-real | V4 | 20, 17, 25, 24, 10 | 19.20 | 25 | 29/96 (30.21%) | 29/86 (33.72%) |
| W-rewind | V1 | 16, 15, 22, 20, 15 | 17.60 | 22 | 31/88 (35.23%) | 31/72 (43.06%) |
| W-rewind | V2 | 26, 21, 26, 22, 19 | 22.80 | 26 | 23/114 (20.18%) | 23/101 (22.77%) |
| W-rewind | V3 | 21, 25, 23, 22, 21 | 22.40 | 25 | 27/112 (24.11%) | 27/100 (27.00%) |
| W-rewind | V4 | 21, 18, 26, 25, 12 | 20.40 | 26 | 29/102 (28.43%) | 29/86 (33.72%) |
| W-drift | V1 | 16, 15, 22, 20, 15 | 17.60 | 22 | 31/88 (35.23%) | 31/77 (40.26%) |
| W-drift | V2 | 26, 21, 26, 22, 19 | 22.80 | 26 | 23/114 (20.18%) | 23/106 (21.70%) |
| W-drift | V3 | 21, 25, 23, 22, 21 | 22.40 | 25 | 27/112 (24.11%) | 27/105 (25.71%) |
| W-drift | V4 | 21, 18, 26, 25, 12 | 20.40 | 26 | 29/102 (28.43%) | 29/91 (31.87%) |
| W-real | V4-Ra | 24, 17, 23, 24, 9 | 19.40 | 24 | 26/97 (26.80%) | 26/84 (30.95%) |
| W-real | V4-Rb | 20, 17, 21, 22, 21 | 20.20 | 22 | 22/101 (21.78%) | 22/85 (25.88%) |
| W-real | N2 | 20, 17, 25, 24, 10 | 19.20 | 25 | 29/96 (30.21%) | 29/86 (33.72%) |
| W-real | N12 | 20, 17, 25, 24, 10 | 19.20 | 25 | 29/96 (30.21%) | 29/86 (33.72%) |
| W-real | N-fence | 19, 28, 23, 25, 15 | 22.00 | 28 | 37/110 (33.64%) | 37/94 (39.36%) |
| W-real | N-viewexp | 20, 17, 25, 24, 10 | 19.20 | 25 | 29/96 (30.21%) | 29/86 (33.72%) |

V4 versus V3 directly:

| Workload | V3 mean / p95 | V4 mean / p95 | Mean delta V4−V3 |
|---|---:|---:|---:|
| W-real | 21.40 / 24 | 19.20 / 25 | -2.20 |
| W-rewind | 22.40 / 25 | 20.40 / 26 | -2.00 |
| W-drift | 22.40 / 25 | 20.40 / 26 | -2.00 |

## Deterministic matrix — expectations retained

| Schedule | Variant | Expected | Observed | Late S2 / S3 / combined | Already invalid | Raw S2 / S3 | Match? |
|---|---|---|---|---:|---:|---:|---|
| SC15 | V1 | FAIL S1 | FAIL (S1, S1_flipback) | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC15 | V2 | PASS | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC15 | V3 | PASS | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC15 | V4 | PASS | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC16 | V3 | PASS | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC16 | V4 | PASS | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC16 | V4-Ra | FAIL L5 | FAIL (L1, L5) | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC18 | V3 | PASS; already invalid =0 | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC18 | V4 | PASS; already invalid =0 | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC18 | V4-Rb | PASS; already invalid ≥1 | PASS | 0 / 0 / 0 | 1 | 1 / 1 | yes |
| SC19 | V3 | PASS | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC19 | V4 | PASS | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC19 | N12 | FAIL S1_flipback | FAIL (S1_flipback) | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC20r | V1 | PASS; restore repair | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC20r | V2 | PASS; restore repair | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC20r | V3 | PASS; restore repair | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC20r | V4 | PASS; restore repair | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC20u | V1 | FAIL L2 | FAIL (L2) | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC20u | V2 | FAIL L2 | FAIL (L2) | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC20u | V3 | PASS; digest repair | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC20u | V4 | PASS; digest repair | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| NC2 | V3 | PASS | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| NC2 | V4 | PASS | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| NC2 | N2 | PASS; masked by V4 fence | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| NC2 | N-fence | PASS; masked by tombstone | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC21 | V2 | FAIL L0 | FAIL (L0) | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC21 | V3 | FAIL L0 | FAIL (L0) | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC21 | V4 | PASS | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC22 | V3 | FAIL L4 | FAIL (L2, L4) | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC22 | V4 | PASS; age repair | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC23 | V4 | PASS | PASS | 1 / 1 / 1 | 0 | 1 / 1 | yes |
| SC24 | V4 | PASS | PASS | 0 / 0 / 0 | 0 | 0 / 0 | yes |
| SC24 | N-viewexp | FAIL S1_flipback or L2 | FAIL (S1_flipback) | 0 / 0 / 0 | 0 | 0 / 0 | yes |

## SC24 / V4 — exactly 30 trace lines

All protocol lines plus selected actual boundary observations from `SC24-V4-trace.txt`, in their original order. View at t10; delete t11; remove v2 t12; deadline at t100 takes a fresh empty view; replacement completes t101; stale original page at t135 is ignored. N-viewexp has neither guard and installs included v1 after tombstone expiry, causing S1_flipback.

```text
0010 replacement view 1 retrieval-0 W=1 store=1 unfinished=0 pages=1
0010 view 1 page=0 ('d0', 'r0') included rev=1 original_v=1
0010 SCRIPT replacement 1 last page held until=135
0010 boundary script_view counter=1 fence=0 store_v=1 mirror=included/v1 unfinished=0
0011 action delete ['d0']
0011 feed 1 current_revision_changed d0
0011 feed 2 document_deleted d0
0011 boundary action counter=1 fence=0 store_v=1 mirror=included/v1 unfinished=0
0012 SCRIPT store remove ('d0', 'r0') v=2
0012 fact ('retrieval-0', 'd0', 'r0') removed rev=None v=2
0012 ENFORCED d0 true
0012 boundary script_remove counter=2 fence=0 store_v=2 mirror=removed/v2 unfinished=0
0012 deliver retrieval feed=1 current_revision_changed d0
0012 boundary poll counter=2 fence=0 store_v=2 mirror=removed/v2 unfinished=0
0012 deliver wiki feed=1 current_revision_changed d0
0012 boundary poll counter=2 fence=0 store_v=2 mirror=removed/v2 unfinished=0
0013 read retrieval-0 trigger=d0 source=d0 desired=None
0013 boundary dispatch counter=2 fence=0 store_v=2 mirror=removed/v2 unfinished=0
0013 boundary cursor_report counter=2 fence=0 store_v=2 mirror=removed/v2 unfinished=0
0013 deliver retrieval feed=2 document_deleted d0
0013 boundary poll counter=2 fence=0 store_v=2 mirror=removed/v2 unfinished=0
0013 boundary cursor_report counter=2 fence=0 store_v=2 mirror=removed/v2 unfinished=0
0013 deliver wiki feed=2 document_deleted d0
0015 read retrieval-0 trigger=d0 source=d0 desired=None
0100 DISCARD replacement 1 retrieval-0 reason=view_lifetime age=90; fresh view
0100 replacement view 2 retrieval-0 W=2 store=0 unfinished=0 pages=1
0101 replacement page 2 index=0 arrived records=0
0101 fact ('retrieval-0', 'd0', 'r0') removed rev=None v=2
0101 replacement 2 atomic END retrieval-0 fence=2
0135 IGNORE obsolete replacement page 1 index=0
```

## Affected Ra witness rerun

Phase-1c evidence is preserved in `phase1c-V4-Ra-W-real-seed4-trace.txt` and its causal explanation in `phase1c-SMOKE.md`. The corrected run is in `V4-Ra-W-real-seed4-trace.txt`: view 2 at t136 is discarded at t226 (age 90), and its late page at t308 is ignored. Seed 4 now PASSes. The seed/workload and all non-transfer rules are unchanged; additional timeout events can change later scheduler RNG consumption. SC24 isolates the same late-view mechanism.

## Evidence and reproduction

Raw results, witnesses, queue cycles and metrics: `smoke-runs.jsonl`, `scenario-runs.jsonl`, `smoke-summary.json`. Every schedule has a full trace.

```sh
prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/smoke.py
prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/smoke.py --scenario SC24 V4
prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/smoke.py --replay V4 W-real 0
prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/phase1-replay.py --replay V3 W-real 0
```

Round-1 `part_b.py` SHA-256: `97b602f4afba5ae583628fecaa832d364ce96ef682782816d0d63ae47fa23796`. Archived files are verified by `phase1-manifest.json`, `phase1b-manifest.json` and `phase1c-manifest.json`. The original cycle evidence and reduction remain in the `phase1c-SC21-WITNESS.md`, `phase1c-SC21-source-witness.txt` and `phase1c-cycle-witnesses.json` archives. No network, paid calls, new dependencies, commits, pushes or GitHub operations.

**Stopped after phase 1d. Full batches intentionally not run.**
