# Ticket 55 round 2 — phase 2 report

Generated and checked by `verify.py` from the phase-2 JSONL and timing metadata. The phase-1d model, mapping and scenario expectations are unchanged. The approved W-drift acceptance exception is applied outside the model: raw fact-based flip-backs remain recorded, but do not fail that workload.

## What ran

Batch command: `prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/phase2.py`. Report commands: `prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/verify.py --write` and the same command without `--write` to check.

Python: `3.9.6 (default, Apr 17 2026, 18:15:52)  [Clang 21.0.0 (clang-2100.1.1.101)]`; platform: `macOS-26.4-arm64-arm-64bit`. Workers: 12. Seeds: 0–999 inclusive for every listed group. Protocol checks: 30.

Accepted totals: 20000 runs; 18624 PASS, 1376 FAIL, 0 UNKNOWN. UNKNOWN is never counted as PASS. L1–L5 are checked only at quiescence; bound-hit repair costs are censored.

| Set | Groups | Runs | Wall seconds |
| --- | --- | --- | --- |
| Main | 12 | 12000 | 591.857 |
| ablations | 2 | 2000 | 23.141 |
| fence | 3 | 3000 | 37.921 |
| controls | 3 | 3000 | 36.554 |
| Deterministic | defined scenario rows | 33 | 1.030 |

Main includes the V4 priority pass followed by remaining variants. Wall times are elapsed set times across parallel workers, not summed worker times. Raw records are in `phase2/raw/`; deterministic records in `phase2/deterministic.jsonl`; timing/version data in `phase2/metadata.json`.

Workload hashes were recomputed from the frozen workload generator and compared for every variant/seed. The following digests summarize the ordered seed/hash pairs:

| Workload | Distinct seeds | SHA-256 of ordered seed/hash pairs |
| --- | --- | --- |
| W-real | 1000 | b4c910e5b01b11a4050524b8e8cc732f9413cfb118556a7e7c4f6b643f93038d |
| W-rewind | 1000 | 07f7c8083e7feb9c244426baedbbe242653f1e9d369db99c516e82e488720371 |
| W-drift | 1000 | db442a835fa8c3446a120fb04c33c816e5f14142741a4a8f8916c02cfc5c01fd |

Model and validation code hashes (the model/mapping remain frozen):

| File | SHA-256 |
| --- | --- |
| model.py | debe2c8d30ce6e6dd456f181464c427b3f0413cea427c78629346dc37242eb52 |
| scenarios.py | 9b0926bb3af6e83472fdcefea89908ef0674b32841d57d2dae1e5f73edbe2006 |
| MAPPING.md | ccf19f77d00293f321b0ce10d4ff4e0418644ca0de584e33ee52cf26c6cad73b |
| ../part_b.py | 97b602f4afba5ae583628fecaa832d364ce96ef682782816d0d63ae47fa23796 |
| phase2.py | 381f9066558dbeb7abfbb83ae46b8ffc1ac320c3766e490c84033b5132b169b3 |
| verify.py | e886cbf6c6f2301b1aa4b333b3b993b2de0c96ca6a2e463ccede52b84b16d7db |

## Main invariants

Cells count seeds with at least one violation, not atomic-event counts. **S1_flipback† under W-drift is exposure only**, excluded from FAIL. Liveness-gate and restore-gate flips are separate metrics. Zero in a quiescence-only invariant is not a pass for a bound-hit seed.

| Variant | Workload | S1 | S1_flipback† | S7 | L0 | L1 | L2 | L3 | L4 | L5 | UNKNOWN | Quiescent | PASS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V1 | W-real | 7 | 7 | 0 | 0 | 0 | 12 | 0 | 0 | 2 | 0 | 1000 | 980 |
| V1 | W-rewind | 7 | 7 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1000 | 991 |
| V1 | W-drift | 7 | 749 | 0 | 0 | 0 | 245 | 0 | 0 | 236 | 0 | 1000 | 750 |
| V2 | W-real | 46 | 2 | 0 | 130 | 0 | 12 | 0 | 12 | 0 | 0 | 870 | 821 |
| V2 | W-rewind | 46 | 2 | 0 | 40 | 0 | 2 | 0 | 2 | 0 | 0 | 960 | 913 |
| V2 | W-drift | 46 | 724 | 0 | 53 | 0 | 176 | 0 | 114 | 162 | 0 | 947 | 736 |
| V3 | W-real | 66 | 5 | 0 | 163 | 0 | 5 | 0 | 5 | 0 | 0 | 837 | 776 |
| V3 | W-rewind | 66 | 5 | 0 | 67 | 0 | 0 | 0 | 0 | 0 | 0 | 933 | 870 |
| V3 | W-drift | 66 | 722 | 0 | 91 | 0 | 2 | 0 | 2 | 0 | 0 | 909 | 844 |
| V4 | W-real | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1000 | 1000 |
| V4 | W-rewind | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1000 | 1000 |
| V4 | W-drift | 0 | 755 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1000 | 1000 |
| V4-Ra | W-real | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1000 | 1000 |
| V4-Rb | W-real | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1000 | 994 |
| N-fence | W-real | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1000 | 1000 |
| N-fence | W-rewind | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1000 | 1000 |
| N-fence | W-drift | 0 | 781 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1000 | 1000 |
| N2 | W-real | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1000 | 1000 |
| N12 | W-real | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1000 | 999 |
| N-viewexp | W-real | 0 | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1000 | 950 |

## W-drift exposure and repair latency

Latency is measured from the silent rewind to a completed repair for the affected Build whose included-fact map equals its store (the exact L2 predicate for that Build). Unrelated Builds or later events can still fail invariants; latency is not a PASS verdict. An already-running repair may qualify. Completion at the same tick has zero latency. A stream report can restore equality without any repair completing: that seed has an explicit null repair latency and is listed separately, not counted as unrepaired or assigned a fabricated completion. Statistics include only measured repair completions. Every seed has its observation/status in raw JSONL. Unrepaired/bound-hit observations are censored.

| Variant | Exposed seeds | Fact flips | Repair samples | Latency mean / p95 / max | Stream-only recovery | Already equal | Unrepaired/censored |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V1 | 749 | 767 | 754 | 42.194 / 59 / 127 | 1 | 0 | 245 |
| V2 | 724 | 738 | 795 | 43.396 / 63 / 161 | 0 | 0 | 205 |
| V3 | 722 | 743 | 973 | 43.041 / 61 / 98 | 0 | 0 | 27 |
| V4 | 755 | 775 | 999 | 44.956 / 129 / 297 | 1 | 0 | 0 |
| N-fence | 781 | 804 | 1000 | 43.445 / 125 / 245 | 0 | 0 | 0 |

Stream-only recovery seeds (with first L2-equality latency):

| Variant | Seed | First equality latency |
| --- | --- | --- |
| V1 | 328 | 67 |
| V4 | 467 | 32 |

Latency observation replay evidence:

| Case | Variant | Seed | Trace |
| --- | --- | --- | --- |
| latency_max | V4 | 153 | [full trace](phase2/traces/V4-W-drift-seed153.txt) |
| stream_recovery | V1 | 328 | [full trace](phase2/traces/V1-W-drift-seed328.txt) |
| stream_recovery | V4 | 467 | [full trace](phase2/traces/V4-W-drift-seed467.txt) |

## Late landings

Mean / nearest-rank p95 / max per seed. Source-entry counts, with combined late landings counted once per initially valid source and page/document transactions reported separately. Already-invalid landings remain a metric, including the Rb ablation.

| Variant | Workload | late_landings | late_S2 | late_S3 | late_transactions | already_invalid_landings | S2_at_write | S3_at_write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V1 | W-real | 6.864 / 12 / 17 | 2.319 / 5 / 8 | 5.917 / 11 / 16 | 6.340 / 11 / 16 | 0.000 / 0 / 0 | 2.319 / 5 / 8 | 5.917 / 11 / 16 |
| V1 | W-rewind | 6.864 / 12 / 17 | 2.319 / 5 / 8 | 5.917 / 11 / 16 | 6.340 / 11 / 16 | 0.000 / 0 / 0 | 2.319 / 5 / 8 | 5.917 / 11 / 16 |
| V1 | W-drift | 6.864 / 12 / 17 | 2.319 / 5 / 8 | 5.917 / 11 / 16 | 6.340 / 11 / 16 | 0.000 / 0 / 0 | 2.319 / 5 / 8 | 5.917 / 11 / 16 |
| V2 | W-real | 6.876 / 12 / 16 | 2.371 / 5 / 8 | 5.876 / 10 / 15 | 6.361 / 11 / 15 | 0.000 / 0 / 0 | 2.371 / 5 / 8 | 5.876 / 10 / 15 |
| V2 | W-rewind | 6.876 / 12 / 16 | 2.371 / 5 / 8 | 5.876 / 10 / 15 | 6.361 / 11 / 15 | 0.000 / 0 / 0 | 2.371 / 5 / 8 | 5.876 / 10 / 15 |
| V2 | W-drift | 6.876 / 12 / 16 | 2.371 / 5 / 8 | 5.876 / 10 / 15 | 6.361 / 11 / 15 | 0.000 / 0 / 0 | 2.371 / 5 / 8 | 5.876 / 10 / 15 |
| V3 | W-real | 6.891 / 12 / 17 | 2.365 / 5 / 8 | 5.939 / 11 / 16 | 6.354 / 11 / 17 | 0.000 / 0 / 0 | 2.365 / 5 / 8 | 5.939 / 11 / 16 |
| V3 | W-rewind | 6.891 / 12 / 17 | 2.365 / 5 / 8 | 5.939 / 11 / 16 | 6.354 / 11 / 17 | 0.000 / 0 / 0 | 2.365 / 5 / 8 | 5.939 / 11 / 16 |
| V3 | W-drift | 6.891 / 12 / 17 | 2.365 / 5 / 8 | 5.939 / 11 / 16 | 6.354 / 11 / 17 | 0.000 / 0 / 0 | 2.365 / 5 / 8 | 5.939 / 11 / 16 |
| V4 | W-real | 6.804 / 12 / 20 | 2.267 / 5 / 8 | 5.861 / 10 / 18 | 6.293 / 11 / 19 | 0.000 / 0 / 0 | 2.267 / 5 / 8 | 5.861 / 10 / 18 |
| V4 | W-rewind | 6.804 / 12 / 20 | 2.267 / 5 / 8 | 5.861 / 10 / 18 | 6.293 / 11 / 19 | 0.000 / 0 / 0 | 2.267 / 5 / 8 | 5.861 / 10 / 18 |
| V4 | W-drift | 6.804 / 12 / 20 | 2.267 / 5 / 8 | 5.861 / 10 / 18 | 6.293 / 11 / 19 | 0.000 / 0 / 0 | 2.267 / 5 / 8 | 5.861 / 10 / 18 |
| V4-Ra | W-real | 6.869 / 12 / 20 | 2.301 / 5 / 8 | 5.893 / 10 / 18 | 6.352 / 11 / 19 | 0.000 / 0 / 0 | 2.301 / 5 / 8 | 5.893 / 10 / 18 |
| V4-Rb | W-real | 7.105 / 12 / 20 | 2.339 / 5 / 8 | 6.169 / 11 / 20 | 6.625 / 11 / 19 | 3.056 / 6 / 11 | 3.505 / 7 / 9 | 8.869 / 15 / 21 |
| N-fence | W-real | 6.850 / 12 / 18 | 2.272 / 5 / 8 | 5.931 / 10 / 17 | 6.327 / 11 / 16 | 0.000 / 0 / 0 | 2.272 / 5 / 8 | 5.931 / 10 / 17 |
| N-fence | W-rewind | 6.850 / 12 / 18 | 2.272 / 5 / 8 | 5.931 / 10 / 17 | 6.327 / 11 / 16 | 0.000 / 0 / 0 | 2.272 / 5 / 8 | 5.931 / 10 / 17 |
| N-fence | W-drift | 6.850 / 12 / 18 | 2.272 / 5 / 8 | 5.931 / 10 / 17 | 6.327 / 11 / 16 | 0.000 / 0 / 0 | 2.272 / 5 / 8 | 5.931 / 10 / 17 |
| N2 | W-real | 6.804 / 12 / 20 | 2.267 / 5 / 8 | 5.861 / 10 / 18 | 6.293 / 11 / 19 | 0.000 / 0 / 0 | 2.267 / 5 / 8 | 5.861 / 10 / 18 |
| N12 | W-real | 6.805 / 12 / 20 | 2.267 / 5 / 8 | 5.863 / 10 / 18 | 6.294 / 11 / 19 | 0.000 / 0 / 0 | 2.267 / 5 / 8 | 5.863 / 10 / 18 |
| N-viewexp | W-real | 6.821 / 12 / 20 | 2.285 / 5 / 8 | 5.882 / 10 / 18 | 6.303 / 11 / 19 | 0.000 / 0 / 0 | 2.285 / 5 / 8 | 5.882 / 10 / 18 |

## Repair cost

Snapshot starts summed over Builds per seed. Transient share uses the existing next-heartbeat counterfactual, unchanged from phase 1d: only heartbeat-triggered starts are classified; shares below show both all-start and heartbeat-start denominators. Suppressing new repairs in the fork can change later RNG consumption.

| Variant | Workload | Snapshots mean / p95 / max | Transient / all starts | Transient / heartbeat starts |
| --- | --- | --- | --- | --- |
| V1 | W-real | 16.360 / 21 / 27 | 6264/16360 (38.289%) | 6264/14819 (42.270%) |
| V1 | W-rewind | 17.354 / 22 / 28 | 6266/17354 (36.107%) | 6266/14821 (42.278%) |
| V1 | W-drift | 17.107 / 22 / 27 | 6268/17107 (36.640%) | 6268/15571 (40.254%) |
| V2 | W-real | 332.954 / 2467 / 4025 | 5543/332954 (1.665%) | 5543/331460 (1.672%) |
| V2 | W-rewind | 115.032 / 29 / 4008 | 5566/115032 (4.839%) | 5566/112560 (4.945%) |
| V2 | W-drift | 143.390 / 1791 / 4008 | 5565/143390 (3.881%) | 5565/141918 (3.921%) |
| V3 | W-real | 389.808 / 2464 / 3440 | 5385/389808 (1.381%) | 5385/388528 (1.386%) |
| V3 | W-rewind | 170.445 / 1806 / 3070 | 5384/170445 (3.159%) | 5384/168182 (3.201%) |
| V3 | W-drift | 222.746 / 2079 / 3070 | 5383/222746 (2.417%) | 5383/221477 (2.431%) |
| V4 | W-real | 19.657 / 25 / 32 | 4992/19657 (25.396%) | 4992/16714 (29.867%) |
| V4 | W-rewind | 20.745 / 26 / 33 | 4991/20745 (24.059%) | 4991/16713 (29.863%) |
| V4 | W-drift | 20.724 / 26 / 33 | 4991/20724 (24.083%) | 4991/17679 (28.231%) |
| V4-Ra | W-real | 19.526 / 25 / 32 | 4922/19526 (25.207%) | 4922/16596 (29.658%) |
| V4-Rb | W-real | 19.775 / 25 / 31 | 4966/19775 (25.113%) | 4966/16737 (29.671%) |
| N-fence | W-real | 19.696 / 25 / 32 | 4853/19696 (24.640%) | 4853/16548 (29.327%) |
| N-fence | W-rewind | 20.757 / 26 / 33 | 4853/20757 (23.380%) | 4853/16547 (29.329%) |
| N-fence | W-drift | 20.737 / 26 / 33 | 4853/20737 (23.403%) | 4853/17507 (27.720%) |
| N2 | W-real | 19.657 / 25 / 32 | 4995/19657 (25.411%) | 4995/16717 (29.880%) |
| N12 | W-real | 19.635 / 25 / 32 | 4990/19635 (25.414%) | 4990/16717 (29.850%) |
| N-viewexp | W-real | 18.012 / 24 / 29 | 4887/18012 (27.132%) | 4887/16711 (29.244%) |

## Fence redundancy

Each row compares paired workload seeds. S1_flipback under W-drift remains exposure, not a failure. A paired difference alone is not causal proof: protocol branches consume scheduler RNG differently. Any N-fence-only failure is a candidate requiring the trace below to establish that the omitted fence enabled it.

| Workload | Invariant | V4 | N-fence | N-fence only | V4 only | Both |
| --- | --- | --- | --- | --- | --- | --- |
| W-real | S1 | 0 | 0 | 0 | 0 | 0 |
| W-real | S1_flipback | 0 | 0 | 0 | 0 | 0 |
| W-real | S7 | 0 | 0 | 0 | 0 | 0 |
| W-real | L0 | 0 | 0 | 0 | 0 | 0 |
| W-real | L1 | 0 | 0 | 0 | 0 | 0 |
| W-real | L2 | 0 | 0 | 0 | 0 | 0 |
| W-real | L3 | 0 | 0 | 0 | 0 | 0 |
| W-real | L4 | 0 | 0 | 0 | 0 | 0 |
| W-real | L5 | 0 | 0 | 0 | 0 | 0 |
| W-real | UNKNOWN | 0 | 0 | 0 | 0 | 0 |
| W-rewind | S1 | 0 | 0 | 0 | 0 | 0 |
| W-rewind | S1_flipback | 0 | 0 | 0 | 0 | 0 |
| W-rewind | S7 | 0 | 0 | 0 | 0 | 0 |
| W-rewind | L0 | 0 | 0 | 0 | 0 | 0 |
| W-rewind | L1 | 0 | 0 | 0 | 0 | 0 |
| W-rewind | L2 | 0 | 0 | 0 | 0 | 0 |
| W-rewind | L3 | 0 | 0 | 0 | 0 | 0 |
| W-rewind | L4 | 0 | 0 | 0 | 0 | 0 |
| W-rewind | L5 | 0 | 0 | 0 | 0 | 0 |
| W-rewind | UNKNOWN | 0 | 0 | 0 | 0 | 0 |
| W-drift | S1 | 0 | 0 | 0 | 0 | 0 |
| W-drift | S1_flipback | 755 | 781 | 91 | 65 | 690 |
| W-drift | S7 | 0 | 0 | 0 | 0 | 0 |
| W-drift | L0 | 0 | 0 | 0 | 0 | 0 |
| W-drift | L1 | 0 | 0 | 0 | 0 | 0 |
| W-drift | L2 | 0 | 0 | 0 | 0 | 0 |
| W-drift | L3 | 0 | 0 | 0 | 0 | 0 |
| W-drift | L4 | 0 | 0 | 0 | 0 | 0 |
| W-drift | L5 | 0 | 0 | 0 | 0 | 0 |
| W-drift | UNKNOWN | 0 | 0 | 0 | 0 | 0 |

No sampled seed demonstrates that the replacement fence is necessary.


## Ablations and negative controls

Detection is per seed under W-real. Shared seeds satisfying the same target in V4 are subtracted from unique detection and explicitly listed. Rb targets already-invalid landings because S2/S3 are measurements; a failure is not expected from that metric. N2 can be masked by the retained fence. Random non-detection is distinct from the targeted deterministic control results. Ra and N2 have no unique random witness to excerpt. Ra is detected by SC16; N2 remains masked on NC2. The absence of a random Ra failure does not establish that the rule is optional.

| Variant | Expected target | Detected | Shared V4 seeds | Unique after subtraction | First unique seed | Subtracted seed list |
| --- | --- | --- | --- | --- | --- | --- |
| V4-Ra | L1 or L5 | 0 | 0 | 0 | — | — |
| V4-Rb | already_invalid_landings | 958 | 0 | 958 | 0 | — |
| N2 | S1_flipback or L2 | 0 | 0 | 0 | — | — |
| N12 | S1_flipback or L2 | 1 | 0 | 1 | 581 | — |
| N-viewexp | S1_flipback or L2 | 50 | 0 | 50 | 95 | — |

### N-viewexp first unique witness — seed 95

[Full replay trace](phase2/traces/N-viewexp-W-real-seed95.txt). Target: `S1_flipback`.

```text
0214 feed 47 current_revision_changed d1
0214 replacement page 1 index=3 arrived records=2
0214 fact ('retrieval-0', 'd0', 'r0') included rev=1 v=14
0214 replacement KEEP >W retrieval-0 ('d1', 'r0') v=38 W=14
0214 replacement KEEP >W retrieval-0 ('d2', 'r0') v=25 W=14
0214 replacement KEEP >W retrieval-0 ('d2', 'r1') v=42 W=14
0214 replacement KEEP >W retrieval-0 ('d3', 'r0') v=17 W=14
0214 replacement KEEP >W retrieval-0 ('d3', 'r1') v=18 W=14
0214 replacement KEEP >W retrieval-0 ('d4', 'r0') v=41 W=14
0214 replacement KEEP >W retrieval-0 ('d5', 'r0') v=40 W=14
0214 replacement KEEP >W retrieval-0 ('d6', 'r0') v=43 W=14
0214 replacement KEEP >W retrieval-0 ('d7', 'r0') v=44 W=14
0214 replacement KEEP >W retrieval-0 ('d7', 'r1') v=45 W=14
0214 replacement 1 atomic END retrieval-0 fence=14
0214 FLIP-BACK d0 enforcement true->false
0214 VIOLATION S1_flipback {"reason": "fact-based enforcement reversal", "uid": "d0"}
0214 fact ('retrieval-1', 'd7', 'r1') removed rev=None v=19
0214 store remove retrieval-0 ('d3', 'r1') v=48
0214 outbox retrieval-0 ('d3', 'r1') included=False v=48
0214 read wiki-0 trigger=d6 source=d4 desired=('r0', 14)
```

### N12 first unique witness — seed 581

[Full replay trace](phase2/traces/N12-W-real-seed581.txt). Target: `S1_flipback`.

```text
0323 tombstone expired ('wiki-0', 'd3', 'r0') v=38
0323 store write FAILED after register retrieval-0 #128 retry
0325 read retrieval-0 trigger=d6 source=d6 desired=('r0', 15)
0326 FENCE ignore retrieval-0 ('d4', 'r0') v=45 <= 46
0327 fact ('wiki-1', 'd1', 'r0') pending rev=23 v=20
0327 register wiki-1 ('d1', 'r0') rev=23 v=20 pending
0327 register accepted wiki-1 #135 write_delay=6
0328 fact ('wiki-0', 'd7', 'r0') removed rev=None v=67
0330 fact ('retrieval-1', 'd3', 'r0') removed rev=None v=15
0330 fact ('retrieval-1', 'd4', 'r0') removed rev=None v=24
0331 fact ('retrieval-0', 'd6', 'r0') pending rev=15 v=48
0331 register retrieval-0 ('d6', 'r0') rev=15 v=48 pending
0331 register accepted retrieval-0 #136 write_delay=2
0333 fact ('wiki-0', 'd3', 'r0') included rev=4 v=30
0333 FLIP-BACK d3 enforcement true->false
0333 VIOLATION S1_flipback {"reason": "fact-based enforcement reversal", "uid": "d3"}
0333 store write FAILED after register wiki-1 #135 retry
0333 store write FAILED after register retrieval-0 #136 retry
0334 replacement page 17 index=0 arrived records=2
0334 fact ('retrieval-0', 'd1', 'r0') included rev=23 v=47
```

### V4-Rb first unique witness — seed 0

[Full replay trace](phase2/traces/V4-Rb-W-real-seed0.txt). Target: `already_invalid_landings`.

```text
0087 register wiki-0 ('d5', 'r0') rev=18 v=42 pending
0087 fact ('wiki-0', 'd7', 'r0') pending rev=9 v=43
0087 register wiki-0 ('d7', 'r0') rev=9 v=43 pending
0087 register accepted wiki-0 #26 write_delay=2
0089 action rollback ['d4']
0089 feed 23 current_revision_changed d4
0089 fresh confirmation wiki-0 ('d5', 'r0') register_v=42 confirm_v=44 fence=9
0089 store write wiki-0 page=d5+d7 ('d5', 'r0') rev=18 v=44
0089 fresh confirmation wiki-0 ('d7', 'r0') register_v=43 confirm_v=45 fence=9
0089 store write wiki-0 page=d5+d7 ('d7', 'r0') rev=9 v=45
0089 outbox wiki-0 ('d5', 'r0') included=True v=44
0089 outbox wiki-0 ('d7', 'r0') included=True v=45
0090 LANDING wiki-0 ('d4', 'r1') S2=False S3=True valid_at_check=True
0090 fresh confirmation wiki-0 ('d4', 'r1') register_v=40 confirm_v=46 fence=9
0090 store write wiki-0 page=d4+d6 ('d4', 'r1') rev=16 v=46
0090 LANDING wiki-0 ('d6', 'r0') S2=False S3=True valid_at_check=False
0090 fresh confirmation wiki-0 ('d6', 'r0') register_v=41 confirm_v=47 fence=9
0090 store write wiki-0 page=d4+d6 ('d6', 'r0') rev=17 v=47
0090 outbox wiki-0 ('d4', 'r1') included=True v=46
0090 outbox wiki-0 ('d6', 'r0') included=True v=47
```

## Deterministic matrix

| Scenario | Variant | Expected | Observed | Already invalid | Late landings | Match |
| --- | --- | --- | --- | --- | --- | --- |
| SC15 | V1 | FAIL S1 | FAIL S1,S1_flipback | 0 | 0 | yes |
| SC15 | V2 | PASS | PASS | 0 | 0 | yes |
| SC15 | V3 | PASS | PASS | 0 | 0 | yes |
| SC15 | V4 | PASS | PASS | 0 | 0 | yes |
| SC16 | V3 | PASS | PASS | 0 | 0 | yes |
| SC16 | V4 | PASS | PASS | 0 | 0 | yes |
| SC16 | V4-Ra | FAIL L5 | FAIL L1,L5 | 0 | 0 | yes |
| SC18 | V3 | PASS; already-invalid =0 | PASS | 0 | 0 | yes |
| SC18 | V4 | PASS; already-invalid =0 | PASS | 0 | 0 | yes |
| SC18 | V4-Rb | PASS; already-invalid ≥1 | PASS | 1 | 0 | yes |
| SC19 | V3 | PASS | PASS | 0 | 0 | yes |
| SC19 | V4 | PASS | PASS | 0 | 0 | yes |
| SC19 | N12 | FAIL S1_flipback | FAIL S1_flipback | 0 | 0 | yes |
| SC20r | V1 | PASS | PASS | 0 | 0 | yes |
| SC20r | V2 | PASS | PASS | 0 | 0 | yes |
| SC20r | V3 | PASS | PASS | 0 | 0 | yes |
| SC20r | V4 | PASS | PASS | 0 | 0 | yes |
| SC20u | V1 | FAIL L2 | FAIL L2 | 0 | 0 | yes |
| SC20u | V2 | FAIL L2 | FAIL L2 | 0 | 0 | yes |
| SC20u | V3 | PASS | PASS | 0 | 0 | yes |
| SC20u | V4 | PASS | PASS | 0 | 0 | yes |
| NC2 | V3 | PASS | PASS | 0 | 0 | yes |
| NC2 | V4 | PASS | PASS | 0 | 0 | yes |
| NC2 | N2 | PASS; masked by V4 fence | PASS | 0 | 0 | yes |
| NC2 | N-fence | PASS; masked by tombstone | PASS | 0 | 0 | yes |
| SC21 | V2 | FAIL L0 | FAIL L0 | 0 | 0 | yes |
| SC21 | V3 | FAIL L0 | FAIL L0 | 0 | 0 | yes |
| SC21 | V4 | PASS | PASS | 0 | 0 | yes |
| SC22 | V3 | FAIL L4 | FAIL L2,L4 | 0 | 0 | yes |
| SC22 | V4 | PASS | PASS | 0 | 0 | yes |
| SC23 | V4 | PASS | PASS | 0 | 1 | yes |
| SC24 | V4 | PASS | PASS | 0 | 0 | yes |
| SC24 | N-viewexp | FAIL S1_flipback or L2 | FAIL S1_flipback | 0 | 0 | yes |

## Every V4 failure

Failure classes are workload × accepted invariant (and UNKNOWN separately). All failing seed IDs remain in raw JSONL; the smallest seed of every class is replayed and compared identically, including metrics and latency observations. W-drift fact-based flip exposure is excluded only by the approved acceptance rule.

**No V4 failures and no V4 UNKNOWNs.** No failure-class replay is required. This does not count W-drift exposure as prevented; its measured exposure is above.

## Every S1 under W-drift

S1 remains a failure even under silent drift. Each case below has an identical full replay, a captured atomic-state context in `phase2/evidence.json`, and a trace. Pre-drift S1 cases cannot be attributed to the later corruption.

| Variant | Seed | Causal explanation | Trace |
| --- | --- | --- | --- |
| V1 | 5 | V1 has no pending reservation covering its check/write/report interval. At tick 215, d3 is judged enforced while present in retrieval-0, before the silent rewind. Atomic event: ["action", ["delete", ["d3"]]]. Stored versions: retrieval-0:r0@v25. Live mirror: retrieval-0/r0:removed@v16, wiki-0/r0:removed@v22, retrieval-1/r0:removed@v5. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V1-W-drift-seed5.txt) |
| V1 | 100 | V1 has no pending reservation covering its check/write/report interval. At tick 175, d3 is judged enforced while present in retrieval-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-0:r1@v16. Live mirror: retrieval-0/r0:removed@v15, wiki-0/r0:removed@v26, retrieval-1/r0:removed@v7. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V1-W-drift-seed100.txt) |
| V1 | 477 | V1 has no pending reservation covering its check/write/report interval. At tick 178, d3 is judged enforced while present in retrieval-0, wiki-0, retrieval-1, before the silent rewind. Atomic event: ["action", ["delete", ["d3"]]]. Stored versions: retrieval-0:r1@v19, wiki-0:r1@v16, retrieval-1:r1@v9. Live mirror: retrieval-0/r0:removed@v18. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V1-W-drift-seed477.txt) |
| V1 | 794 | V1 has no pending reservation covering its check/write/report interval. At tick 205, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v19. Live mirror: retrieval-0/r0:removed@v16, wiki-0/r0:removed@v17, retrieval-1/r0:removed@v8, retrieval-0/r1:removed@v19. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V1-W-drift-seed794.txt) |
| V1 | 797 | V1 has no pending reservation covering its check/write/report interval. At tick 207, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v26. Live mirror: retrieval-0/r0:removed@v26, wiki-0/r0:removed@v24. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V1-W-drift-seed797.txt) |
| V1 | 816 | V1 has no pending reservation covering its check/write/report interval. At tick 207, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["write_attempt", null]. Stored versions: retrieval-1:r0@v10. Live mirror: retrieval-0/r0:removed@v12. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V1-W-drift-seed816.txt) |
| V1 | 853 | V1 has no pending reservation covering its check/write/report interval. At tick 240, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v24. Live mirror: retrieval-0/r0:removed@v26, retrieval-1/r0:removed@v10. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V1-W-drift-seed853.txt) |
| V2 | 10 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 169, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v11. Live mirror: retrieval-0/r0:removed@v15, wiki-0/r0:removed@v18. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed10.txt) |
| V2 | 95 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 244, d3 is judged enforced while present in retrieval-1, wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r1@v6, wiki-1:r0@v2. Live mirror: retrieval-0/r0:removed@v31, retrieval-0/r1:removed@v28, wiki-0/r1:removed@v43, retrieval-1/r1:removed@v9, wiki-0/r0:removed@v59, wiki-1/r0:removed@v3. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed95.txt) |
| V2 | 130 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 205, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r1@v2. Live mirror: retrieval-0/r0:removed@v11, wiki-0/r0:removed@v27, wiki-1/r1:removed@v6, wiki-0/r1:removed@v30, retrieval-1/r1:removed@v8. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed130.txt) |
| V2 | 145 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 207, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v19. Live mirror: retrieval-0/r0:removed@v28, wiki-0/r0:removed@v34, retrieval-1/r0:removed@v8. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed145.txt) |
| V2 | 152 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 201, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v27. Live mirror: retrieval-0/r0:removed@v15, wiki-0/r0:removed@v28, retrieval-1/r0:removed@v6. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed152.txt) |
| V2 | 168 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 246, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v1. Live mirror: retrieval-0/r0:removed@v23, retrieval-1/r0:removed@v13, wiki-0/r0:removed@v46. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed168.txt) |
| V2 | 206 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 244, d3 is judged enforced while present in retrieval-0, retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-0:r0@v4, retrieval-1:r0@v2. Live mirror: retrieval-0/r0:removed@v17, wiki-0/r0:removed@v29, retrieval-1/r0:removed@v8. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed206.txt) |
| V2 | 227 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 274, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v4. Live mirror: retrieval-0/r0:removed@v32, wiki-0/r0:removed@v48, retrieval-1/r0:removed@v11, wiki-1/r0:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed227.txt) |
| V2 | 251 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 253, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v2. Live mirror: retrieval-0/r0:removed@v31, wiki-0/r0:removed@v44, retrieval-1/r0:removed@v10. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed251.txt) |
| V2 | 292 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 222, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v15. Live mirror: retrieval-0/r0:removed@v20, wiki-0/r0:removed@v34, retrieval-1/r0:removed@v17. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed292.txt) |
| V2 | 334 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 307, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v2. Live mirror: retrieval-0/r0:removed@v26, wiki-0/r0:removed@v50, retrieval-1/r0:removed@v18, wiki-1/r0:removed@v4. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed334.txt) |
| V2 | 384 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 226, d3 is judged enforced while present in retrieval-0, retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-0:r0@v4, retrieval-1:r0@v5. Live mirror: retrieval-0/r0:removed@v14, wiki-0/r0:removed@v36, retrieval-1/r0:removed@v8. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed384.txt) |
| V2 | 390 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 249, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v5. Live mirror: retrieval-0/r0:removed@v13, wiki-0/r0:removed@v45, wiki-1/r0:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed390.txt) |
| V2 | 391 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 227, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v25. Live mirror: retrieval-0/r0:removed@v33, wiki-0/r0:removed@v25, retrieval-1/r0:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed391.txt) |
| V2 | 399 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 236, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v2. Live mirror: retrieval-0/r0:removed@v31, wiki-0/r0:removed@v36, wiki-1/r0:removed@v5, retrieval-1/r0:removed@v7. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed399.txt) |
| V2 | 400 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 234, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v11. Live mirror: retrieval-0/r0:removed@v19, retrieval-1/r0:removed@v11, wiki-0/r0:removed@v29. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed400.txt) |
| V2 | 412 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 359, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["action", ["retire", ["retrieval"]]]. Stored versions: wiki-1:r0@v2. Live mirror: retrieval-0/r0:removed@v18, wiki-1/r0:removed@v15. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed412.txt) |
| V2 | 430 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 155, d0 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["recover", null]. Stored versions: wiki-0:r0@v5. Live mirror: retrieval-0/r0:removed@v9, wiki-0/r0:removed@v29. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed430.txt) |
| V2 | 445 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 237, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v3. Live mirror: retrieval-0/r0:removed@v26, wiki-0/r0:removed@v38, wiki-1/r0:removed@v6, retrieval-1/r0:removed@v7. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed445.txt) |
| V2 | 490 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 279, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v31. Live mirror: retrieval-0/r0:removed@v22, wiki-0/r0:removed@v40, retrieval-1/r0:removed@v18. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed490.txt) |
| V2 | 491 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 255, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v32. Live mirror: retrieval-0/r0:removed@v34, wiki-0/r0:removed@v43, wiki-0/r1:removed@v43, retrieval-0/r1:removed@v35, retrieval-1/r1:removed@v17. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed491.txt) |
| V2 | 515 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 230, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v38. Live mirror: retrieval-0/r0:removed@v38, wiki-0/r0:removed@v41, retrieval-1/r0:removed@v19. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed515.txt) |
| V2 | 524 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 256, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v31. Live mirror: retrieval-0/r0:removed@v22, retrieval-1/r0:removed@v16, wiki-0/r0:removed@v35. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed524.txt) |
| V2 | 611 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 222, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v14. Live mirror: retrieval-0/r0:removed@v35, wiki-0/r0:removed@v41. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed611.txt) |
| V2 | 629 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 221, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v33. Live mirror: retrieval-0/r0:removed@v30, wiki-0/r0:removed@v41, retrieval-1/r0:removed@v7, retrieval-0/r1:removed@v30, wiki-0/r1:removed@v41. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed629.txt) |
| V2 | 638 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 269, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v1. Live mirror: retrieval-0/r0:removed@v26, wiki-0/r0:removed@v42, retrieval-1/r0:removed@v13, wiki-1/r0:removed@v7. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed638.txt) |
| V2 | 645 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 332, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v4. Live mirror: retrieval-0/r0:removed@v35, wiki-0/r0:removed@v60, retrieval-1/r0:removed@v16, wiki-1/r0:removed@v13, wiki-0/r1:removed@v60. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed645.txt) |
| V2 | 678 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 278, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v33. Live mirror: retrieval-0/r0:removed@v22, wiki-0/r0:removed@v42, retrieval-1/r0:removed@v13. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed678.txt) |
| V2 | 682 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 250, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v5. Live mirror: retrieval-0/r0:removed@v23, wiki-0/r0:removed@v46, retrieval-1/r0:removed@v16, wiki-1/r0:removed@v7. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed682.txt) |
| V2 | 685 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 331, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v4. Live mirror: retrieval-0/r0:removed@v35, wiki-0/r0:removed@v47, retrieval-1/r0:removed@v11, wiki-1/r0:removed@v7. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed685.txt) |
| V2 | 688 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 218, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v26. Live mirror: retrieval-0/r0:removed@v20, wiki-0/r0:removed@v28, retrieval-1/r0:removed@v5. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed688.txt) |
| V2 | 716 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 243, d3 is judged enforced while present in wiki-0, wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v46, wiki-1:r1@v4. Live mirror: retrieval-0/r0:removed@v16, wiki-0/r0:removed@v47, wiki-1/r0:removed@v9, wiki-0/r1:removed@v47, retrieval-1/r1:removed@v13, retrieval-0/r1:removed@v23, wiki-1/r1:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed716.txt) |
| V2 | 743 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 235, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v3. Live mirror: retrieval-0/r0:removed@v26, wiki-0/r0:removed@v42, retrieval-1/r0:removed@v4. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed743.txt) |
| V2 | 747 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 221, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v18. Live mirror: retrieval-0/r0:removed@v32, wiki-0/r0:removed@v32, retrieval-1/r0:removed@v7. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed747.txt) |
| V2 | 754 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 290, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r1@v2. Live mirror: retrieval-0/r0:removed@v24, wiki-0/r0:removed@v59, wiki-0/r1:removed@v59, retrieval-1/r1:removed@v16, wiki-1/r1:removed@v9, retrieval-0/r1:removed@v24. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed754.txt) |
| V2 | 761 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 219, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v12. Live mirror: retrieval-0/r0:removed@v30, wiki-0/r0:removed@v36, retrieval-1/r0:removed@v10. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed761.txt) |
| V2 | 780 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 304, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v4. Live mirror: retrieval-0/r0:removed@v18, wiki-0/r0:removed@v51, retrieval-1/r0:removed@v12, wiki-1/r0:removed@v11. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed780.txt) |
| V2 | 796 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 265, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v17. Live mirror: retrieval-0/r0:removed@v17, retrieval-1/r0:removed@v10, wiki-0/r0:removed@v47. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed796.txt) |
| V2 | 812 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 192, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["action", ["delete", ["d3"]]]. Stored versions: wiki-0:r0@v27. Live mirror: retrieval-0/r0:removed@v10, wiki-0/r0:removed@v30, retrieval-1/r0:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed812.txt) |
| V2 | 817 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 220, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v2. Live mirror: retrieval-0/r0:removed@v28, wiki-0/r0:removed@v39, wiki-1/r0:removed@v4, retrieval-1/r0:removed@v10. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed817.txt) |
| V2 | 821 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 282, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v4. Live mirror: retrieval-0/r0:removed@v21, wiki-0/r0:removed@v52, retrieval-1/r0:removed@v12, wiki-1/r0:removed@v18. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed821.txt) |
| V2 | 825 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 219, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v5. Live mirror: retrieval-0/r0:removed@v28, wiki-0/r0:removed@v59, retrieval-1/r0:removed@v11. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed825.txt) |
| V2 | 862 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 272, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v16. Live mirror: retrieval-0/r0:removed@v24, wiki-0/r1:removed@v56, retrieval-1/r1:removed@v13, retrieval-0/r1:removed@v25. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed862.txt) |
| V2 | 890 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 267, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v3. Live mirror: retrieval-0/r0:removed@v18, wiki-0/r0:removed@v60, wiki-1/r0:removed@v16, retrieval-1/r0:removed@v13. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed890.txt) |
| V2 | 897 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 187, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v14. Live mirror: retrieval-0/r0:removed@v15, wiki-0/r0:removed@v18, retrieval-1/r0:removed@v10. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed897.txt) |
| V2 | 981 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 292, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v1. Live mirror: retrieval-0/r0:removed@v35, wiki-0/r0:removed@v50, wiki-1/r0:removed@v18, retrieval-1/r0:removed@v14. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V2-W-drift-seed981.txt) |
| V3 | 10 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 169, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v11. Live mirror: retrieval-0/r0:removed@v15, wiki-0/r0:removed@v18. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed10.txt) |
| V3 | 48 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 291, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v6. Live mirror: retrieval-0/r0:removed@v31, wiki-0/r0:removed@v45, retrieval-1/r0:removed@v12. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed48.txt) |
| V3 | 135 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 227, d3 is judged enforced while present in retrieval-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-0:r0@v4. Live mirror: retrieval-0/r0:removed@v27, wiki-0/r0:removed@v47. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed135.txt) |
| V3 | 137 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 220, d3 is judged enforced while present in wiki-0, wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v12, wiki-1:r0@v2. Live mirror: retrieval-0/r0:removed@v23, wiki-0/r0:removed@v34, retrieval-1/r0:removed@v9, wiki-1/r0:removed@v3. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed137.txt) |
| V3 | 199 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 208, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v20. Live mirror: retrieval-0/r0:removed@v26, wiki-0/r0:removed@v28, retrieval-1/r0:removed@v7. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed199.txt) |
| V3 | 206 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 243, d3 is judged enforced while present in retrieval-0, retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-0:r0@v4, retrieval-1:r0@v2. Live mirror: retrieval-0/r0:removed@v17, wiki-0/r0:removed@v31, retrieval-1/r0:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed206.txt) |
| V3 | 226 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 188, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v6. Live mirror: retrieval-0/r0:removed@v15, wiki-0/r0:removed@v39, retrieval-1/r0:removed@v6. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed226.txt) |
| V3 | 227 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 258, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v4. Live mirror: retrieval-0/r0:removed@v32, wiki-0/r0:removed@v48, retrieval-1/r0:removed@v11, wiki-1/r0:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed227.txt) |
| V3 | 242 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 220, d3 is judged enforced while present in retrieval-0, wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-0:r0@v21, wiki-0:r0@v32. Live mirror: retrieval-0/r0:removed@v21, wiki-0/r0:removed@v34, retrieval-1/r0:removed@v15. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed242.txt) |
| V3 | 245 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 229, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v8. Live mirror: retrieval-0/r0:removed@v27, wiki-0/r0:removed@v41, retrieval-1/r0:removed@v11. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed245.txt) |
| V3 | 246 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 240, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v20. Live mirror: retrieval-0/r0:removed@v15, wiki-0/r0:removed@v41, retrieval-1/r0:removed@v17. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed246.txt) |
| V3 | 251 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 253, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v2. Live mirror: retrieval-0/r0:removed@v31, wiki-0/r0:removed@v44, retrieval-1/r0:removed@v10. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed251.txt) |
| V3 | 263 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 227, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v28. Live mirror: retrieval-0/r0:removed@v40, wiki-0/r0:removed@v36, retrieval-1/r0:removed@v11. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed263.txt) |
| V3 | 266 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 210, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v19. Live mirror: retrieval-0/r0:removed@v15, wiki-0/r0:removed@v37. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed266.txt) |
| V3 | 283 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 244, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v21. Live mirror: retrieval-0/r0:removed@v33, wiki-0/r0:removed@v39, retrieval-1/r0:removed@v11. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed283.txt) |
| V3 | 284 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 254, d3 is judged enforced while present in wiki-0, retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v47, retrieval-1:r0@v2. Live mirror: retrieval-0/r0:removed@v30, wiki-0/r0:removed@v55, wiki-1/r0:removed@v6, retrieval-1/r0:removed@v17, wiki-0/r1:removed@v55. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed284.txt) |
| V3 | 301 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 251, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v23. Live mirror: retrieval-0/r0:removed@v35, retrieval-1/r0:removed@v11, wiki-0/r0:removed@v30. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed301.txt) |
| V3 | 309 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 248, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v16. Live mirror: retrieval-0/r0:removed@v36, wiki-0/r0:removed@v40, retrieval-1/r0:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed309.txt) |
| V3 | 314 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 188, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v6. Live mirror: retrieval-0/r0:removed@v15, wiki-0/r0:removed@v20. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed314.txt) |
| V3 | 357 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 268, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v2. Live mirror: retrieval-0/r0:removed@v27, wiki-0/r0:removed@v44, wiki-1/r0:removed@v5, retrieval-1/r0:removed@v15. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed357.txt) |
| V3 | 358 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 247, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v39. Live mirror: retrieval-0/r0:removed@v24, wiki-0/r0:removed@v51, retrieval-1/r0:removed@v20. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed358.txt) |
| V3 | 369 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 304, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v3. Live mirror: retrieval-0/r0:removed@v35, retrieval-1/r0:removed@v16, wiki-0/r0:removed@v49, wiki-1/r0:removed@v8. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed369.txt) |
| V3 | 377 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 206, d3 is judged enforced while present in retrieval-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-0:r0@v24. Live mirror: retrieval-0/r0:removed@v24, wiki-0/r0:removed@v17. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed377.txt) |
| V3 | 391 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 227, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v25. Live mirror: retrieval-0/r0:removed@v33, wiki-0/r0:removed@v25, retrieval-1/r0:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed391.txt) |
| V3 | 397 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 232, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v36. Live mirror: retrieval-0/r0:removed@v34, wiki-0/r0:removed@v37, retrieval-0/r1:removed@v37, wiki-0/r1:removed@v37, retrieval-1/r1:removed@v14. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed397.txt) |
| V3 | 400 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 202, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v11. Live mirror: retrieval-0/r0:removed@v18, retrieval-1/r0:removed@v9, wiki-0/r0:removed@v24. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed400.txt) |
| V3 | 431 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 275, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v3. Live mirror: retrieval-0/r0:removed@v32, wiki-0/r0:removed@v45, wiki-1/r0:removed@v9, retrieval-1/r0:removed@v15. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed431.txt) |
| V3 | 434 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 208, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v8. Live mirror: retrieval-0/r0:removed@v19, wiki-0/r0:removed@v31, retrieval-1/r0:removed@v13. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed434.txt) |
| V3 | 435 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 221, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v2. Live mirror: retrieval-0/r0:removed@v28, wiki-0/r0:removed@v37, retrieval-1/r0:removed@v6, wiki-1/r0:removed@v2. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed435.txt) |
| V3 | 446 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 242, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v3. Live mirror: retrieval-0/r0:removed@v17, wiki-1/r0:removed@v10, wiki-0/r0:removed@v38, retrieval-1/r0:removed@v22. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed446.txt) |
| V3 | 460 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 237, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v36. Live mirror: retrieval-0/r0:removed@v18, wiki-0/r0:removed@v49, retrieval-1/r0:removed@v11. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed460.txt) |
| V3 | 475 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 226, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v17. Live mirror: retrieval-0/r0:removed@v26, wiki-0/r0:removed@v28, wiki-1/r0:removed@v8, retrieval-1/r0:removed@v5. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed475.txt) |
| V3 | 478 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 295, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v3. Live mirror: retrieval-0/r0:removed@v21, wiki-0/r0:removed@v62, retrieval-1/r0:removed@v19, wiki-1/r0:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed478.txt) |
| V3 | 491 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 255, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v32. Live mirror: retrieval-0/r0:removed@v34, wiki-0/r0:removed@v43, wiki-0/r1:removed@v43, retrieval-0/r1:removed@v35, retrieval-1/r1:removed@v17. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed491.txt) |
| V3 | 493 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 196, d3 is judged enforced while present in wiki-0, wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v31, wiki-1:r0@v2. Live mirror: retrieval-0/r0:removed@v33, wiki-0/r0:removed@v33, wiki-1/r0:removed@v9, retrieval-1/r0:removed@v11. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed493.txt) |
| V3 | 500 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 253, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v33. Live mirror: retrieval-0/r0:removed@v22, retrieval-1/r0:removed@v15, wiki-0/r0:removed@v35. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed500.txt) |
| V3 | 501 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 220, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v28. Live mirror: retrieval-0/r0:removed@v23, wiki-0/r0:removed@v35, retrieval-1/r0:removed@v8. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed501.txt) |
| V3 | 510 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 273, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v39. Live mirror: retrieval-0/r0:removed@v21, wiki-0/r0:removed@v45, retrieval-1/r0:removed@v18. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed510.txt) |
| V3 | 514 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 254, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v35. Live mirror: retrieval-0/r0:removed@v24, wiki-0/r0:removed@v54, wiki-0/r1:removed@v54, retrieval-0/r1:removed@v26, retrieval-1/r1:removed@v14. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed514.txt) |
| V3 | 523 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 242, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v11. Live mirror: retrieval-0/r0:removed@v32, wiki-0/r0:removed@v38, retrieval-1/r0:removed@v13. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed523.txt) |
| V3 | 548 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 342, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v6. Live mirror: retrieval-0/r0:removed@v25, retrieval-1/r0:removed@v10, wiki-0/r0:removed@v62, wiki-1/r0:removed@v13. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed548.txt) |
| V3 | 564 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 226, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v20. Live mirror: retrieval-0/r0:removed@v22, wiki-0/r0:removed@v31, retrieval-1/r0:removed@v17. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed564.txt) |
| V3 | 598 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 227, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v34. Live mirror: retrieval-0/r0:removed@v23, wiki-0/r1:removed@v49, retrieval-1/r1:removed@v11, wiki-1/r1:removed@v6, retrieval-0/r1:removed@v24. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed598.txt) |
| V3 | 626 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 279, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v16. Live mirror: retrieval-0/r0:removed@v18, wiki-0/r0:removed@v47, retrieval-1/r0:removed@v15. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed626.txt) |
| V3 | 640 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 301, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v1. Live mirror: retrieval-0/r0:removed@v23, wiki-0/r0:removed@v39, retrieval-1/r0:removed@v12, wiki-1/r0:removed@v5. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed640.txt) |
| V3 | 645 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 286, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v4. Live mirror: retrieval-0/r0:removed@v38, wiki-0/r0:removed@v53, retrieval-1/r0:removed@v17, wiki-1/r0:removed@v7. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed645.txt) |
| V3 | 646 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 237, d3 is judged enforced while present in retrieval-0, retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-0:r0@v13, retrieval-1:r0@v10. Live mirror: retrieval-0/r0:removed@v14, wiki-0/r0:removed@v32, retrieval-1/r0:removed@v10. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed646.txt) |
| V3 | 647 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 242, d3 is judged enforced while present in wiki-0, wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v36, wiki-1:r0@v6. Live mirror: retrieval-0/r0:removed@v35, wiki-0/r0:removed@v46, wiki-1/r0:removed@v8, retrieval-1/r0:removed@v14. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed647.txt) |
| V3 | 652 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 233, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v33. Live mirror: retrieval-0/r0:removed@v17, wiki-0/r0:removed@v40, retrieval-1/r0:removed@v14. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed652.txt) |
| V3 | 682 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 247, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v15. Live mirror: retrieval-0/r0:removed@v25, wiki-0/r0:removed@v52, retrieval-1/r0:removed@v17, wiki-1/r0:removed@v14. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed682.txt) |
| V3 | 688 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 229, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v1. Live mirror: retrieval-0/r0:removed@v19, wiki-0/r0:removed@v37, retrieval-1/r0:removed@v8. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed688.txt) |
| V3 | 727 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 191, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v9. Live mirror: retrieval-0/r0:removed@v31, retrieval-1/r0:removed@v10. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed727.txt) |
| V3 | 745 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 261, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r1@v6. Live mirror: retrieval-0/r0:removed@v34, wiki-0/r0:removed@v35, retrieval-1/r0:removed@v13, retrieval-0/r1:removed@v33, retrieval-1/r1:removed@v13, wiki-0/r1:removed@v45, wiki-1/r1:removed@v8. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed745.txt) |
| V3 | 747 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 221, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v18. Live mirror: retrieval-0/r0:removed@v32, wiki-0/r0:removed@v32, retrieval-1/r0:removed@v7. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed747.txt) |
| V3 | 761 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 219, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v12. Live mirror: retrieval-0/r0:removed@v30, wiki-0/r0:removed@v36, retrieval-1/r0:removed@v10. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed761.txt) |
| V3 | 785 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 196, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v40. Live mirror: retrieval-0/r0:removed@v24, wiki-0/r1:removed@v42, retrieval-0/r1:removed@v31, retrieval-1/r1:removed@v7. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed785.txt) |
| V3 | 805 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 285, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v3. Live mirror: retrieval-0/r0:removed@v32, wiki-0/r0:removed@v49, wiki-1/r0:removed@v6, retrieval-1/r0:removed@v10. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed805.txt) |
| V3 | 806 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 191, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v6. Live mirror: retrieval-0/r0:removed@v15, wiki-0/r0:removed@v27, retrieval-1/r0:removed@v8. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed806.txt) |
| V3 | 812 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 192, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["action", ["delete", ["d3"]]]. Stored versions: wiki-0:r0@v27. Live mirror: retrieval-0/r0:removed@v10, wiki-0/r0:removed@v30, retrieval-1/r0:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed812.txt) |
| V3 | 857 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 244, d3 is judged enforced while present in wiki-0, retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r1@v27, retrieval-1:r1@v3. Live mirror: retrieval-0/r0:removed@v34, retrieval-0/r1:removed@v39, wiki-0/r1:removed@v43, retrieval-1/r1:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed857.txt) |
| V3 | 871 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 273, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v32. Live mirror: retrieval-0/r0:removed@v28, wiki-0/r0:removed@v40, retrieval-1/r0:removed@v9. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed871.txt) |
| V3 | 872 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 200, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v4. Live mirror: retrieval-0/r0:removed@v20, retrieval-1/r0:removed@v7, wiki-0/r0:removed@v31. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed872.txt) |
| V3 | 890 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 291, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v3. Live mirror: retrieval-0/r0:removed@v19, wiki-0/r0:removed@v51, wiki-1/r0:removed@v15, retrieval-1/r0:removed@v14. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed890.txt) |
| V3 | 938 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 251, d3 is judged enforced while present in wiki-0, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-0:r0@v29. Live mirror: retrieval-0/r0:removed@v24, wiki-0/r0:removed@v48, retrieval-1/r0:removed@v13. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed938.txt) |
| V3 | 962 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 241, d3 is judged enforced while present in retrieval-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: retrieval-1:r0@v2. Live mirror: retrieval-0/r0:removed@v13, retrieval-1/r0:removed@v8, wiki-0/r0:removed@v49. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed962.txt) |
| V3 | 968 | The retained mark-and-sweep protocol can tombstone an unconfirmed fact at a newer watermark while its store entry survives. At tick 308, d3 is judged enforced while present in wiki-1, before the silent rewind. Atomic event: ["report", null]. Stored versions: wiki-1:r0@v1. Live mirror: retrieval-0/r0:removed@v27, wiki-1/r0:removed@v10, wiki-0/r0:removed@v44, retrieval-1/r0:removed@v22. The enforcement predicate has no included/pending blocker for this deleted document; the store still holds it. | [full trace](phase2/traces/V3-W-drift-seed968.txt) |

## Harness handling and verification

No phase-1d protocol source, invariant implementation, cost metric or scenario expectation was changed for the batches. No new harness bug was found or fixed. W-drift acceptance and read-only latency observation live in `phase2.py`; all original model verdicts, violations and metrics are retained alongside accepted verdicts. Replay comparisons canonicalize tuple-bearing cycle witnesses through JSON before comparing with JSONL arrays; this verifier serialization correction affects no model transition or batch. Observer parity was checked against the original model for every main variant/workload combination.

`verify.py` recomputes every report table from raw JSONL, checks complete seed coverage and all workload/source hashes, validates acceptance and flip counters, regenerates witnesses, and compares replay results identically. The entire generated Markdown must match REPORT.md byte-for-byte.

## Limits

- Snapshot views, register operations, store mini-batches and replacement are atomic. The model does not represent torn snapshots, distributed transactions or database isolation anomalies.
- The platform has an idealized immediate liveness flag. Failure detection time, false suspicions and partitions between independent detectors are not represented.
- The population is eight documents, paired Wiki pages, two resources and two projections. This is not a scale or throughput benchmark.
- Time is logical ticks. Queue boundaries and FIFO tie order idealize transport, storage and concurrent execution; no physical latency calibration is claimed.
- There is no durable outbox. A projection crash can lose unsent confirmations; the pending-age and heartbeat paths must repair the mirror.
- A restore rewinds mirror facts only; projection counters, stores, expiry metadata and Build fences remain. Silent corruption can make judgments wrong before detection.
- The digest uses stable truncated SHA-256 XOR. The model does not inject hash collisions or Byzantine publishers.
- Fault draws share scheduler RNG. The same workload hashes guarantee the same external actions, not identical fault realizations after variants take different branches.
- Finite seeds and the event bound cannot prove the design or fence redundancy. Costs at repair-cycle bounds are censored. Undefined repair-completion latency is kept distinct from recovery without a repair and from unrepaired/censored runs.

No network, paid API calls, commits, pushes or GitHub operations. All writes are under round2/.
