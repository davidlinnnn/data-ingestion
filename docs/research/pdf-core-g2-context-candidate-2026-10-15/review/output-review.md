# Independent structural/source-input review

The candidate passes this bounded structural review under the pre-output [evaluation contract](evaluation-contract.json). [check.py](check.py) and [output-review.json](output-review.json) reproduce the checks. No new model response was generated or graded. No challenger is selected for holdout, and G2 remains unpassed.

| Document | Native item refs | Group refs | Planner rows | Ready | Member | Abstain | Unsupported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| controls | 20 | 1 | 12 | 9 | 3 | 0 | 0 |
| seal | 326 | 15 | 142 | 118 | 0 | 5 | 19 |
| wikiskill | 514 | 16 | 291 | 124 | 0 | 8 | 159 |
| dgm | 734 | 28 | 371 | 139 | 0 | 45 | 187 |

All **1594 native item refs and 60 group refs** match the frozen source documents and hashes. The **816 planner rows** inventory the configured native roles; they are not a semantic opportunity denominator. Re-running the planner preserves native objects and reproduces every row. Independent bijections of native refs and a changed document name preserve dispositions/context associations; translating source coordinates preserves decisions and shifts the emitted envelopes correctly. The supplied synthetic planner checks also replay exactly.

On the five existing selected document/page pairs, 44 rows comprise **36 prepared jobs, three formula members and five explicit abstentions**. The prepared jobs are 27 ordinary paragraphs, six code items and three formula envelopes. Whole-item cross-page targets require eight distinct physical page rasters. The checker independently renders those eight pages from the source PDFs, reconstructs all 42 source fragments and 36 canvases, checks exact pixels, 2-point outward padding/clamping/rounding, physical page identity, inverse transforms, source scope hashes, target/context roles and prepared request hashes.

All three controls formula envelopes equal both the independently derived parent-plus-child unions and the old fixed crop envelopes. Visual inspection confirms complete matrix brackets, fraction structure and both piecewise branches. The controls comment/body inputs contain all seven code lines once with visible nesting. Each request retains one native code target; the other code item is read-only context. The separate inline item14 retains its own scope.

Only **two selected jobs add neighboring context, both controls code items**. The selected ordinary-paragraph context rule triggers zero times, including SEAL32. Its existing standalone pixels remain clear, but its saved incorrect model identity/subscript/prime remains semantically unapproved. Four standalone SEAL formula rows abstain on incomplete or overlapping native character provenance and produce no prepared inputs. These are coverage gaps, not recovered formulas.

SEAL34 explicitly abstains on its same-page multi-provenance boundary. Both native34 spans `[0,657]` and `[658,734]` remain intact, and native45 continuation stays separately accounted. No prepared SEAL34 request exists; no silent fragment loss or blanket omission occurs. This does not demonstrate automatic caption separation or a repaired complete body paragraph.

| Prior paragraph scope | Planner disposition | Protected positive scope |
| --- | --- | --- |
| wikiskill-texts-361 | ready | — |
| wikiskill-texts-362 | ready | Opening-sentence omission regression restored |
| wikiskill-texts-363 | ready | F13 math/prose pass |
| dgm-texts-648 | ready | F14 selected token/binding/number pass; hyphenation difference remains visible |
| seal-texts-30 | ready | F13 cross-page paragraph pass |
| seal-texts-32 | ready | — |
| seal-texts-34 | abstain | — |
| seal-texts-46 | ready | — |
| seal-texts-49 | ready | — |
| seal-texts-52 | ready | — |
| controls-texts-4 | ready | — |
| controls-texts-6 | member | — |
| controls-texts-8 | member | — |
| controls-texts-10 | member | — |
| controls-texts-12 | ready | — |
| controls-texts-13 | ready | — |
| controls-texts-14 | ready | — |

All four bounded positive anchors stay planner-ready. This is structural eligibility; new-input semantic outcomes remain **not evaluated**. The 17 original refs/scopes stay visible, including the three formula children now inventoried as members of their parent-envelope jobs and unresolved SEAL34.

Legacy adapter review separately reconstructs each of the **17 original HTTP requests** from its frozen description and exact original image bytes, verifies response/output hashes and equality, and replays only those original scopes. Eleven responses apply structurally; all four bounded positive anchors retain structural eligibility. The three hidden formula children remain unsupported serializer boundaries; code12 and inline14 have native/model role mismatches; SEAL34 has two roots. No lexical gate rejects the old positives. Original review labels remain fixed, including the known SEAL32 semantic failure.

All four legacy working Markdown documents reproduce from their exact proposals; baseline Markdown, raw provider hashes, outside literal spans, old input/output artifacts and association hashes match. The adapter’s 19 saved negative controls are retained, and this checker independently rejects stale outside graphs, shrunk targets, context consumption, duplicate/nested scopes, changed image/prompt fingerprints, old responses with changed context and unknown model segments. Reviewer crop-rounding, transform and missing-inventory controls also fail as intended.

All newly prepared prompts differ from the old requests. Historical responses therefore provide **no replay-compatible new-input model-quality result**. Target rectangles cover padded native source fragment crops and are explicitly coarse canvas regions, not measured glyph masks; no new model has consumed them.

Not checked: new model behavior, semantics of unrun context inputs, untouched sources, all 57 G1 cases/V01–V19, production SLOs or Canonical Acceptance. Structural success leaves the paragraph-context and SEAL boundary/formula gaps visible.

```sh
rtk docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python -B docs/research/pdf-core-g2-context-candidate-2026-10-15/review/check.py
```
