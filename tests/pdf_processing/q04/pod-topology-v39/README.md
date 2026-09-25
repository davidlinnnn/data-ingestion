# AN native method-invalidation window

This immutable, single-run adapter follows the incomplete AM window. AM reused a warm parser across two different methods and failed before method-off processing. AN inserts an attributed worker generation boundary after fresh, preserving the existing 250 ms sampling and 1 s maximum transition gap. It retains the frozen v3 source/oracle, one native fixture, `fresh → invalidation → replay`, 20-request parser budget per generation, unchanged resource gates, and fail-stop execution. Use the reviewed `RUNNER-MANIFEST.json` and `--offline-check` before any execution; do not rerun this identity.

The first and only AN runtime passed the bounded method-invalidation gate. See [results](first-window-evidence/RESULTS.md). Historical A–AM evidence remains separate.
