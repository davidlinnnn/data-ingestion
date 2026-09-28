# YOLO fixture-local equivalence candidate

This candidate packages the two source-reviewed, table-interrupted paragraph
splits from `yolo-lifecycle-a`. It is **pending main approval**, is not wired to
the runtime consumer, and has no acceptance effect.

[`BUNDLE.json`](BUNDLE.json) binds the exact fixture 07 source, candidate inputs,
historical method evidence and payload, continuation method, historical graph,
candidate graph, and four reviewed source fragments. The independent
[`yolo_equivalence_candidate.py`](../yolo_equivalence_candidate.py) validator
also checks parent, provenance, reading order, and the intervening table/header
sequence. Because the complete candidate graph hash is fixed, any other graph,
table, picture, caption, text, or relationship change is rejected.

The retained candidate validation is in
[`evidence/validation.json`](evidence/validation.json). Its
`runtime_active=false`, `runtime_accepted=false`, and `acceptance_effect=none`
fields are part of the contract. Activating it requires a separate reviewed
integration after main approves this exact bundle and after the independent
resource gate passes. The historical reference and `FAIL_GRAPH_GATE` record
remain unchanged.
