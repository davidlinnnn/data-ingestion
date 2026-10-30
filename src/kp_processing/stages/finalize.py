"""finalize: register the Processing Result, or the failure report (#129, Processing Result
and failure report)."""

from kp_processing.stages import FailureInput, FinalizeInput, Ports, Runtime


async def run(input: FinalizeInput, ports: Ports, runtime: Runtime) -> str:
    """Write requests/{request_id}/result.json (overwriting) and return its key:

    schema       "pdf-processing-result/v1"
    request      request_id, document_uid, source_revision_id, adopted_version,
                 adoption_sequence, files[{role, custody_ref, sha256, size, media_type}]
    profile      id, status_rule, methods[{id, version, components[], module_digest}] in
                 profile order, runtime_identity{python, docling_slim, build_id}
    outcome      "complete"
    native       assembly_ref, page_groups[{pages, ref}], page_images[{page, ref, sha256}]
                 in page order (read from the group objects), picture_images[{picture_id,
                 page, bbox, ref, sha256}] (read from the assembly object)
    inventory    ref, counts{<method_id>: {unverified, disputed, failed, no_text}}
                 ({} while the inventory has no items)
    enrichments  []
    limitations  the profile's [{code, scope: "profile", detail}], then, when the plan
                 lists any, {code: "NO_TEXT_LAYER_PAGES", scope: "document",
                 detail: "no text layer on pages 3, 5"}
    """
    raise NotImplementedError


async def run_failure(input: FailureInput, ports: Ports, runtime: Runtime) -> str:
    """Write requests/{request_id}/failure.json (overwriting) and return its key:

    schema         "pdf-processing-failure/v1"
    request        request_id, document_uid, source_revision_id (null when absent)
    cause, stage, error
    inventory_ref  only when not None
    """
    raise NotImplementedError
