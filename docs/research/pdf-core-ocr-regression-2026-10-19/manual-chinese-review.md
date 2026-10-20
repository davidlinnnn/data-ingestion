# Chinese source-page adjudication

Reviewed all source-native text units on three frozen regression pages. Source
PNGs and region references were visually inspected before inference. Review now
compares exact saved candidate text and source coordinates. Screenshot interior
text remains outside the frozen accuracy scope. No reference or output was
edited. `manual-chinese-review.json` records every unit, exact output DocItem IDs,
source/output bounding boxes and output hashes.

## R0 versus R1

The three Chinese pages have byte-identical `document.json`, `document.md` and
`cells.json` between R0 and R1. There is no Chinese regression or improvement
from disabling the line direction classifier on these three inputs.

| Page | Full body/headings | Minor differences | Meaningful remaining caveat |
| --- | --- | --- | --- |
| ndhu-p7 | All body instructions and both captions retained; URL and `/User/Login` identifiers intact | Caption 注意→註意; duplicated list number 3 in Markdown; missing small figure callout 6 | None in body prose under this scope |
| ndhu-p9 | All numbered instructions and explanatory note retained | Parenthesis/spacing variants | ※ markers disappear from two menu targets and the explanatory note, losing the authenticated-only function linkage |
| nccu-p3 | All body prose, title and subsection retained; menu identifiers B and B5A intact | Enumerator 一 and heading punctuation omitted; delimiter positioning/spacing | None in body prose under this scope |

The ndhu-p9 marker loss is baseline-inherited and should not be presented as a
new R1 regression. It is still material source structure: `註：標記※代表此功能僅提供給登入使用者使用。`
becomes `註：標記代表此功能僅提供給登入使用者使用。`, while the corresponding
`【※登入帳號顯示／資料維護】` and `【登入／※登出】` also lose ※. The individual
prose survives, but the explanatory rule no longer identifies its targets.
This is a semantic linkage caveat, not a claim that most text is missing.

## Score flags resolved manually

- ndhu-p7 U04: exact critical-caption matching flags 注意→註意. The complete
  caption exists at `#/texts/16`; this is a minor character variant, not a lost
  caption or changed warning condition.
- ndhu-p7 U01: the reference groups three spatially separate callouts 3, 4, 5.
  `#/texts/4`, `#/texts/7`, `#/texts/10` retain each at the correct location.
  Requiring a contiguous `345` substring creates a false positive.
- ndhu-p7 U03: the native source callout 6 is actually absent at its source
  position. A different 6 elsewhere in the document makes global short-string
  matching look successful. This is a false negative, classified here as a small
  figure annotation omission; the full body step 6 survives.
- ndhu-p9: the scorer removes non-alphanumeric ※, so it does not flag the
  authenticated-only marker relationship loss. High coverage cannot establish
  semantic acceptance.

## T1 corrected complete outputs

Reviewed the corrected, completed T1 artifacts. The initial invalid TSV/config
attempt is not treated as an accuracy result; root retains its failure and the
environment correction separately.

| Page | Source-grounded finding | Comparison with R0/R1 |
| --- | --- | --- |
| ndhu-p7 | `https://iss.yuntech.edu.tw` becomes `https://iss.yunteeh.edu.tw`; the login URL becomes `https://iss.vuntech.edu.tw/User/Login` (`#/texts/83`, `#/texts/84`) | Two new material identifier errors; R0/R1 preserved both addresses |
| ndhu-p9 | Complete explanatory note `註：標記※代表此功能僅提供給登入使用者使用。` becomes `註 : PREZ IK AR He dE) HE ETRE RR BR` (`#/texts/9`) | New whole-note corruption; R0/R1 retained the note prose even though the ※ relationship was already broken |
| nccu-p3 | `壹、登入方法` becomes `Be. 登入 方法` (`#/texts/0`) | New section-enumerator corruption; the title words 登入方法 remain, so the automatic whole-heading omission flag overstates the damage |

T1 improves caption 注意 on ndhu-p7 and retains the two target ※ markers on
ndhu-p9. Those improvements do not compensate for changed URL destinations and
the unreadable condition note. Remaining body instructions and the B/B5A menu
identifiers on nccu-p3 are retained. Additional minor defects include missing or
garbled list numbers, lost page-number furniture, missing figure callouts and
spacing/punctuation variants.

No new Chinese-page regression was found for R1. T1 has new material content
errors and is unsuitable as the replacement Chinese OCR configuration under the
current criteria. R0/R1 still have the baseline semantic marker linkage caveat;
they are not declared globally qualified from this small suite.

No candidate has been accepted on coverage scores alone. Screenshot interior,
formula fidelity, natural scan degradation and downstream reading order remain
outside this review.
