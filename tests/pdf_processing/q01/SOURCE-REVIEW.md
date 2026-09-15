# Q01 collateral review

Reviewed the exact source PDF SHA-256
`b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980`,
rendered locally on 2026-09-15. Rendered source pages 3–6 and 8–9 were inspected
alongside the original pinned checkpoint elements. All handoff input hashes matched;
`replay.load()` additionally checks the original R2 checkpoint, package and upstream
predictor manifest. Private source images are in `/private/tmp/q01-source-review/`.
These source IDs are test evidence, never production selection rules.

| Historical root → target | Source observation | Q01 disposition |
| --- | --- | --- |
| `#/3/0` → `#/4/14` | Paragraph above a figure continues on the next page; the target is the later margin heading beside another section. | Remove false join. Its real successor remains separate; figure-interrupted continuation is outside this bounded rule. |
| `#/3/36` → `#/3/37` | Adjacent fragments on the same algorithm line. | Preserve upstream inline chain; reject candidate removal. |
| `#/3/36` → `#/3/38` | Next fragment on that same line, after the preceding target. | Preserve upstream inline chain; reject candidate removal. |
| `#/3/36` → `#/3/39` | Next fragment on that same line. | Preserve upstream inline chain; reject candidate removal. |
| `#/4/2` → `#/5/10` | Prose precedes a new page whose entrance contains a boxed algorithm; the target is that algorithm's header. Actual prose resumes below two figures. | Remove false join; preserve separate source items. Do not jump across the container. |
| `#/5/0` → `#/6/14` | Prose at the page bottom continues at the next page's body entrance; target is a margin label much farther down. | Remove false join. |
| `#/8/4` → `#/9/11` | Prose resumes below the next page's boxed algorithm; target is a margin label beside that prose. | Remove false join; container-interrupted continuation stays separate. |
| Added `#/5/0` → `#/6/6` | Source-reviewed next-page body paragraph completes the preceding paragraph. | Accept corrected join with exact source regions. |

The resulting delta is four removals and one addition, versus the candidate's
seven removals and one addition. The historical candidate and corrected role/order
oracle are preserved under `evidence/`, with Git object references and SHA-256 hashes.
They retain their original bounded claims; Q01 does not adopt the algorithm helper.

## Bounded policy decision

Use the candidate's conservative page-edge, width and alignment thresholds only
for the explicitly selected `column-edge-continuation-v1` method. They describe a
bounded heuristic, not a universal document contract. Preserve upstream joins
between horizontally adjacent, vertically overlapping same-page fragments. Reject
overlapping alternative entrances as well as exact ties, multiple owners and
intervening body/header/container regions at the destination and later content
in the source column. Uppercase successors remain valid.

The table/picture comparison initially failed on renumbered caption references.
Resolving those references to their unchanged text/type/provenance confirms equal
payloads. Full child-graph equivalence, figure-interrupted continuation, shifted
columns, short terminal fragments and all-fixture qualification remain unclaimed.
