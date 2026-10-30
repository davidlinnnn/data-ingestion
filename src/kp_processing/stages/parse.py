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

from kp_processing.stages import AssembleInput, GroupInput, GroupRef, Ports, Registered, Runtime


async def run_group(input: GroupInput, ports: Ports, runtime: Runtime) -> GroupRef:
    """Parse pages [first, last] of the source with the docling-parse method and register the
    group. key = reuse_key(document_uid, "docling-parse@<version>", the method's components,
    its module_digest, [source_sha256, "pages:<first>-<last>"]).

    When group.json already exists, returns it with reused=True and runs no inference. The
    source is read from source_key and checked against source_sha256 (mismatch: platform,
    integrity, SOURCE_DIGEST_MISMATCH). A docling failure on any page of the group raises
    ProcessingFailure(platform, method, NATIVE_PARSE_FAILED).
    """
    raise NotImplementedError


async def run_assemble(input: AssembleInput, ports: Ports, runtime: Runtime) -> Registered:
    """Rebuild the whole document from the registered groups only, without running any page
    inference (layout, table structure, OCR), and register assembly.json and the picture
    images. key = reuse_key(document_uid, "docling-parse@<version>", components,
    module_digest, [group digests in page order]). When assembly.json exists, returns it with
    reused=True. A group whose stored bytes do not match its digest, or groups that do not
    cover pages 1..N contiguously, raise ProcessingFailure(platform, integrity,
    NATIVE_COVERAGE_INCOMPLETE).
    """
    raise NotImplementedError
