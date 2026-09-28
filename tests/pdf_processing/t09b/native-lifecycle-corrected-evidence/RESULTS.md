# Corrected native trace lifecycle

PASS for the bounded diagnostic: readiness and final marker PUTs were observed;
the remote timeout/mc ownership was stopped and verified absent, and the local
reader stopped. Exit 143 is the expected targeted TERM. See result.json and the
sanitized traffic.jsonl. Marker objects remain under the unique recorded prefix.

This tests trace lifecycle, not PDF workflow or performance acceptance. The prior
failed diagnostic and its zombie caveat remain recorded separately.
