"""local enrichment: the item-scope methods that run on the inference worker (#132)."""

import asyncio
import json

from kp_processing.methods import InventoryItem
from kp_processing.stages import (
    EnrichInput,
    OutcomeRef,
    Ports,
    Runtime,
    enrichment_inputs,
    enrichment_key,
    in_thread,
    item_prefix,
    method_failure,
    register_enrichment,
    registered,
)


async def run(input: EnrichInput, ports: Ports, runtime: Runtime) -> list[OutcomeRef]:
    """Run every inventory item of a method that runs locally (not Method.calls_vlm), in inventory
    order, and register one outcome record per item; ports.heartbeat() after each item. Returns one
    OutcomeRef per such item, in inventory order.

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
    lock = asyncio.Lock()
    outcomes = []
    item: InventoryItem
    for item in inventory["items"]:
        method = runtime.profile.methods[item["method"]]
        if method.calls_vlm:
            continue
        key = enrichment_key(input.document_uid, item, method)
        prefix = item_prefix(input.document_uid, key)
        ref = f"{prefix}/outcome.json"
        if existing := await registered(ports.store, ref):
            outcomes.append(OutcomeRef(item["item_id"], existing.ref, existing.digest, True))
            ports.heartbeat()
            continue

        inputs = await enrichment_inputs(ports.store, item, verified, lock)
        package = method.package
        try:
            output = await in_thread(package.run, item, inputs)
        except Exception as exc:
            raise method_failure(item["item_id"], exc) from exc
        outcomes.append(
            await register_enrichment(ports.store, item["item_id"], method, prefix, output)
        )
        ports.heartbeat()
    return outcomes
