# AIMA source-reviewed oracle v2 — frozen before candidate implementation

Accepted design SHA-256: 987d3fa25a88adf64815b5d65434a6e87d299da771abca47d4fa29d3d7e7430a.
Reviewed 2026-09-15 against rendered contiguous source pages 3, 5, 6, 9, 10
(original PDF pages 101, 103, 104, 107, 108; printed 82, 84, 85, 88, 89).
Processed source SHA-256: b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980.
Original source SHA-256: 0609d012bf123d210c3587d1c1610074f5079217a996299123a2f7872f28a8e9.

This is test/source review, never input to candidate derivation. Coordinates below
are top-left PDF points, deliberately enclosing the visibly boxed algorithms and
captions. Content expectations come from the previously source-audited transcript
(`/private/tmp/t09a-code-oracle.json`, hashes in historical code-source-oracle.json),
not a corrected parser output. Historical v1 RED remains unchanged.

| Page | Header anchor | Algorithm region [l,t,r,b] | Caption anchor | Caption region |
| --- | --- | --- | --- | --- |
| 3 | function BREADTH-FIRST-SEARCH | [110,80,475,255] | Figure 3.11 | [120,270,495,286] |
| 5 | function UNIFORM-COST-SEARCH | [110,80,475,267] | Figure 3.14 | [120,280,495,346] |
| 9 | function DEPTH-LIMITED-SEARCH | [110,80,475,247] | Figure 3.17 | [120,260,495,278] |
| 10 | function ITERATIVE-DEEPENING-SEARCH | [110,90,475,142] | Figure 3.18 | [120,155,495,197] |

Required: exact header span, all body fragments in source order, and full caption
membership linked to that algorithm, irrespective of item type/count. Embedded
headers exclude preceding prose. Each member has exact result/item/text-range and
source-region references. Whitespace-only sequence comparison is allowed; semantic
symbols cannot be deleted or normalized. Depth-limited includes its recursive
function in the body. Isolated U+0338 remains a separate source-linked uncertain
fragment: native U+0007 versus combining slash extraction is not mathematical
equivalence and must be reported locally. Structural resolution remains mandatory.

Continuation: the final prose paragraph on page 5 (region [100,568,510,650], ending
`second path`) continues into page 6's first body paragraph (region
[100,65,510,108], beginning `to Bucharest with cost`). The margin label at
[35,438,75,456] is excluded. Correct ordered source-linked separate members with
an explicit continuation edge pass; one merged item is not mandatory. Content
and regions must survive unchanged. Selection anchors are test-only.

Missing/wrong/dangling/wrong-result relationships and missing content/order are
FAIL, not permitted unknown. Local symbol uncertainty can coexist with correct
structure when exact raw text and readable source evidence are preserved.
This oracle qualifies only these five relationships, never complete discovery.

Pre-evaluation coordinate erratum: the initial page-10 rectangles were too high/short.
Source-page measurement corrected them to the values above before implementing or
scoring relationships. Initial document hash e4160ce903d9bf5bb4444434974abdf7fe936c50658a3308ea59be3ee6388d82 is retained here for audit.
