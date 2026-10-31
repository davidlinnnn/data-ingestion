"""parse group and assemble: the docling-parse method's registered items (#129).

Registered objects, all under documents/{document_uid}/items/{key}/ and written once, the
JSON last so that its presence means the item is complete:

    group.json     {"schema": "docling-parse-group/v1", "pages": [first, last],
                    "page_images": [{"page", "ref", "sha256"}], ...what assemble needs}
    pages/{sha256}.png                     one page image per page
    assembly.json  {"schema": "docling-parse-assembly/v1",
                    "groups": [{"pages", "ref", "digest"}],
                    "picture_images": [{"picture_id", "page", "bbox", "ref", "sha256"}],
                    "document": DoclingDocument JSON without embedded images}
    pictures/{sha256}.png                  one image per picture

picture_id is the DoclingDocument self_ref ("#/pictures/0"); bbox is the picture's first
provenance box as docling dumps it ({l, t, r, b, coord_origin}, PDF points).
"""

import asyncio
from dataclasses import asdict

from kp_processing.identity import reuse_key
from kp_processing.methods.docling_parse import pipeline
from kp_processing.methods.docling_parse.serialization import (
    Group,
    PageImage,
    assembly_json,
    group_json,
    restore_page,
)
from kp_processing.stages import (
    AssembleInput,
    GroupInput,
    GroupRef,
    Ports,
    ProcessingFailure,
    Registered,
    Runtime,
    read_verified,
    register,
    registered,
    sha256,
)


def _incomplete() -> ProcessingFailure:
    return ProcessingFailure(
        "platform",
        "integrity",
        "NATIVE_COVERAGE_INCOMPLETE",
        "Registered groups are incomplete or inconsistent",
    )


async def run_group(input: GroupInput, ports: Ports, runtime: Runtime) -> GroupRef:
    """Parse pages [first, last] of the source with the docling-parse method and register the
    group. key = reuse_key(document_uid, "docling-parse@<version>", the method's components,
    its module_digest, [source_sha256, "pages:<first>-<last>"]).

    When group.json already exists, returns it with reused=True and runs no inference. The
    source is read from source_key and checked against source_sha256 (mismatch: platform,
    integrity, SOURCE_DIGEST_MISMATCH). A docling failure on any page of the group raises
    ProcessingFailure(platform, method, NATIVE_PARSE_FAILED).
    """
    method = runtime.profile.methods["docling-parse"]
    first, last = input.pages
    key = reuse_key(
        input.document_uid,
        method.ref,
        method.components,
        method.module_digest,
        [input.source_sha256, f"pages:{first}-{last}"],
    )
    prefix = f"documents/{input.document_uid}/items/{key}"
    ref = f"{prefix}/group.json"
    if existing := await registered(ports.store, ref):
        return GroupRef(input.pages, existing.ref, existing.digest, existing.reused)
    data = await ports.store.get(input.source_key)
    if sha256(data) != input.source_sha256:
        raise ProcessingFailure(
            "platform",
            "integrity",
            "SOURCE_DIGEST_MISMATCH",
            "Source bytes differ from declared digest",
        )
    try:
        count, captured = await asyncio.to_thread(pipeline.parse_group, data, input.pages)
    except Exception as exc:
        raise ProcessingFailure(
            "platform", "method", "NATIVE_PARSE_FAILED", "PDF group conversion failed"
        ) from exc
    images = []
    for page, png in captured:
        digest = sha256(png)
        image_ref = f"{prefix}/pages/{digest}.png"
        await ports.store.put_if_absent(image_ref, png)
        images.append(PageImage(page=page.page_no, ref=image_ref, sha256=digest))
    body = group_json(
        Group(
            schema="docling-parse-group/v1",
            pages=(first, last),
            source_sha256=input.source_sha256,
            page_count=count,
            source_name="paper.pdf",
            page_results=[page for page, _ in captured],
            page_images=images,
        )
    )
    group = await register(ports.store, ref, body)
    return GroupRef(input.pages, group.ref, group.digest, group.reused)


async def run_assemble(input: AssembleInput, ports: Ports, runtime: Runtime) -> Registered:
    """Rebuild the whole document from the registered groups only, without running any page
    inference (layout, table structure, OCR), and register assembly.json and the picture
    images. key = reuse_key(document_uid, "docling-parse@<version>", components,
    module_digest, [group digests in page order]). When assembly.json exists, returns it with
    reused=True. A group whose stored bytes do not match its digest, or groups that do not
    cover pages 1..N contiguously, raise ProcessingFailure(platform, integrity,
    NATIVE_COVERAGE_INCOMPLETE).
    """
    method = runtime.profile.methods["docling-parse"]
    key = reuse_key(
        input.document_uid,
        method.ref,
        method.components,
        method.module_digest,
        [group.digest for group in input.groups],
    )
    prefix = f"documents/{input.document_uid}/items/{key}"
    ref = f"{prefix}/assembly.json"
    if existing := await registered(ports.store, ref):
        return existing
    groups = []
    pages = []
    next_page = 1
    count = None
    for group_ref in input.groups:
        data = await read_verified(ports.store, group_ref.ref, group_ref.digest, _incomplete)
        try:
            group = Group.model_validate_json(data)
            first, last = group.pages
            if (
                list(group.pages) != group_ref.pages
                or first != next_page
                or last < first
                or group.source_sha256 != input.source_sha256
                or (count is not None and group.page_count != count)
                or last > group.page_count
                or len(group.page_results) != last - first + 1
                or any(
                    page.page_no != first + index for index, page in enumerate(group.page_results)
                )
                or [image.page for image in group.page_images]
                != [page.page_no for page in group.page_results]
            ):
                raise ValueError("Invalid group coverage")
        except (ValueError, TypeError) as exc:
            raise _incomplete() from exc
        for saved, image in zip(group.page_results, group.page_images, strict=True):
            png = await read_verified(ports.store, image.ref, image.sha256, _incomplete)
            try:
                pages.append(await asyncio.to_thread(restore_page, saved, png))
            except (ValueError, TypeError, OSError) as exc:
                raise _incomplete() from exc
        groups.append(group)
        count = group.page_count
        next_page = last + 1
    if count is None or next_page != count + 1:
        raise _incomplete()
    document, pictures = await asyncio.to_thread(pipeline.assemble, groups, pages)
    picture_refs = []
    for picture, png in pictures:
        digest = sha256(png)
        image_ref = f"{prefix}/pictures/{digest}.png"
        await ports.store.put_if_absent(image_ref, png)
        picture_refs.append({**picture, "ref": image_ref, "sha256": digest})
    body = assembly_json(
        [
            {key: value for key, value in asdict(group).items() if key != "reused"}
            for group in input.groups
        ],
        picture_refs,
        document,
    )
    return await register(ports.store, ref, body)
