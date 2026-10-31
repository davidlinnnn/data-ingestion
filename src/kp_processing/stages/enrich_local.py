"""local enrichment: the item-scope methods that run on the inference worker (#132)."""

from kp_processing.stages import EnrichInput, Outcome, Ports, Runtime

# Methods this Activity runs; inventory items of other methods belong to other Activities.
METHODS = ("picture-ocr", "code", "table-status")


async def run(input: EnrichInput, ports: Ports, runtime: Runtime) -> list[Outcome]:
    """Run every inventory item of METHODS, in inventory order, and register one outcome
    record per item. Returns one Outcome per such item, in inventory order.

    Per item, with method = runtime.profile.methods[item["method"]]:
      key = reuse_key(document_uid, method.ref, method.components, method.module_digest,
                      [each input_refs sha256 in order,
                       compact sorted-key JSON of {"target_ref", "page", "bbox"}])
      prefix = documents/{document_uid}/items/{key}
    When {prefix}/outcome.json exists, it is returned with reused=True and the method does
    not run. Otherwise each input_refs object is read and checked against its sha256; the
    method package's run(item, inputs) runs off the event loop; its files are registered as
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
    raise NotImplementedError
