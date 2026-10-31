# Coding standards

Judgement calls for writing and reviewing code in this repo. Mechanical rules live in
tooling: ruff and pyright (`pyproject.toml`) and `scripts/check-docs`.

## Language

Write code, identifiers, comments, docstrings, test names and log messages in English.
Refer to tickets and spec sections by number (`#129`) rather than by their titles.

## Vocabulary

Name things with the terms in `CONTEXT.md` (Processing Profile, Enrichment Method,
Processing Result, Enrichment Status, …), so code, docs and tickets share one language.

## Ports and tests

- Each external dependency (object store, admission, inference services, clock) sits
  behind a port: a `Protocol`, an in-process fake and the real adapter. The fake and the
  adapter pass one shared contract test.
- Tests observe behaviour at a seam: given inputs and port state, assert what was
  registered, returned or reported. Exercise the real library (docling, RapidOCR, boto3
  against the S3 stand-in) or swap a whole port for its fake.
- Mark tests that need Docker or a local socket (`s3`, `network`), so the Codex
  sandbox can deselect them.

## Comments and contracts

- A comment states, in one line, a why the code cannot show.
- A contract (docstring, port, schema) states obligations and observable semantics only.
  The spec names the extension points that are required, such as #108's insertion
  points; everything else waits for a ticket that asks for it.

## Temporal workers

- A worker's Activity slots match what its process can run at once. Work that holds a
  process-wide resource (a model, a lock, a GPU) gets its own task queue and a worker with
  that many slots, so waiting work stays visible in Temporal as backlog.

## Validation evidence

- Check each acceptance criterion as a range with a lower bound (0 <= t <= limit), so a
  broken measurement fails instead of passing. Convert external timestamps with an
  explicit UTC zone.
- Pair a "never happens" claim with a negative control that shows the measurement can see it.
