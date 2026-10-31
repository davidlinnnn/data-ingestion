"""Helpers for stage tests; the ports and runtime fixtures live in tests/conftest.py."""

import dataclasses
import hashlib
from typing import Any

from kp_processing.stages import Ports, Runtime


def with_runtime(runtime: Runtime, **overrides: Any) -> Runtime:
    """The runtime with some profile runtime parameters replaced."""
    profile = dataclasses.replace(runtime.profile, runtime={**runtime.profile.runtime, **overrides})
    return dataclasses.replace(runtime, profile=profile)


async def start_input(
    ports: Ports, pdf: bytes, request_id: str = "req_1", **overrides: Any
) -> dict[str, Any]:
    """Put the PDF into the stand-in custody and return a §10 start input pointing at it."""
    sha = hashlib.sha256(pdf).hexdigest()
    await ports.store.put_if_absent(f"custody/{sha}", pdf)
    start = {
        "request_id": request_id,
        "document_uid": "doc_1",
        "source_revision_id": "srv_1",
        "files": [
            {
                "path": "paper.pdf",
                "role": "main",
                "custody_ref": f"s3://kp-dev/custody/{sha}",
                "sha256": sha,
                "size": len(pdf),
                "media_type": "application/pdf",
            }
        ],
        "adopted_version": "paper-pdf@1",
        "adoption_sequence": 1,
        "initiator": "source",
        "priority": "normal",
        "trace_id": "4bf92f3577b34da6",
    }
    return {**start, **overrides}
