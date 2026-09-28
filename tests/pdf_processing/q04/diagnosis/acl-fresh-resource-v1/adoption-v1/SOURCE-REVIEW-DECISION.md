# Fixture 09 Option A adoption decision

Status: **ADOPTED FOR THE NEXT FIXED-FIXTURE QUALIFICATION ONLY**

The source review accepts the candidate representation for the fixed fixture 09
PDF bytes `bd33fffb2c91f35225f5b89feb29a93013f4814558ac578bef000b632fd169bf`.
The accepted delta is exactly one text node split into two adjacent text nodes.
The fragments preserve order, parent, label, concatenated text and the two source
regions after rebasing the second charspan. Later references increase by one.
The relational proof leaves no other graph delta.

The adopted reference retains exact graph comparison, all six formulas, equation
2 as `TextItem`, both required OCR outcomes, both captions, source provenance and
the complete graph. The quality oracle contains 40, 69 and 21 items for processed
pages 1, 2 and 3 (original pages 2, 3 and 4).

This decision does not define a general split normalization, expand continuation
behavior, change the canonical schema, change production processing, or make a
general PDF quality claim. The historical candidate package remains
`NOT_ACCEPTED` as a record of its pre-decision state. Historical runtime FAILs and
raw evidence also remain unchanged. A new bundle records this independent
decision; runtime acceptance still requires a fresh/restored/exact-replay pass.

Old requests remain bound to their original profile, bundle, run ID and object
prefix. The new qualification prefix starts empty and receives no copied
registration. Therefore old-request verification belongs to the original store;
the new run's restored case is a new request for its fresh artifact, and exact
replay reuses that new request.
