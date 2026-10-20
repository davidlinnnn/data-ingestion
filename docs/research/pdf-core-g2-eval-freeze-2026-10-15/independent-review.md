# Independent evaluation-design review

Date: 2026-10-15. Offline review of `protocol.json` and `regression-manifest.json`; no holdout PDF/content was opened and no model was called.

Reviewed SHA256:

- Protocol: `56e0c5f9b8a061e50765b56f1ddd7c07c09c87ba77e0c3f3430957c2202ee5fe`
- Regression manifest: `508ad60768d8777d7d4e92666123135c4acb34da5a44cdaea5dc59c6059d4c75`

**Verdict: no remaining evaluation-design blocker found in these versions.** The freeze is a reviewable protocol, not permission to run or evidence of G2 quality. Source inventory, candidate locks, and applicable behavioral regression review remain pending; `holdout_run_permitted=false` and `g2_passed=false` correctly reflect that.

- **Exposure and grouping:** development/regression overlap is explicit and never called independent validation. The whole originating work and linked derivatives share a split; uncertain ancestry is ineligible. The holdout claim is limited to this experiment's method selection, with no template-family, pretraining-contamination, or production-representativeness claim.
- **Search budget:** at most three new complete configurations, registered before development runs, is a bounded project choice rather than a statistical guarantee. Earlier trials remain disclosed. One challenger is selected using exposed evidence before one paired holdout comparison; no holdout-based budget expansion, reshuffle, semantic retry, or best-of-N selection is allowed.
- **Page selection:** first/last physical pages plus up to two pages selected by source-hash/page-number ordering is deterministic and outcome independent. Equal context and source-first inventory prevent emitted content from defining the denominator. Sparse subtype coverage remains explicitly unevaluated; it cannot justify outcome-driven replacement pages.
- **Metrics:** the revised protocol fixes one outcome per frozen non-overlapping source opportunity. Inline obligations remain nested, duplicates fail their source unit, and unsupported additions are separately counted and block adoption. Technical failure counts affected opportunities, with failed attempts reported separately. Explicit abstention, failure, and missing/not-attempted outcomes remain distinct; all stay visible in the fixed eligible denominator. Zero accepted outputs give undefined selective error, and missing task strata are reported.
- **Regression retention:** an offline assertion check confirmed 57 unique case references, all 19 validation groups with internally consistent membership, 17 distinct paragraph-output references, and four protected positive anchors included among them. Source labels and retained hashes are explicitly not behavioral passes; bounded positive rubrics and the globally rejected guard remain protected.

Two initial ambiguities were reported and corrected before this verdict: counting model output blocks versus source opportunities, and dividing failed attempts by source opportunities. No new accuracy threshold or relaxed source rubric was introduced.

The design follows the separation, grouped-evaluation, abstention, and small-sample guidance summarized in [primary-sources.md](primary-sources.md). Reviewing rules cannot establish corpus independence, annotation completeness, capability coverage, or implementation compliance; those require the later frozen inventory and run evidence.
