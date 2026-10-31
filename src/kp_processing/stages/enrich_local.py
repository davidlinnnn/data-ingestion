"""local enrichment: the item-scope methods that run on the inference worker (#132)."""

import asyncio
import json

from kp_processing.identity import reuse_key
from kp_processing.methods import InventoryItem, MethodUnavailable
from kp_processing.stages import (
    EnrichInput,
    OutcomeRef,
    Ports,
    ProcessingFailure,
    Runtime,
    read_verified,
    register,
    registered,
)

# Methods this Activity runs; inventory items of other methods belong to other Activities.
METHODS = ("picture-ocr", "code", "table-status")


async def run(input: EnrichInput, ports: Ports, runtime: Runtime) -> list[OutcomeRef]:
    """Run every inventory item of METHODS, in inventory order, and register one outcome
    record per item; ports.heartbeat() after each item. Returns one OutcomeRef per such item,
    in inventory order.

    Per item, with method = runtime.profile.methods[item["method"]]:
      key = reuse_key(document_uid, method.ref, method.components, method.module_digest,
                      [each input_refs sha256 in order,
                       compact sorted-key JSON of {"target_ref", "page", "bbox"}])
      prefix = documents/{document_uid}/items/{key}
    When {prefix}/outcome.json exists, it is returned with reused=True and the method does
    not run. Otherwise each input ref is read and verified at most once per call; repeated
    refs must declare the same sha256. The method package's run(item, inputs) runs off the
    event loop; its files are registered as
    {prefix}/{name}; then {prefix}/outcome.json is registered last, write-once:

        {"schema": "enrichment-outcome/v1",
         "method_ref": {"id", "version", "digest": module_digest},
         "scope": "item", "origin": the package's ORIGIN,
         "outcome": "success" | "no_text" | "failed", "reason": str | null,
         "content": ..., "evidence_refs": [{prefix}/{name}...],
         "provider_artifact_ref": {prefix}/{name} | null,
         "signals": {...}, "contradictions": [...]}

    Errors (ProcessingFailure, all cause "platform"):
      an input missing or differing from its sha256  integrity     INPUT_DIGEST_MISMATCH
      MethodUnavailable                               configuration METHOD_UNAVAILABLE
      any other exception from a method               method        METHOD_ERROR
    each with metadata {"item_id": ...}. A content failure is an outcome, never an error.
    """
    inventory = json.loads(await ports.store.get(input.inventory.ref))
    verified: dict[str, tuple[bytes, str]] = {}
    outcomes = []
    item: InventoryItem
    for item in inventory["items"]:
        if item["method"] not in METHODS:
            continue
        method = runtime.profile.methods[item["method"]]
        target = json.dumps(
            {key: item[key] for key in ("target_ref", "page", "bbox")},
            sort_keys=True,
            separators=(",", ":"),
        )
        key = reuse_key(
            input.document_uid,
            method.ref,
            method.components,
            method.module_digest,
            [*(ref["sha256"] for ref in item["input_refs"]), target],
        )
        prefix = f"documents/{input.document_uid}/items/{key}"
        ref = f"{prefix}/outcome.json"
        if existing := await registered(ports.store, ref):
            outcomes.append(OutcomeRef(item["item_id"], existing.ref, existing.digest, True))
            ports.heartbeat()
            continue

        def invalid(item_id: str = item["item_id"]) -> ProcessingFailure:
            return ProcessingFailure(
                "platform",
                "integrity",
                "INPUT_DIGEST_MISMATCH",
                "Enrichment input is missing or differs from its declared digest",
                metadata={"item_id": item_id},
            )

        inputs = []
        for source in item["input_refs"]:
            if source["ref"] not in verified:
                data = await read_verified(ports.store, source["ref"], source["sha256"], invalid)
                verified[source["ref"]] = (data, source["sha256"])
            data, digest = verified[source["ref"]]
            if digest != source["sha256"]:
                raise invalid()
            inputs.append(data)
        package = method.package
        try:
            output = await asyncio.to_thread(package.run, item, inputs)
        except MethodUnavailable as exc:
            raise ProcessingFailure(
                "platform",
                "configuration",
                "METHOD_UNAVAILABLE",
                str(exc),
                metadata={"item_id": item["item_id"]},
            ) from exc
        except Exception as exc:
            raise ProcessingFailure(
                "platform",
                "method",
                "METHOD_ERROR",
                "Enrichment method failed",
                metadata={"item_id": item["item_id"]},
            ) from exc
        for name, data in output.files.items():
            await ports.store.put_if_absent(f"{prefix}/{name}", data)
        body = json.dumps(
            {
                "schema": "enrichment-outcome/v1",
                "method_ref": {
                    "id": method.id,
                    "version": method.version,
                    "digest": method.module_digest,
                },
                "scope": "item",
                "origin": package.ORIGIN,
                "outcome": output.outcome,
                "reason": output.reason,
                "content": output.content,
                "evidence_refs": [f"{prefix}/{name}" for name in output.evidence],
                "provider_artifact_ref": (
                    f"{prefix}/{output.provider_artifact}" if output.provider_artifact else None
                ),
                "signals": output.signals,
                "contradictions": output.contradictions,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        result = await register(ports.store, ref, body)
        outcomes.append(OutcomeRef(item["item_id"], result.ref, result.digest, result.reused))
        ports.heartbeat()
    return outcomes
