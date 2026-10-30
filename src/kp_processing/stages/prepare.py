"""prepare: validate the start input, read and verify the source, preflight, freeze the plan."""

from kp_processing.stages import Plan, Ports, PrepareInput, Runtime


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
    7. Every page's width x height in points (72 dpi pixels) is at most
       preflight.max_page_pixels -> else source, source, PIXEL_LIMIT_EXCEEDED.

    Source failures are not retryable; metadata carries "limit" and "actual" for 3, 6 and 7.
    On success, splits the pages into groups of runtime parse_group_pages, lists the pages
    whose text layer has no characters, writes the plan as JSON to
    requests/{request_id}/attempts/{run_id}/plan.json (write-once) and returns it.
    """
    raise NotImplementedError
