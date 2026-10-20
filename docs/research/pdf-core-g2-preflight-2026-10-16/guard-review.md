# Independent render-guard review

Review date: 2026-10-16. This review covers the new registration and
`render_preflight.py`, plus the installed Docling API-engine factory, input
builder, API engine and image normalization. It changes no runner or prior
evidence. Expected load is one local research process with eight fixed cases.

What this change does: The runner captures actual `VlmEngineInput` values from
the native `VlmPipeline`, then compares a later render against an inspection
approval before returning a fixed synthetic response. This validates rendering
and the approval boundary; the response does not measure model quality.

Final verdict: pass for the exact eight fixed research inputs. The corrected
native gate allowed six approved inputs with successful synthetic conversion
and blocked the two visibly damaged inputs before any synthetic transport
return. The original failed attempt remains preserved. No model inference was
performed.

## Initial findings, corrected before execution

1. **Must fix: a pre-engine failure can be assigned to another case.**
   `observations[-1]` after `converter.convert()` assumes the engine hook ran.
   If a later page fails before that hook, the preceding record receives its
   status; if the first page fails, the runner raises `IndexError`. Associate
   one record with each case before conversion and explicitly record that the
   engine hook was never reached. Otherwise a render failure can disappear.

2. **Must fix: unexpected failures can leave no structured result.** The
   results file is written only after all conversions and final assertions.
   A source mismatch, unhandled conversion exception or failed final check can
   leave a populated output directory with no failure record. Persist the
   per-case observations and final failure before propagating the error.

3. **Must fix before reporting delivery success: allowed transport does not
   imply successful conversion.** The original checks count six allowed and
   two blocked records without checking native success for the allowed cases.
   A parser failure after the stub would satisfy those gate counts. Keep gate
   permission and native conversion outcome separate, and require successful
   native status before claiming this synthetic delivery path works.

## Correction review before execution

The parent preserved the unexecuted original runner and original freeze, then
corrected all three findings before collection. Each case now owns a record
before conversion, records engine entries and exceptions, and persists in a
`finally` block. Allowed inputs must have native success; blocked inputs must
have zero synthetic transport calls. No blocker remains to collect the eight
fixed diagnostic inputs.

The parent also added a top-level state: `running` during processing and
`completed` only after all final checks. File existence alone is not evidence
that the run passed. Startup errors before the first persisted record still
depend on the process error, which does not affect this completed fixed run.

## Checks that passed by inspection

- Approval uses full equality over source path and digest, physical page,
  backend, render/VLM scales, serialized pipeline options, RGB size/pixels,
  and the full non-image engine input digest. Changing any bound value denies
  approval. The gate runs before the synthetic transport return.
- RGB hashing matches the API engine's own normalization. The hook inspects
  the real pipeline's engine inputs, including prompt, generation limits,
  stop strings and extra generation configuration. It does not claim a future
  Paddle preprocessing path has the same inputs.
- Dark-pixel fraction is descriptive evidence only. It does not decide
  acceptance and cannot reject a legitimate dark source page automatically.
- Source bytes are checked against fixed digests before conversion. The four
  cases are fixed known diagnostic pages, not an unseen quality sample.
- The explicit API-engine factory branch returns an API object without local
  model construction or artifact download. Its initializer only validates
  options. The synthetic method replaces the API request method, and socket
  connects are forbidden during pipeline execution. MLX absence is asserted.
- The stub text, purpose, and stop reason explicitly identify synthetic
  process evidence. There is no model-quality score.

## Collection review

The collection result reports `completed` with exactly eight unique cases,
one native engine entry each, and successful synthetic conversion for every
case. That first executed runner digest is
`3423f52a0e267b8bdf9a866a2dff478cfb109b697498bc31fa361c718eb1275d`.
Independent integrity checks passed for all collected PNG file hashes, RGB
pixel hashes and sizes, full non-image request digests and source digests.
The v2 execution freeze matches the runner, registration and prior evidence;
the original unexecuted freeze still matches its preserved runner backup.
`guard-artifact-integrity.json` records 16 successful checks.

I independently viewed all eight native engine-input PNGs. Both renderers show
the control's matrix, fraction, piecewise expression and nested code, and the
WikiSkill figure/page. The original Docling validation p1/p12 images have large
dark blocks obscuring the content, while PyPdfium shows the title/abstract on
p1 and readable prose/math on p12. This supports rejecting those two original
renderer inputs by visible content failure; no global pixel threshold decides
approval.

The extracted guard functions also passed 17 independent unit controls in
`guard-negative-controls.json`: the exact approval allows; absent, rejected or
partial approval and every changed fingerprint field deny. Explicit changes
to one pixel, the actual prompt and extra generation configuration also deny.
That first control file binds the original pre-review runner; the final
versioned controls below bind the executed runner and saved approvals.

## First gate failure and correction

The first gate attempt correctly denied all eight inputs: its options digest
differed from the approved collection digest. This is a failed 6/2 integration
attempt, despite identical pixels and engine-input hashes. It must remain
preserved separately from any retry.

Independent diagnosis proved the sole difference can be the order of
`chart_extraction_options.model_spec.supported_engines`. That field is a set,
but Pydantic serializes it as a list; sorting dictionary keys does not sort
that list. Permuting only this one list exactly reproduced both recorded
digests. `guard-options-order-diagnosis.json` records that proof. The fix must
canonicalize set semantics while keeping meaningful sequence order, followed
by a separately frozen retry. Approval binding must remain strict.

The corrected runner uses the Python options dump and a narrow JSON encoder
that sorts only sets/frozensets, serializes paths as text and rejects unknown
types. It saves the full normalized options. Independent AST-extracted tests
passed 33 checks in `guard-canonicalization-controls.json`: all 24 insertion
orders of the four-engine set share a hash; changed membership changes it;
ordered lists/tuples and duplicate elements retain their meaning. Nested sets,
dictionary order, paths and unsupported values were also checked. No blocker
remains in this correction by inspection.

The first configuration-only check then exposed an actual-schema gap:
Pydantic's API URL is `AnyUrl`, which the strict encoder initially rejected.
This happened before the new freeze or a pipeline execution. The parent added
explicit `AnyUrl` text encoding while retaining rejection of unknown types.
The earlier 33 checks were toy-value tests and did not cover this API type.

`guard-schema-controls-v2.json` closes that coverage gap. I imported the actual
runner module without calling `run` or converting a document, then created its
real options in two separate processes with `PYTHONHASHSEED=0` and `1`.
All 66 actual-schema assertions passed, and both options digests were
`58bc18ad4adf953ebb62b8980594f454f227c9fe71c571584709694fd9537a92`.
The checks cover the actual URL type/value and changed URL, all 24 orders of
the actual engine set, changed set membership, ordered stop strings, paths,
zero socket attempts and absence of `mlx_vlm`. No pipeline was executed.

## Corrected native gate and final independent verification

The fresh collection and gate both report `completed` under runner digest
`b444aea51a33f30a99cb1e9a13961b68516105ab813253789d7f8bd54eb53f5a`.
The coordinator confirmed the gate process exited zero. The v3 execution
freeze and v2 approval freeze match their files. Normalized options are equal
across collection and gate and hash to the stable actual-schema digest above.

`guard-artifact-integrity-v2.json` records 17 successful checks: fresh input
PNG file bytes and RGB pixels exactly match all eight images directly viewed
in the first collection, as do source/page/backend/scales and full engine
inputs. Only the options digest changes through the documented fix. Prior
evidence and the earlier executed runner backup still match their freezes.

`guard-final-verification-v2.json` records the final native outcomes and ten
freeze checks. Every collection fingerprint equals its saved approval and its
new native gate fingerprint, including full source digest and normalized
options. All eight records have exactly one engine entry. Six approved inputs
have one synthetic transport return and native `success`. The two rejected
Docling validation inputs have zero synthetic returns and native `failure`.
Thus those failures are recorded denials, not omitted pages or parser success.

The same file records 106 independent controls using the actual saved
approvals and actual captured images/requests. Exact approvals follow their
six approved/two rejected decisions. Missing approvals deny all eight.
For all six approved cases, changing any fingerprint field, one real pixel,
the prompt, generation limit or extra generation configuration denies before
the test's synthetic return; an incomplete fingerprint also denies. These
controls extract only guard functions and do not execute another pipeline.

No model inference, network requests, holdout content or historical artifact
writes were performed in this review. The native runner records zero model
and network calls, no model loaded, and zero holdout reads. The API factory
inspection and socket prohibition support those bounded claims.

Verdict: pass for this research-run input guard. All original findings and the
unstable-set defect were corrected before the successful versioned retry.

Not checked: no model quality, future Paddle preprocessing, general-purpose
security enforcement or independent duplicate native conversion. Synthetic
delivery success does not establish semantic acceptance or extraction quality.
