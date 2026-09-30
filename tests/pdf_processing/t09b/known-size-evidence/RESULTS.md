# Known-size MinIO accounting probe

2026-09-28: two fresh retained objects, 16 and 4096 bytes, written once and read
back exactly. No PDF workload or Deployment mutation. Object Pod UID:
`b61dcfc5-3eef-45a3-bf4d-79135c8b456d`. Prefix and sanitized observations are in
result.json; executed-probe.py preserves the exact one-shot command driver.

The 20-second native verbose trace ended via timeout (exit 124). It captured ten
matching calls: multipart-init POST, part PUT, complete POST, HEAD and GET for
each object. GET tx values were exactly 16 and 4096. PUT rx values were 333 and
4415, demonstrating that rx is not simply logical object size for this client.
All ten observed calls returned HTTP 200. Raw headers, query strings and bodies
were discarded; only scoped accounting fields are retained.

This demonstrates the native measurement source works for this bounded mc
sequence. It does not establish boto3 transport accounting, packet bytes, trace
loss detection or complete coverage under interruption. The different upload
shape must not be silently treated as the worker's put_object path. Duration
units remain unqualified. Both diagnostic objects remain retained.

Earlier missing-object probes returned no records with their nonverbose/path
filters; the unfiltered verbose schema probe succeeded. Those empty observations
were never counted as zero traffic or workload success.
