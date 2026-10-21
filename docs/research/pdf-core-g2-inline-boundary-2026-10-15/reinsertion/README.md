# Boundary working results

The six new API responses produce four working model substitutions and two abstentions. Two separately attributed proposals complete the working comparison: the frozen earlier inline-code interpretation and a native-only paragraph boundary repair. Original provider documents, images, graphs, API outputs, and both prior payload manifests remain unchanged.

| Proposal | Working outcome |
| --- | --- |
| Three controls formula parent pictures | Replace only their working Markdown serializer boundaries; raw pictures, formula children, and source assets remain in custody. Model math strings are unchanged. |
| Controls adjacent code items 12+13 | One code block at 12; suppress the serialized 13 after complete native character, operator, line-order, and geometry-derived indentation checks. Both provider references remain associated. |
| SEAL paragraph 32 plus formula 33 context | Model paragraph abstains: native multiletter identity is lost. Formula 33 is context only and remains unchanged in the main serialization; all response blocks remain visible in the sidecar. |
| SEAL body 34 plus continuation 45 | Model proposal abstains: one occurrence of `parameters` is missing; conservative coverage also rejects changed line-wrap words `result` and `misaligned`. |
| SEAL native-only boundary fallback | At 34, serialize exact native body fragment + existing whitespace gap + full 45, followed by the separate exact native parallel title fragment. Suppress serialized 45 atomically. Every native character is accounted for once. No AI transcription or math completion is used. |
| Controls item 14 | Reuse the exact frozen earlier paragraph/code-segment interpretation only after native character/operator equality and mixed-font prose/code-run checks. The raw provider CodeItem remains unchanged. |

`controls/working.md` and `seal/working.md` are derived working Markdown. Their `working-delta.json` sidecars retain every new model block, including rejected proposals and context formulas, source fragments/transforms, declared consumed/context references, exact native charspan accounting, working segment offsets, suppressed serialization spans, and hashes of all untouched literal spans in order. The native parallel title is spatially separate; its caption role is only an inference with lineage to the earlier model response. The provider label is `text`.

The adapter reuses the frozen source hash/ref/span guards, compatible-root/duplicate-run guard, text serializer, and JSON renderer. A small picture serializer supplies the previously hidden formula boundary. Whole-document hashes protect neighbors and outside-scope content. Coalescing consumes declared references once; context references cannot be consumed. The code check derives a 6 pt monospace character pitch from native line geometry, then requires exact characters and measured indentation. Formula checks cover native signed numeric occurrences and multiletter identifiers, without claiming general math equivalence.

The conservative native-token guard checks only the target paragraph, so a correct identifier in a context formula cannot mask its loss in prose. It ignores LaTeX command names while retaining command arguments. It checks multiletter Latin occurrence counts; it can over-abstain on hyphenation and does not prove single-letter identity, primes, operators, punctuation, ordering, or semantic equivalence. Structural application is not semantic acceptance. The native fallback retains the original plain-text math limitations; the SEAL inline-math result remains unresolved.

`selfcheck.json` includes split identifiers in balanced markup, saved prior wrong output, context masking, occurrence loss, unknown/outside/duplicate scope, missing title evidence/characters, duplicate lines, altered code operators/indentation, and unsupported role override. Both working serializations are reconstructed byte-for-byte from the original provider snapshot and accepted proposals; untouched literal bytes/order and segment offsets are checked.

Read-only verification:

```sh
rtk docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python -B docs/research/pdf-core-g2-inline-boundary-2026-10-15/reinsertion/verify.py
```

No new inference, API call, dependency, production adapter, source-graph mutation, or general LaTeX parser was added by this lane. Independent semantic review is separate.
