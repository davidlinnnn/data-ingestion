"""finalize: register the Processing Result, or the failure report (#129, Processing Result
and failure report)."""

import importlib.metadata
import json
import platform

from kp_processing.stages import FailureInput, FinalizeInput, Ports, Runtime


async def run(input: FinalizeInput, ports: Ports, runtime: Runtime) -> str:
    """Write requests/{request_id}/result.json once (a retry keeps the first) and return its key:

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
    profile = runtime.profile
    request = {
        key: input.start[key]
        for key in (
            "request_id",
            "document_uid",
            "source_revision_id",
            "adopted_version",
            "adoption_sequence",
        )
    }
    request["files"] = [
        {key: file[key] for key in ("role", "custody_ref", "sha256", "size", "media_type")}
        for file in input.start["files"]
    ]
    page_images = []
    for group in input.groups:
        page_images.extend(json.loads(await ports.store.get(group.ref))["page_images"])
    assembly = json.loads(await ports.store.get(input.assembly.ref))
    limitations = [
        {"code": item.code, "scope": "profile", "detail": item.detail}
        for item in profile.limitations
    ]
    if input.plan.no_text_layer_pages:
        limitations.append(
            {
                "code": "NO_TEXT_LAYER_PAGES",
                "scope": "document",
                "detail": "no text layer on pages "
                + ", ".join(map(str, input.plan.no_text_layer_pages)),
            }
        )
    result = {
        "schema": "pdf-processing-result/v1",
        "request": request,
        "profile": {
            "id": profile.profile,
            "status_rule": profile.status_rule,
            "methods": [
                {
                    "id": method.id,
                    "version": method.version,
                    "components": list(method.components),
                    "module_digest": method.module_digest,
                }
                for method in profile.methods.values()
            ],
            "runtime_identity": {
                "python": platform.python_version(),
                "docling_slim": importlib.metadata.version("docling-slim"),
                "build_id": runtime.build_id,
            },
        },
        "outcome": "complete",
        "native": {
            "assembly_ref": input.assembly.ref,
            "page_groups": [{"pages": group.pages, "ref": group.ref} for group in input.groups],
            "page_images": page_images,
            "picture_images": assembly["picture_images"],
        },
        "inventory": {"ref": input.inventory.ref, "counts": {}},
        "enrichments": [],
        "limitations": limitations,
    }
    ref = f"requests/{input.start['request_id']}/result.json"
    # Write-once: a retried finalize keeps the result already registered.
    await ports.store.put_if_absent(
        ref, json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    )
    return ref


async def run_failure(input: FailureInput, ports: Ports, runtime: Runtime) -> str:
    """Write requests/{request_id}/failure.json once (a retry keeps the first) and return its key:

    schema         "pdf-processing-failure/v1"
    request        request_id, document_uid, source_revision_id (null when absent)
    cause, stage, error
    inventory_ref  only when not None
    """
    start = input.start if isinstance(input.start, dict) else {}
    report = {
        "schema": "pdf-processing-failure/v1",
        "request": {
            "request_id": input.request_id,
            "document_uid": start.get("document_uid"),
            "source_revision_id": start.get("source_revision_id"),
        },
        "cause": input.cause,
        "stage": input.stage,
        "error": input.error,
    }
    if input.inventory_ref is not None:
        report["inventory_ref"] = input.inventory_ref
    ref = f"requests/{input.request_id}/failure.json"
    await ports.store.put_if_absent(
        ref, json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    )
    return ref
