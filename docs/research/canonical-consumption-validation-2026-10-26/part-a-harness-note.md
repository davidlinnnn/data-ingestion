An initial trial used SELECT xid::text with unqualified ORDER BY xid. PostgreSQL resolved the output-column name, so that ordered xid text lexicographically. This was a harness error, not the requested xid8 ordering. Those trials are preserved as invalid-part-a-* and excluded from the result table. The corrected SQL qualifies ORDER BY feed.xid, feed.seq, and records an explicit monotonicity check.

A restart raced PostgreSQL startup and failed before any transactions with:

```text
psycopg.OperationalError: connection failed: connection to server at "127.0.0.1", port 55455 failed: server closed the connection unexpectedly
    This probably means the server terminated abnormally
    before or while processing the request.
```

The subsequent successful run waited for readiness. `run_part_a.sh` checks TCP readiness explicitly (`pg_isready -h 127.0.0.1`) to avoid treating the entrypoint's temporary Unix-socket-only initialization server as ready. This startup attempt is not one of the result-table runs.
