# PDF checkpoint performance diagnosis

**Finding: the measured slowdown is primarily the prototype's execution shape, not Temporal orchestration.** Keep Docling and Temporal as the current prototype direction. Optimize the observed wait and process lifetime before considering a parser rewrite; separately evaluate checkpoint granularity against recovery cost. This is a diagnosis, not a production performance acceptance test.

The earlier 112.25 s workflow included component OCR, durable checkpoint output and many child processes. Its 50.08 s comparator was one native conversion process without enrichment. Historical accounting already places 90.77 s inside parsing/assembly children and 2.36 s in the OCR Activity; attributing the complete difference to Temporal would be incorrect.

## Repeated comparisons

Measurements below come from `evidence/analysis.json`. Three trials per condition; no concurrent benchmark jobs. Both fixtures use the same pinned Linux image/configuration, source bytes and final output assertions. The native paper has 51 pages and five-page groups; the scanned fixture has two pages and one-page groups. Do not extrapolate the scanned result to a 51-page scanned paper.

| Execution | Native 51 pages, seconds | Scanned 2 pages, seconds |
|---|---:|---:|
| Whole, fresh process | 46.66 (44.94–46.80) | 11.00 (10.67–11.23) |
| Grouped direct, fresh children | 110.36 (109.84–111.42) | 21.01 (20.01–21.08) |
| Grouped Temporal, fresh children | 111.71 (111.26–112.81) | 20.54 (20.04–22.09) |
| Grouped direct, warm steady state | 82.15 (81.43–82.72) | 14.85 (14.76–15.34) |

Cells are median (minimum–maximum), n = 3. Warmup median: native **6.30 s**, scan **6.83 s**. Including warmup, parent setup and shutdown, warm launcher medians are **89.21 s** and **22.33 s** respectively. Thus the two-page scan does not show a one-off total-time win from warming a new converter. Cold direct/Temporal launcher medians differ by **1.35 s native** and **−0.46 s scan**; with n = 3 and staggered trials, do not treat either as an exact Temporal tax.

Whole time includes a fresh child process, parsing, document assembly and JSON/Markdown export. Grouped cold launcher time also includes parent bootstrap, all fresh children, actual shared storage, completion registration, assembly and full JSON fidelity checks. Warm steady-state time excludes the explicitly reported one-time daemon startup/discarded warmup group. Enrichment is excluded from every matrix cell. Grouped additionally persists internal checkpoints; identical final documents do not imply identical intermediate output scope.

“Cold” here means a new Python process and converter after an excluded filesystem/model-cache warmup, not a freshly booted machine. Warm converter requests run sequentially with fresh input/output state and stable pipeline instance IDs. Assembly remains fresh-process guarded restoration. The actual trial sequence is retained in the index: a variant-label bookkeeping error initially skipped repetitions 1/2 of cold direct trials, which were filled afterward with the corrected runner. Consequently this is not a perfectly counterbalanced experiment.

## Attribution

For the native case, three-run medians show:

| Measured component | Whole | Grouped direct, cold | Grouped direct, warm |
|---|---:|---:|---:|
| Module imports inside timed work | 1.98 s | 23.67 s | 1.95 s (fresh restoration only) |
| Converter initialization, nested in conversion | 0.34 s | 3.72 s | 0.004 s after warmup |
| Conversion/reconstruction calls, sum across sequential requests | 43.39 s | 59.93 s | 63.10 s |
| Layout/table overlapping time | 31.55 s | 2.82 s | 2.92 s |
| Layout/table interval union | 42.10 s | 55.33 s | 58.31 s |
| Method fingerprint checks | 0.26 s | 3.40 s | 3.59 s |
| Local checkpoint commit / load | — | 2.35 / 1.00 s | 2.20 / 1.02 s |
| Final document assembly stage | 1.19 s | 1.15 s | 1.17 s |

The dominant explanations are repeated imports and reduced layout/table overlap. The grouped layout/table union grows despite smaller individual stage sums. Warm reuse removes repeated initialization but retains group barriers and checkpoints; measured grouped conversion calls actually take somewhat longer warm, so do not promise that reuse speeds up model inference itself. Backend constructors total only 0.044 s cold grouped; this excludes lazy backend extraction. JSON/Markdown export totals about 0.24 s; it is not the main serialization cost.

The native direct run leaves about **18.85 s** outside child calls and measured imports (warm: **13.56 s**). This includes publication waiting and process startup/exit as well as shared I/O and parent validation. These are median component summaries, not a sum-to-total decomposition: medians of separate quantities need not add to the median wall time.

The real-store paired publication test used 185 files, 12 accepted operations and approximately 76.12 MB of payload, with each original artifact hash verified. Three trials gave **12.118 s (12.101–12.129)** with legacy polling and **0.924 s (0.906–0.934)** when awaiting completion. The observed lag after actual publication completion was **10.89 s** median across the 12 operations for legacy polling and less than 0.001 s when awaited. The approximately **11.19 s** end-to-end ablation difference also includes ordinary store/cache variation; it is not all pure polling lag. This confirms a large removable wait, without claiming an optimized full workflow was measured. Normal grouped direct successful-request timers total about **1.47 s**, but do not represent complete storage overhead.

For the scanned two-page case, imports grow from **1.98 to 5.84 s** and conversion calls from **7.68 to 8.35 s**; the layout/table overlap effect is absent (no substantial table stage). It is largely a fixed-cost problem at this size. Native PDF OCR is disabled during parsing; scan-page OCR is part of parsing and remains enabled in every scanned comparison. The separate historical component-image OCR Activity took **2.36 s**, of which **0.86 s** was engine initialization plus recognition (58/58 scored labels). It includes neither a full-document rerun nor evidence of 51-page scanned throughput. No new OCR-only benchmark was needed to explain the matched no-enrichment matrix.


Instrumentation boundaries matter:

- Module import time is measured separately from `exp.main()`. Diagnostic `metrics.wall_seconds` therefore excludes import, unlike the historical original entry. Use launcher/workflow wall time for comparisons. Warm daemon import occurs during warmup once; analysis never sums that repeated metadata once per group.
- Model initialization, fingerprinting, backend constructor, exports and conversion timings are nested components. Their sums are not additional wall time. The backend constructor probe does not cover every lazy PDF backend operation.
- Layout/table overlap uses measured intervals. Stage sums are explicitly **not** wall time. Group barriers are an observed scheduling difference, not evidence of more expensive individual table inference.
- Checkpoint commit/load includes local serialization and validation; shared materialization, hashing, registry verification, file copies and JSON comparison also run in the parent. The residual outside child calls/imports includes these, publication waits, process startup/exit and orchestration. It is not all network or all Temporal.
- Successful S3 request timers cover only selected calls, not the full store path. The separate actual-store publication ablation includes payload reading, hashing, uploads, conditional completion registration and readback, and measures completion-to-observation lag directly. It does not isolate all assembly download/validation CPU or node filesystem behavior.

## Decisions supported by this evidence

1. **Remove the artificial publication wait in the next bounded implementation change.** Await completion while retaining periodic heartbeats instead of sleeping through an already completed upload. The ablation preserves real MinIO conditional registration/hash checks. Re-run the existing real Pod-loss/lost-ack gates after any worker change; performance tests alone do not prove recovery behavior.
2. **Prototype a persistent parser subprocess/worker lifecycle next.** Sequential converter reuse saves repeated imports/model setup and preserves full fixture fidelity here. Specify memory recycling, cancellation, crash replacement and concurrency before adopting it. Do not assume a mutable converter can serve simultaneous activities safely. Method/source/producer identity checks remain necessary.
3. **Compare a small number of group sizes only after those fixed costs are addressed.** Whole conversion retains more layout/table overlap; five-page barriers sacrifice some throughput to bound unfinished work. Evaluate normal-path time together with repeated work after loss and artifact size. This evidence does not select an optimal group size.

These costs merit bounded optimization before treating the measured normal path as a production target. There is no stated throughput/latency SLA, so this report cannot declare the pipeline fast enough or too slow for production. It does reject the claim that Temporal itself accounts for a twofold slowdown in this local setup.

## Correctness, limitations and cleanup

Every successful matrix run asserts complete final JSON equality with the original Linux baseline; checkpoint method validation remains enabled. Fresh S3 prefixes prevent reuse from making normal-path trials artificially fast. Compact diagnostics verify expected 51/2 page-stage counts, no page processing during restoration, and a stable warm pipeline ID within each warm trial. Original K8s fault evidence is preserved separately.

The environment is one local ARM64 Docker VM and a single selected kind node, with actual MinIO/Temporal services in a dedicated namespace. Bench memory is capped at 5 GiB; CPU has no quota; model libraries use four threads. No competing benchmark was launched, but host/VM scheduling and caches are not controlled laboratory hardware. Three trials describe observed spread, not a confidence interval or production capacity model. RSS is a per-process high-water measurement; warm RSS is cumulative. Timing probes add some overhead to all compared parser variants.

No production code was optimized, no parser internals rewritten, and no canonical schema decision made. Warm reuse was tested directly, not through a long-lived Temporal worker or during a Pod crash. The publication ablation is frozen-output transport work, not a full optimized end-to-end workflow. Node loss, storage HA, broad document diversity and 51-page scanned behavior remain outside this diagnosis.

See [README.md](README.md) for exact commands, [evidence/verification.json](evidence/verification.json) for checks, and [evidence/cleanup.json](evidence/cleanup.json) for namespace removal. No commits or remote changes were made.
