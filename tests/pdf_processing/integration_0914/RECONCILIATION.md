# T08 / T09a reconciliation — 2026-09-14

## Disposition

T08 is ready to publish as a PASS for its declared phased compatible-worker rollout scenario. T09a is valuable, reproducible partial work, but remains OPEN. Neither result qualifies the combined source tree, production resource bounds, or canonical acceptance.

Reviewed branch snapshots:

| Task | Branch | Commit | Disposition |
|---|---|---|---|
| T08 #43 | `codex/t08-compatible-worker-rollouts` | `747bbdf7c50d726d574c3283e8a47ac5fc70a139` | Ready for integration verification and publication |
| T09a #44 | `codex/t09a-long-warm-qualification` | `863d2d1b17ff953e23924268408fc288b90e8772` | Preserve partial results and narrow evidence fix; do not close |

Both start at T07 `765d5483a61f8648f015e2f7f5538c54b62b6198`. Both worktrees were clean at review. T08's 61 sealed evidence files and T09a's 82 sealed files matched their recorded SHA-256 values (and T09a byte lengths). T08's sealed producer also matched all current package Python source hashes. These checks establish snapshot integrity, not independent reproduction of runtime observations.

## Accepted evidence and limits

T08's `tests/pdf_processing/t08/evidence/VERDICT.md`, runtime records and review support:

- Actually queued Workflow and group Activity work, pinned explicit stage queues, and explicit invalid/unavailable/conflicting routing failures.
- Native child Pod loss plus Workflow Pod replacement, and graceful drain, both followed by successful group attempt 2. Drain observation: 31.54 seconds; not a cleanup SLA.
- Actual required OCR scale 3→4 with compatible parsing/assembly reuse, distinct request-bound outputs, and current-Pod Temporal pollers on both Workflow and both OCR queues before and after mixed-method cases.
- Recorded full suite: 10 passing tests; focused suites passing; Pyright zero errors/warnings; corrected two-axis reviews.

This qualifies a one-page synthetic fixture under a predeclared phased rollout. Both releases use the same image/package/model bytes. It does not qualify a package/model upgrade, simultaneous full worker population, capacity, HA, or broader PDF quality. Interrupted exploratory trials remain excluded.

T09a's `tests/pdf_processing/t09a/REPORT.md` and review support successful full processing for the native 51-page paper, WikiSkill, YOLO, contiguous AIMA pages 99–110, ACL pages 2–4, and the one-page Keynote export. Required OCR/source evidence exists for successful outputs. A changed OCR scale reused parsing/assembly while producing newly bound OCR outputs. Fresh/warm JSON equality is a consistency result, not source-quality approval.

The narrow production correction permits positive-height, in-page, zero-width combining-only TextItems to retain full-page source context. It preserves raw text, type, JSON and zero-width provenance, records uncertainty, and does not invent a glyph crop or attach a combining slash to a neighboring operator. Invalid ordinary geometry still fails; zero-area regions cannot satisfy reviewed formula overlap. Recorded geometry coverage: 12 cases; the real AIMA seam completed with unchanged raw parser JSON.

T09a remains partial because:

- The warm sequence completed with three OOM restarts. Kernel records identify global OOM (`CONSTRAINT_NONE`), not a demonstrated 5 GiB container-limit breach. Neither a memory leak nor a sole competing process is established. Sampling has gaps; there is no qualified stable warm envelope or planned recycle result.
- Drain replacement also encountered global OOM. The retained workflow was last recorded assembling with 51 pages registered, not complete. Final recovery equality, reuse assertions and scratch cleanup remain unqualified.
- Restart-aware harness guards and cleanup corrections have static checks, but their runtime validation and the full 10-test rerun remain deferred.
- AIMA source-quality gates remain open even on contiguous pages: cross-page prose can join a margin label, algorithm headers/body/captions can lack declared relationships, and inequality representation is uncertain. Preserved evidence does not fix these associations.

The apparent image-name discrepancy was resolved by retained image attribution: the observed digest resolves to the same ARM64 Linux content. It is not evidence of a runtime-byte change.

## Integration contract

The changed-file intersection is only `src/pdf_processing/README.md`; preserve both additive contracts when integrating. This is a file-overlap check, not proof of semantic merge safety.

T08 adds routing modules and a Workflow Activity-dispatch seam. T09a changes `evidence.py`. Both affect the complete producer fingerprint. Therefore:

1. Preserve both original commits and evidence seals without rewriting them to describe the combined tree.
2. Integrate T08, then T09a's committed partial work, retaining its PARTIAL verdict. Resolve README additions explicitly.
3. Treat the integrated tree as a new producer/release. Generate its matching immutable routing/configuration bindings. Do not relabel an old queue or reuse an already accepted request ID with changed producer bytes.
4. Keep original workers/configuration available for old accepted requests, or use a new request identity for compatible artifact reuse after validation. Do not automatically resume the incomplete T09a request on new workers.
5. Before claiming integrated qualification, run scoped routing/dispatch and geometry regressions against the combined tree, then a bounded routed end-to-end case with required evidence and the new producer. Prior branch tests do not substitute for these checks. Heavy runtime work requires a controlled resource window with the host lock held through remote quiescence.

The evidence-interface addition must be communicated to consumers: use the declared crop recipe and `geometry_status`; do not derive a usable localized crop from the zero-width provenance line. Required enrichment still must finish before processing complete. Canonical adoption and future LaTeX enrichment remain separate.

## Next work and ticket handling

Live GitHub read on 2026-09-14 confirmed #43, #44, #45 and #46 are OPEN. Recommended disposition after publication:

- #43: attach the scoped PASS evidence and close after integration verification/publication.
- #44: attach partial evidence and keep open with explicit remaining gates. First inspect retained OOM/node/competing-memory records without inference. Then schedule a controlled fixed-profile warm/recycle run, followed by bounded drain/replay and deferred harness/full-suite checks. Do not silently raise limits or change recycling policy and call it the same qualification.
- #44 source quality: investigate the retained AIMA association/algorithm failures separately from resource recovery. Any reduction of the declared supported quality scope needs an explicit decision; processing success alone cannot approve it.
- #45: retain the #44 blocking edge. Resource tuning must not stand in for missing baseline qualification.
- #46: still waits for the required rollout and calibration gates; do not present this partial handoff as deployable-core qualification.

This reconciliation performed code/document/evidence reads and local hash verification only. No inference, workflow restart, cluster mutation, merge, push, or ticket update was performed. Existing unrelated main-checkout changes were preserved.
