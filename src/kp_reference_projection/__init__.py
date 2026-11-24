"""The reference projection (#127): a Retrieval-shaped projection that follows the Change Feed,
keeps each Document's whole Canonical Markdown in its own PostgreSQL store and reports what it
serves (canonical consumption DR §2 A3, A7, A9, §4, §5; admission spec §7.4). It shows a
projection owner the protocol and lets the pilot test the handoff; product quality is not a
goal. It lives in the pilot only: in PROD the real Retrieval owner replaces it (user ruling
2026-11-24).

It talks to the platform through kp_sdk.projection only, over HTTP; it imports nothing of the
platform's packages.
"""

from pathlib import Path
from typing import LiteralString, cast

SCHEMA = cast(LiteralString, (Path(__file__).parent / "schema.sql").read_text())
