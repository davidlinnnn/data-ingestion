"""Does the Change Feed hand out positions again after a point-in-time restore? (#57 §7.2)

Runs kp_admission's schema and feed module on PostgreSQL 17 in Docker: a base backup, events
before a restore point T, events after it that a projection reads (its cursor is then stale),
recovery from the backup and the archived WAL up to T, then new events. Writes evidence.json.

    uv run python docs/validation/57/restore_feed_positions.py
"""

import asyncio
import json
import socket
import subprocess
import time
from pathlib import Path

from psycopg import AsyncConnection

from kp_admission import SCHEMA, feed

IMAGE = "postgres:17.10-alpine"  # the image the test suite uses
PORT = 55457
URL = f"postgresql://postgres@127.0.0.1:{PORT}/"
A, B = "kp57-restore-a", "kp57-restore-b"
VOLUMES = ("kp57-archive", "kp57-backup", "kp57-data-b")
OTHER_WRITES = 3  # non-feed write transactions between two feed events, before and after T
EVENT = {"tenant_id": "t", "source_id": "s", "priority": "normal"}


def sh(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def cleanup() -> None:
    subprocess.run(["docker", "rm", "-f", A, B], capture_output=True)
    subprocess.run(["docker", "volume", "rm", "-f", *VOLUMES], capture_output=True)


async def connect(database: str) -> AsyncConnection:
    for _ in range(120):
        try:
            return await AsyncConnection.connect(URL + database, autocommit=True)
        except Exception:
            await asyncio.sleep(0.5)
    raise RuntimeError("PostgreSQL did not come up")


async def event(conn: AsyncConnection, uid: str) -> str:
    """One feed event in its own transaction, then OTHER_WRITES transactions that write elsewhere."""
    async with conn.transaction():
        position = await feed.append(conn, "current_revision_changed", document_uid=uid, **EVENT)
    for _ in range(OTHER_WRITES):
        await conn.execute("INSERT INTO other_writes DEFAULT VALUES")
    return position


async def read_all(conn: AsyncConnection, cursor: str) -> list[str]:
    events, _ = await feed.read(conn, cursor, 1000)
    return [e.document_uid or "" for e in events]


async def report(conn: AsyncConnection, position: str) -> str:
    try:
        await feed.report_cursor(conn, "projection", position)
    except (ValueError, feed.Backwards) as error:
        return f"{type(error).__name__}: {error}"
    return "accepted"


async def scalar(conn: AsyncConnection, query: str) -> str:
    [(value,)] = await (await conn.execute(query)).fetchall()
    return str(value)


async def run(lost_count: int, writes_first: int = 0) -> dict:
    cleanup()
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            raise RuntimeError(f"port {PORT} is in use")
    mounts = ("-v", "kp57-archive:/archive", "-v", "kp57-backup:/backup")
    sh("docker", "run", "--rm", *mounts, IMAGE, "chown", "postgres:postgres", "/archive", "/backup")
    sh("docker", "run", "-d", "--name", A, "-p", f"127.0.0.1:{PORT}:5432", *mounts,
       "-e", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE,
       "-c", "archive_mode=on", "-c", "archive_command=cp %p /archive/%f")  # fmt: skip
    admin = await connect("postgres")
    await admin.execute("CREATE DATABASE kp")
    conn = await connect("kp")
    await conn.execute(SCHEMA)
    await conn.execute("CREATE TABLE other_writes (id bigserial PRIMARY KEY)")
    sh("docker", "exec", "-u", "postgres", A, "pg_basebackup", "-D", "/backup/base", "-c", "fast")

    # Before T: three events, read and reported by the projection.
    start = await feed.head(conn)
    before = [await event(conn, f"before-{i}") for i in range(3)]
    assert await read_all(conn, start) == [f"before-{i}" for i in range(3)]
    cursor_t = before[-1]
    assert await report(conn, cursor_t) == "accepted"
    await conn.execute("SELECT pg_create_restore_point('T')")
    seq_at_t = await scalar(conn, "SELECT last_value FROM change_feed_seq")

    # After T: events the restore will lose. The projection reads them, so its cursor is stale.
    lost = [await event(conn, f"lost-{i}") for i in range(lost_count)]
    control = await read_all(conn, cursor_t)  # harness control: no restore, new events are read
    assert control == [f"lost-{i}" for i in range(lost_count)], control
    stale = lost[-1]
    assert await report(conn, stale) == "accepted"
    segment = await scalar(conn, "SELECT pg_walfile_name(pg_switch_wal())")
    while await scalar(conn, "SELECT coalesce(last_archived_wal, '') FROM pg_stat_archiver") < segment:
        await asyncio.sleep(0.2)
    await conn.close()
    await admin.close()
    sh("docker", "stop", A)

    # Restore: the base backup, then archived WAL up to T, on a new data directory.
    sh("docker", "run", "--rm", "-v", "kp57-backup:/backup", "-v", "kp57-data-b:/data", IMAGE, "sh", "-c",
       "cp -a /backup/base/. /data/ && touch /data/recovery.signal && chmod 700 /data"
       " && printf \"restore_command = 'cp /archive/%%f %%p'\\nrecovery_target_name = 'T'\\n"
       "recovery_target_action = 'promote'\\n\" >> /data/postgresql.auto.conf"
       " && chown -R postgres:postgres /data")  # fmt: skip
    sh("docker", "run", "-d", "--name", B, "-p", f"127.0.0.1:{PORT}:5432",
       "-v", "kp57-archive:/archive", "-v", "kp57-data-b:/var/lib/postgresql/data",
       "-e", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE)  # fmt: skip
    conn = await connect("kp")
    while await scalar(conn, "SELECT pg_is_in_recovery()") == "True":
        await asyncio.sleep(0.2)
    assert await read_all(conn, start) == [f"before-{i}" for i in range(3)]  # the lost ones are gone
    for _ in range(writes_first):  # other transactions that commit before the first new event
        await conn.execute("INSERT INTO other_writes DEFAULT VALUES")
    result = {
        "lost_events": lost_count,
        "other_writes_before_the_first_new_event": writes_first,
        "cursor_at_t": cursor_t,
        "stale_cursor": stale,
        "sequence_at_t": seq_at_t,
        "sequence_after_restore": await scalar(conn, "SELECT last_value FROM change_feed_seq"),
        "recorded_cursor_after_restore": await scalar(conn, "SELECT position FROM consumer_cursor"),
        "report_stale_right_after_restore": await report(conn, stale),
        "read_stale_right_after_restore": await read_all(conn, stale),
    }

    # New events, in the same pattern, until the stale cursor is handed one (or 400 were tried).
    new: list[str] = []
    report_accepted_after = None
    seen: list[str] = []
    while not seen and len(new) < 400:
        new.append(await event(conn, f"new-{len(new)}"))
        seen = await read_all(conn, stale)
        if report_accepted_after is None and await report(conn, stale) == "accepted":
            report_accepted_after = len(new)
    rewound = await read_all(conn, cursor_t)  # fix control: the cursor rewound to T
    assert rewound == [f"new-{i}" for i in range(len(new))], rewound
    first_seen = int(seen[0].removeprefix("new-")) if seen else None
    result |= {
        "new_events_appended": len(new),
        "new_events_at_or_before_stale_cursor": sum(p <= stale for p in new),
        "new_events_skipped_by_stale_cursor": first_seen if seen else len(new),
        "first_new_event_the_stale_cursor_is_handed": seen[0] if seen else None,
        "stale_cursor_read_ever_raised": False,  # read_all above would have raised
        "report_stale_accepted_after_new_events": report_accepted_after,
        "read_from_cursor_at_t_returns_all_new_events": True,
        "positions_shared_by_a_lost_and_a_new_event": sorted(set(lost) & set(new)),
        "first_lost_positions": lost[:3],
        "first_new_positions": new[:3],
    }
    await conn.close()
    cleanup()
    return result


async def main() -> None:
    started = time.monotonic()
    # The third run offsets the transaction counter by the sequence's jump (30 values, 4 ids each).
    runs = [await run(5), await run(40), await run(40, writes_first=120)]
    for r in runs:
        # Reuse and skip: the claims of §7.2. A failure here refutes them.
        assert r["new_events_at_or_before_stale_cursor"] > 0, "no position was reused"
        assert r["read_stale_right_after_restore"] == [], "read handed the stale cursor an event"
        assert r["new_events_skipped_by_stale_cursor"] > 0, "nothing was skipped"
    image = sh("docker", "image", "inspect", IMAGE, "--format", "{{index .RepoDigests 0}}")
    evidence = {"image": image, "other_writes_between_events": OTHER_WRITES, "runs": runs}
    Path(__file__).with_name("evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    print(f"reuse and skip reproduced in {len(runs)} runs, {time.monotonic() - started:.0f} s")


if __name__ == "__main__":
    asyncio.run(main())
