# T07 two-axis review

Base: `42f90f4da93ac7ad702744ba1870300ee34a4ebf`.
Initial implementation: `9cd402c`. Two independent read-only agents reviewed
Standards and Spec using the code-review skill; neither edited the implementation.

| Axis | Initial findings | Correction / recheck |
|---|---|---|
| Standards | No documented-rule violations. One optional duplicated strict/scoped method comparison. | Centralized `methods_match`; no outstanding finding on recheck. |
| Spec | No actionable implementation defect or scope creep. Final runtime evidence was pending. | Rechecked the correction and strengthened evidence-policy assertion; no implementation blocker. Final runtime acceptance is recorded separately in the evidence verdict. |

The Standards inspection also noted that the warm parser checked its sidecar
producer only before its receive loop. The implementation now validates every
request against the process's actual checkpoint dependencies before readiness or
artifact writes. Expected-method validation runs first for accurate failure codes.
Both reviewers confirmed the correction. Typechecking and all ten regression tests
passed afterward. No T06 source-quality limitations were upgraded by these reviews.

A final dependency audit removed parser-only options/models, known native-only
packages and transport/tooling from OCR/evidence runtime identities; unknown
packages remain conservative. It also added `processing.py` to enrichment producer
dependencies because evidence uses its serialization helper. Both reviewers
rechecked this adjustment with no outstanding finding. The full matrix and suite
were rerun on that final compatibility producer. Subprocess audit assertions were
then added to the compatible cases without changing production code.
