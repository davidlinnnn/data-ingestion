# Conservation-guard shadow regression

**Do not promote this rule as a global rejection gate.** The frozen native-token conservation guard rejects two of four existing source-positive anchors. No regex, threshold, source payload, model response, or application code was changed. No API calls or inference were run.

[regression.py](regression.py) imports only the frozen adapter's `conservation` callable for decisions. [results.json](results.json) records all 17 prior paragraph outputs, source-review labels separately, two new target-only diagnostics, and before/after hash checks for **943 unique frozen files**, including all **846** prior payload entries. [selfchecks.json](selfchecks.json) records six in-memory behavior/limitation checks. `artifact-sha256.json` freezes this regression's four payload files.

| Scope | Guard result | Interpretation |
|---|---|---|
| All17 prior outputs, first raw block probe | 13 pass,4 abstain | Shadow probes only; one item has two roots and no valid one-block whole-item association |
|16 single-root outputs |13 pass,3 abstain | Lexical eligibility, not source-quality approval |
|11 previously structurally applied outputs |8 pass,3 abstain | Two source-positive outputs and the known wrong SEAL32 would newly abstain |
|4 existing positive anchors |2 pass,2 false abstentions | E13/SEAL30 and WikiSkill362 pass; E14/WikiSkill363 and E04/DGM648 abstain |
|Old SEAL32 |Abstain for lost `LM` occurrence | Catches the saved wrong nested model identifier; does not establish a general semantic check |
|New SEAL32 target only |Abstain for lost `LM` occurrence | Adjacent formula context is excluded, so its identifier cannot satisfy target coverage |
|New SEAL34 body target only |Abstain for `misaligned`, `parameters`, `result` | Uses repaired body34+45; retained foreign title is excluded |

The material false abstentions are native `topranked` versus API `top-ranked` in E14, and native `benchmark` versus API `bench-mark` in E04. Independent review gives E14 a bounded F13 pass. E04 has a selected code-token/binding/number F14 pass while retaining the minor hyphenation difference explicitly; this is not relabelled an exact full-transcript pass. Those source-positive labels remain visible and unchanged in the results even when the guard rejects them.

The rule counts ASCII multiletter occurrences and removes LaTeX command names while retaining arguments. Greek native characters contribute no such tokens. An in-memory wrong Greek identity and a single-letter inequality change therefore both pass; these are recorded blind spots, not quality successes. The existing E13 source-positive Greek/LaTeX paragraph passes, but that does not prove this guard validates its math. A wrong matrix delimiter can also pass the word guard. Coverage and semantic fidelity must remain separate.

The runner asserts the frozen guard SHA, all four positive labels, both observed false abstentions, and the explicit `do_not_promote_as_global_rejection_gate` decision. A changed guard or silently omitted approved anchor fails the replay. It does not tune normalization to these examples or alter any current adapter outcome.

These17 selected outputs are **regression data, not an unseen holdout**. The crop/context source policy covers only the six declared prototype jobs. A fresh cross-source holdout, general detector coverage, and evidence that broader application preserves other cases remain missing. This already-rejected global rule requires no extra API calls to establish its observed regression.

Replay with the existing isolated runtime:

```sh
rtk docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python docs/research/pdf-core-g2-inline-boundary-2026-10-15/regression/regression.py
```
