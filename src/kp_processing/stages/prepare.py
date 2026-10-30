"""prepare: validate the start input, read and verify the source, preflight, freeze the plan."""

import asyncio
import json
from contextlib import closing
from dataclasses import asdict
from typing import Any
from urllib.parse import urlsplit

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from docling.utils.locks import pypdfium2_lock

from kp_processing.methods.docling_parse.pipeline import IMAGES_SCALE
from kp_processing.ports.object_store import ObjectNotFound
from kp_processing.stages import Plan, Ports, PrepareInput, ProcessingFailure, Runtime, sha256


def _source_key(start: dict[str, Any]) -> str:
    invalid = ProcessingFailure(
        "platform", "configuration", "INVALID_START_INPUT", "Invalid workflow start input"
    )
    strings = (
        "request_id",
        "document_uid",
        "source_revision_id",
        "adopted_version",
        "initiator",
        "priority",
        "trace_id",
    )
    if (
        not isinstance(start, dict)
        or any(not isinstance(start.get(key), str) for key in strings)
        or type(start.get("adoption_sequence")) is not int
        or start["priority"] not in ("normal", "low")
        or not isinstance(start.get("files"), list)
        or len(start["files"]) != 1
    ):
        raise invalid
    file = start["files"][0]
    if (
        not isinstance(file, dict)
        or any(
            not isinstance(file.get(key), str)
            for key in ("path", "role", "custody_ref", "sha256", "media_type")
        )
        or type(file.get("size")) is not int
        or file["role"] != "main"
        or file["media_type"] != "application/pdf"
    ):
        raise invalid
    try:
        ref = urlsplit(file["custody_ref"])
    except ValueError as exc:
        raise invalid from exc
    if ref.scheme != "s3" or not ref.netloc or not ref.path[1:] or ref.query or ref.fragment:
        raise invalid
    return ref.path[1:]


def _check_limit(reason: str, actual: int | float, limit: int) -> None:
    if actual > limit:
        raise ProcessingFailure(
            "source",
            "source",
            reason,
            "Source exceeds the processing limit",
            metadata={
                "limit": str(limit),
                "actual": str(int(actual)) if actual == int(actual) else str(actual),
            },
        )


def _preflight(data: bytes, limits: dict[str, Any]) -> tuple[int, list[int]]:
    try:
        with pypdfium2_lock, pdfium.PdfDocument(data) as document:
            count = len(document)
            if count == 0:
                raise ProcessingFailure("source", "source", "CORRUPT_PDF", "PDF has no pages")
            _check_limit("PAGE_LIMIT_EXCEEDED", count, limits["max_pages"])
            no_text = []
            for index in range(count):
                with closing(document[index]) as page:
                    width, height = page.get_size()
                    pixels = width * height * IMAGES_SCALE**2  # as rendered, not in points
                    _check_limit("PIXEL_LIMIT_EXCEEDED", pixels, limits["max_page_pixels"])
                    with closing(page.get_textpage()) as text:
                        if text.count_chars() == 0:
                            no_text.append(index + 1)
            return count, no_text
    except pdfium.PdfiumError as exc:
        reason = (
            "PASSWORD_REQUIRED" if exc.err_code == pdfium_raw.FPDF_ERR_PASSWORD else "CORRUPT_PDF"
        )
        raise ProcessingFailure("source", "source", reason, "PDF cannot be opened or read") from exc


async def run(input: PrepareInput, ports: Ports, runtime: Runtime) -> Plan:
    """Checks, in this order, raising ProcessingFailure (cause, category, reason) on the first
    that fails:

    1. The start input has every admission spec §10 field with its JSON type, priority is
       normal or low, and files holds exactly one entry with role main and media_type
       application/pdf whose custody_ref is s3://{bucket}/{key}
       -> platform, configuration, INVALID_START_INPUT.
    2. adopted_version equals runtime.profile.profile
       -> platform, integrity, ADOPTED_VERSION_MISMATCH.
    3. The declared size is at most runtime preflight.max_bytes
       -> source, source, SIZE_LIMIT_EXCEEDED.
    4. The object at {key} exists -> else platform, integrity, SOURCE_NOT_FOUND; its bytes
       match the declared sha256 and size -> else platform, integrity, SOURCE_DIGEST_MISMATCH.
    5. The PDF opens without a password -> else source, source, PASSWORD_REQUIRED; it opens
       at all and has at least one page -> else source, source, CORRUPT_PDF.
    6. Page count at most preflight.max_pages -> else source, source, PAGE_LIMIT_EXCEEDED.
    7. Every page, rendered at the parser's images scale (points x IMAGES_SCALE squared), has
       at most preflight.max_page_pixels -> else source, source, PIXEL_LIMIT_EXCEEDED.

    Source failures are not retryable; metadata carries "limit" and "actual" for 3, 6 and 7.
    On success, splits the pages into groups of runtime parse_group_pages, lists the pages
    whose text layer has no characters, writes the plan as JSON to
    requests/{request_id}/attempts/{run_id}/plan.json (write-once) and returns it.
    """
    start = input.start
    key = _source_key(start)
    if start["adopted_version"] != runtime.profile.profile:
        raise ProcessingFailure(
            "platform",
            "integrity",
            "ADOPTED_VERSION_MISMATCH",
            "Adopted profile differs from worker",
        )
    file = start["files"][0]
    limits = runtime.profile.runtime["preflight"]
    _check_limit("SIZE_LIMIT_EXCEEDED", file["size"], limits["max_bytes"])
    try:
        data = await ports.store.get(key)
    except ObjectNotFound as exc:
        raise ProcessingFailure(
            "platform", "integrity", "SOURCE_NOT_FOUND", "Source object is absent"
        ) from exc
    if sha256(data) != file["sha256"] or len(data) != file["size"]:
        raise ProcessingFailure(
            "platform",
            "integrity",
            "SOURCE_DIGEST_MISMATCH",
            "Source bytes differ from declaration",
        )
    count, no_text = await asyncio.to_thread(_preflight, data, limits)
    group_size = runtime.profile.runtime["parse_group_pages"]
    plan = Plan(
        source_key=key,
        source_sha256=file["sha256"],
        page_count=count,
        groups=[
            [first, min(first + group_size - 1, count)] for first in range(1, count + 1, group_size)
        ],
        no_text_layer_pages=no_text,
        ref=f"requests/{start['request_id']}/attempts/{input.run_id}/plan.json",
    )
    encoded = json.dumps(asdict(plan), sort_keys=True, separators=(",", ":")).encode()
    if not await ports.store.put_if_absent(plan.ref, encoded):
        return Plan(**json.loads(await ports.store.get(plan.ref)))
    return plan
