"""finalize: register the Processing Result, or the failure report (#129, Processing Result
and failure report)."""

import importlib
import importlib.metadata
import json
import platform

from kp_processing.identity import canonical_json
from kp_processing.ports.object_store import ObjectStore
from kp_processing.stages import (
    FailureInput,
    FinalizeInput,
    Ports,
    ProcessingFailure,
    Runtime,
    read_verified,
)

CONTENT_INLINE_MAX = 16384  # bytes of compact JSON; larger content stays in the outcome record


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
    inventory    ref, counts{<method_id>: {unverified, disputed, failed, no_text}} for each
                 method with inventory items; buckets are disjoint, an item whose outcome is
                 no_text counts under no_text only
    enrichments  one per inventory item, in inventory order (see below)
    limitations  the profile's [{code, scope: "profile", detail}], then, when the plan
                 lists any, {code: "NO_TEXT_LAYER_PAGES", scope: "document",
                 detail: "no text layer on pages 3, 5"}

    Each enrichment joins an inventory item with its outcome record and applies the status
    rule kp_processing.status_rules.<profile status_rule>:

        item_id, result_ref (the outcome record), method_ref, scope, origin (from the record),
        target_refs [target_ref], input_refs [the item's input refs], content (the record's
        content when its compact JSON is at most CONTENT_INLINE_MAX bytes, else null: read
        result_ref), evidence_refs, status, status_reason (from the rule), signals,
        provider_artifact_ref, reused (from the OutcomeRef)

    An outcome record with "fields" yields one enrichment per field instead, in the record's
    key order: item_id "<item_id>/<field>", content, signals, status and status_reason from
    the field's entry (the rule applied to it), the rest from the record; counts count
    enrichments.

    When any enrichment has status_reason SERVICE_UNAVAILABLE, the redrive marker
    documents/{document_uid}/service-unavailable/{request_id} (empty) is written first,
    write-once (#129; listed by service_unavailable()).

    An inventory item without an OutcomeRef, or whose outcome record is missing or differs
    from the OutcomeRef's digest, raises ProcessingFailure(platform, integrity,
    OUTCOME_RECORD_MISSING, metadata {"item_id"}). A status rule that does not exist raises
    ProcessingFailure(platform, configuration, STATUS_RULE_UNKNOWN).
    """
    profile = runtime.profile
    rule_name = f"kp_processing.status_rules.{profile.status_rule}"
    try:
        rule = importlib.import_module(rule_name)
    except ModuleNotFoundError as exc:
        if exc.name != rule_name:
            raise
        raise ProcessingFailure(
            "platform", "configuration", "STATUS_RULE_UNKNOWN", "Unknown Enrichment Status rule"
        ) from exc
    inventory = json.loads(await ports.store.get(input.inventory.ref))
    outcomes = {outcome.item_id: outcome for outcome in input.outcomes}
    enrichments = []
    counts: dict[str, dict[str, int]] = {}
    for item in inventory["items"]:

        def missing(item_id: str = item["item_id"]) -> ProcessingFailure:
            return ProcessingFailure(
                "platform",
                "integrity",
                "OUTCOME_RECORD_MISSING",
                "Enrichment outcome record is missing or differs from its declared digest",
                metadata={"item_id": item_id},
            )

        outcome = outcomes.get(item["item_id"])
        if outcome is None:
            raise missing()
        record = json.loads(await read_verified(ports.store, outcome.ref, outcome.digest, missing))
        method_counts = counts.setdefault(
            item["method"], {"unverified": 0, "disputed": 0, "failed": 0, "no_text": 0}
        )
        entries = record["fields"].items() if "fields" in record else [(None, record)]
        for name, field in entries:
            status, reason = rule.assign(field)
            content = field["content"]
            if len(canonical_json(content)) > CONTENT_INLINE_MAX:
                content = None
            enrichments.append(
                {
                    "item_id": f"{item['item_id']}/{name}" if name is not None else item["item_id"],
                    "result_ref": outcome.ref,
                    "method_ref": record["method_ref"],
                    "scope": record["scope"],
                    "origin": record["origin"],
                    "target_refs": [item["target_ref"]],
                    "input_refs": [source["ref"] for source in item["input_refs"]],
                    "content": content,
                    "evidence_refs": record["evidence_refs"],
                    "status": status,
                    "status_reason": reason,
                    "signals": field["signals"],
                    "provider_artifact_ref": record["provider_artifact_ref"],
                    "reused": outcome.reused,
                }
            )
            method_counts["no_text" if field["outcome"] == "no_text" else status] += 1
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
            "id": profile.id,
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
        "inventory": {"ref": input.inventory.ref, "counts": counts},
        "enrichments": enrichments,
        "limitations": limitations,
    }
    ref = f"requests/{input.start['request_id']}/result.json"
    if any(item["status_reason"] == "SERVICE_UNAVAILABLE" for item in enrichments):
        marker = (
            f"documents/{input.start['document_uid']}/service-unavailable/"
            f"{input.start['request_id']}"
        )
        await ports.store.put_if_absent(marker, b"")
    # Write-once: a retried finalize keeps the result already registered.
    await ports.store.put_if_absent(ref, canonical_json(result))
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
    await ports.store.put_if_absent(ref, canonical_json(report))
    return ref


async def service_unavailable(store: ObjectStore) -> list[dict[str, str]]:
    """Every redrive marker as {"document_uid", "request_id"}, sorted. Whether the request is
    still its document's current revision is for #98 to decide, not this list."""
    markers = []
    # shortcut: scans every documents/ key; use a marker index when listing grows too slow.
    for key in await store.list_prefix("documents/"):
        parts = key.split("/")
        if len(parts) == 4 and parts[1] and parts[2] == "service-unavailable" and parts[3]:
            markers.append({"document_uid": parts[1], "request_id": parts[3]})
    return sorted(markers, key=lambda marker: (marker["document_uid"], marker["request_id"]))
