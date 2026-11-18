"""The adoption record (admission spec §3): which Processing Profile version a new process request
runs, by the media type of its main file, and the adoption sequence it carries (§10).

One sequence counts every adoption of the deployment, so it rises for every Source at each
adoption: in the pilot no Source pins a version, and current-revision selection compares the
sequences of one document only. Adopting a version supersedes the one adopted before for that
media type; cancelling the adopted version leaves none, with no fall back to an earlier one.
Neither opens a refresh request (#98 does).
"""

import psycopg
from psycopg import AsyncConnection

_LATEST = """
SELECT adopted_version, sequence, cancelled_at IS NULL FROM adoption
WHERE media_type = %s ORDER BY sequence DESC LIMIT 1 FOR SHARE
"""


async def current(conn: AsyncConnection, media_type: str) -> tuple[str, int] | None:
    """(adopted_version, adoption_sequence) for `media_type`, or None when none is adopted. In a
    transaction its row stays locked until the end, so a cancel waits for the requests made under
    it and none is made under a version after its cancel returns."""
    row = await (await conn.execute(_LATEST, (media_type,))).fetchone()
    return (row[0], row[1]) if row and row[2] else None


async def adopt(conn: AsyncConnection, *, tenant_id: str, media_type: str, version: str) -> int:
    """Adopts `version` for `media_type` and returns its adoption sequence. The version adopted
    already keeps its sequence."""
    while True:
        if (found := await current(conn, media_type)) and found[0] == version:
            return found[1]
        try:
            row = await (
                await conn.execute(
                    "INSERT INTO adoption (sequence, tenant_id, media_type, adopted_version)"
                    " SELECT coalesce(max(sequence), 0) + 1, %s, %s, %s FROM adoption"
                    " RETURNING sequence",
                    (tenant_id, media_type, version),
                )
            ).fetchone()
            assert row
            return row[0]
        except psycopg.errors.UniqueViolation:
            pass  # a concurrent adoption took the sequence: count again


async def cancel(conn: AsyncConnection, *, media_type: str, version: str) -> bool:
    """Cancels the adoption of `version` for `media_type` when it is the adopted one; False when
    it is not."""
    cursor = await conn.execute(
        "UPDATE adoption SET cancelled_at = now() WHERE sequence = ("
        " SELECT max(sequence) FROM adoption WHERE media_type = %s)"
        " AND adopted_version = %s AND cancelled_at IS NULL",
        (media_type, version),
    )
    return cursor.rowcount == 1
