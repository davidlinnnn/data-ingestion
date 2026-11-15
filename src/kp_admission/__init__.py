"""The admission core (#95): admission records on PostgreSQL, the outbox and the dispatcher that
starts canonical processing on Temporal (admission spec §3, §9, §10)."""

from pathlib import Path
from typing import LiteralString, cast

# A file shipped with the package, not input, so psycopg may run it as written.
SCHEMA = cast(LiteralString, (Path(__file__).parent / "schema.sql").read_text())
