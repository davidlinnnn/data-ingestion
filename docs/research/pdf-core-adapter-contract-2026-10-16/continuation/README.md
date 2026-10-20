# Continuation prerequisite: stop

2026-10-16. The unchanged `src/pdf_processing/continuation.py` policy fails two necessary controls. **Do not implement the mapper or tune this policy as part of A′.** This is a bounded delivery-contract result, not a model-accuracy measurement or a universal claim about Docling.

The 24 inputs, truth and stop threshold were written to [controls.json](controls.json) before running the policy. Its SHA256 is `5b02f864b67e1bb915f28cc05402edd7b79cb2a65259a32225d4d9182f494d33`. [freeze.py](freeze.py) uses only the standard library and package metadata; [run.py](run.py) calls the existing policy once per control, with no rule or threshold changes. Results and identities are in [results.json](results.json).

| Check | Result | Meaning |
|---|---|---|
| Frozen controls | 22/24 pass | Two required semantic relationships are wrong. |
| Existing unmodified synthetic tests | 11/11 pass | These tests do not cover the two failing cases; their success does not cancel new failures. |
| Actual-label tall-body/right-title control | Expected `{}`, actual `{"0": [1]}` | A tall body paragraph absorbs the separate right-hand algorithm title when both retain the native `text` label. |
| Ordinary independent paragraphs, first lacks punctuation | Expected `{}`, actual `{"0": [1]}` | Lowercase final character and matching page-edge geometry alone cannot distinguish a new paragraph from continuation. |
| Correctly typed heading counterfactual | Pass | Helpful contrast only; replacing the actual title label to pass would hide the existing discovery/typing gap. |
| Per-control preservation/ID/ownership/cycle invariants | All pass | Inputs remain unchanged and output chain ownership is well formed; semantic misassociation still occurs. |

The 24 controls comprise four expected-merge positives (margin-before-body, cross-column uppercase, cross-page chain, inline chain), 14 existing-test-equivalent negative variants, and six added negatives (caption barrier, heading barrier, independent punctuated paragraph, independent unpunctuated paragraph, preserved actual-label title, typed-title counterfactual). The four positives and 18 negatives pass. The two negative failures remain failures. Existing test subcases are represented individually in the frozen control count; the separate unittest count is test methods, not an additional document sample.

The title control is a minimal policy input reconstructed from **explicit existing provenance fragments**, not from PDF content or inferred raw VLM text. The prior preserved `source-snapshot.json` has item `#/texts/34`, provenance 0 (body charspan `[0,657]`) and provenance 1 (title charspan `[658,734]`), page 4, 612×792 points. The control preserves their native text labels, coordinates and substrings. Prior review already established that the title belongs separately. This tests the mechanism described in the [earlier boundary report](../../pdf-core-g2-inline-boundary-2026-10-15.md); it is not a live upstream parsing replay or proof of an implemented splitter.

The independent-paragraph case is authored synthetic truth, frozen before execution: `Method A uses a fixed schedule` and `Results improve on the held-out set.` are two paragraphs. It establishes a concrete false positive, not a population error rate. The ordinary punctuated-paragraph counterpart passes. The same-line inline chain and multi-page/cross-column positives also pass, so the failure cannot be removed by simply disabling every merge without losing required positives.

Runtime: existing `docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python`, Docling 2.102.0, Docling Core 2.96.0, IBM models 3.15.0. Source review verified that `ReadingOrderPredictor` is rule based, its package initializers are empty, and its constructor sets two geometry parameters. No learned model weights are loaded. The runner blocked network connection methods, observed zero attempts, and no `torch`, `transformers`, `onnxruntime`, `rapidocr`, `mlx`, `paddle`, `paddlex` or `openai` runtime modules were imported. There were zero inferences, installs, environment creations and PDF/image/holdout reads.

The runner asserted all eight frozen source identities and the fixture hash both before and after this single run. The unchanged continuation source SHA256 is `791e2ebef036d6f2468fb607162a135eecb3c4eaa056d4e35b1a81bffde49772`; the upstream rule predictor SHA256 is `68e2be8f709e8ed29a44597780d38dbb93deec4841e007b7b61a99b8a0cecf10`. The existing source snapshot SHA256 is `ac24732003ac15e77ec1af8213cb686c174fff3b8983f904020504c96ab14fad`. No historical evidence, production code or existing test was edited.

Two older tests were **not run** because `/private/tmp/t09a-r2-20260914/checkpoints` no longer exists: `Continuation.test_source_continues_into_body` and `Preservation.test_input_content_not_mutated`. No checkpoint was recreated; the 24 per-control input-preservation checks cover only this run's inputs.

The failure threshold was fixed before execution: any required expected-relation mismatch is material. Both failures exceed it. No second run, policy edit, mapper, model call or Paddle action followed. A broader paragraph discovery/assembly method would exceed the approved reuse-only scope.
