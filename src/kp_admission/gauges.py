"""Gauges the admission CronJobs measure and the api exports (#98). A job's pod ends with its run,
so each run writes its values to job_gauge and the api's observe loop sets them, the pattern of
#261's adoption gauges. Every gauge has one label."""

from prometheus_client import Gauge
from psycopg import AsyncConnection

_SPECS = (
    (
        "kp_admission_deletions_unenforced",
        "deletions applied more than 10 minutes ago and not enforced, by why: held (a Build"
        " still holds the Document), liveness or writes_lost (the judgment is suspended)",
        "reason",
    ),
    (
        "kp_admission_documents_on_withdrawn",
        "live Documents whose current Canonical Revision a withdrawn version made",
        "version",
    ),
    (
        "kp_admission_documents_without_current",
        "live Documents created more than an hour ago with no current Canonical Revision",
        "source_id",
    ),
    (
        "kp_admission_requests_overdue",
        "process requests dispatched more than an hour ago and still queued or processing",
        "adopted_version",
    ),
    (
        "kp_admission_reruns_retrying",
        "latest Source Revisions with at least the warning count of retryable failures under"
        " the adoption, by the last failure's reason; the scan keeps retrying them",
        "reason",
    ),
    (
        "kp_admission_reruns_stopped",
        "latest Source Revisions the scan does not reopen until the next adoption, by the"
        " last request's reason: a non-retryable failure, a rejection or NO_CANDIDATE",
        "reason",
    ),
    (
        "kp_admission_job_last_run_timestamp_seconds",
        "when each admission CronJob (enforce, scan) last finished a run, Unix time",
        "job",
    ),
)
GAUGES = {name: Gauge(name, doc, [label]) for name, doc, label in _SPECS}
_shown: dict[str, set[str]] = {name: set() for name in GAUGES}


async def record(conn: AsyncConnection, job: str, values: dict[str, dict[str, float]]) -> None:
    """Replaces the values of each gauge in `values`, label value to value, and marks the run of
    `job`, in one transaction."""
    async with conn.transaction():
        await conn.execute("DELETE FROM job_gauge WHERE name = ANY(%s)", (list(values),))
        for name, by_label in values.items():
            for label, value in by_label.items():
                await conn.execute(
                    "INSERT INTO job_gauge (name, label, value) VALUES (%s, %s, %s)",
                    (name, label, value),
                )
        await conn.execute(
            "INSERT INTO job_gauge (name, label, value)"
            " VALUES ('kp_admission_job_last_run_timestamp_seconds', %s, extract(epoch FROM now()))"
            " ON CONFLICT (name, label) DO UPDATE SET value = EXCLUDED.value",
            (job,),
        )


async def observe(conn: AsyncConnection) -> None:
    """Sets the gauges from the jobs' last runs. A label a run no longer wrote is removed after
    the new values are set, so a scrape never reads a gauge missing."""
    rows = await (await conn.execute("SELECT name, label, value FROM job_gauge")).fetchall()
    found: dict[str, dict[str, float]] = {name: {} for name in GAUGES}
    for name, label, value in rows:
        if name in found:
            found[name][label] = value
    for name, gauge in GAUGES.items():
        for label, value in found[name].items():
            gauge.labels(label).set(value)
        for label in _shown[name] - found[name].keys():
            gauge.remove(label)
        _shown[name] = set(found[name])
