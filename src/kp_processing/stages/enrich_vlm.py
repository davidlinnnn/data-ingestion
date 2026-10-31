"""VLM enrichment: the item-scope methods that call the VLM, on the vlm worker (#133; #93 §3)."""

from kp_processing.profile import ProcessingProfile
from kp_processing.stages import EnrichInput, OutcomeRef, Ports, Runtime

# Methods this Activity runs; inventory items of other methods belong to other Activities.
METHODS = ("picture-interpretation", "formula", "code")


def model(profile: ProcessingProfile) -> str:
    """The VLM model the profile names: the text after the first "/" of the one component that
    every METHODS entry of the profile lists, e.g. "gpt-6-luna" for "openai/gpt-6-luna".
    Raises ValueError when those methods do not all list exactly that one component."""
    raise NotImplementedError


async def run(input: EnrichInput, ports: Ports, runtime: Runtime) -> list[OutcomeRef]:
    """Run every inventory item of METHODS, at most runtime vlm_concurrency_per_document items
    at once, and record one outcome per item; ports.heartbeat() after each item. Returns one
    OutcomeRef per such item, in inventory order. Parameters below are runtime keys.

    Per item, the reuse key, the prefix documents/{document_uid}/items/{key}, the reuse of an
    already registered {prefix}/outcome.json (nothing is sent) and the reading of inputs are
    those of enrich_local. Otherwise the package's request(item, inputs) runs off the event
    loop; a MethodOutput it returns is recorded as below, a request body is sent with
    ports.vlm.complete through the retry chain.

    Receipts, one per send, at requests/{request_id}/attempts/{run_id}/receipts/{item_id}/
    {n}.json, n = 1, 2, ... Written write-once before the send:
        {"item_id", "method": "<id>@<version>", "attempt": n,
         "params_digest": sha256 of the request body's compact sorted-key JSON,
         "sent_at": RFC 3339 UTC}
    rewritten after it with the same fields plus
        {"result": "ok" | "unavailable" | "invalid" | "refused", "reason": str | None,
         "latency_ms", "usage", "result_digest": sha256 of Completion.body | None,
         "model", "system_fingerprint"}   (the last four None when no Completion came back)
    The item's receipts already present when the call starts each count as one attempt used;
    one without "result" (the worker died between send and completion) counts as
    "unavailable".

    Retry chain (#93 §3.4), per item:
      ServiceUnavailable(r)  result unavailable, reason r; send again after a backoff of
                             min(retry.cap_s, retry.initial_s * retry.multiplier ** (u - 1))
                             * uniform(0.5, 1.0) seconds on ports.clock, u = unavailable
                             results of the item so far
      Completion.refusal     result refused, reason MODEL_REFUSAL; never sent again
      parse() raising InvalidOutput(r)  (content None is passed as "")
                             result invalid, reason r; sent again at once the first time only
      parse() returning      result ok; the item's output
    The chain ends, outcome failed, with
      MODEL_REFUSAL          on a refusal
      EMPTY_OUTPUT | SCHEMA_INVALID   on the second invalid result (its reason)
      SERVICE_UNAVAILABLE    when retry.max_attempts receipts exist and the last is not ok,
                             or when the next send (after its backoff) would start later than
                             enrichment_stage_budget_s.hard seconds after this call started
                             (ports.clock.monotonic), first sends included

    The record is enrich_local's enrichment-outcome/v1 record, with "provider_artifact_ref"
    naming {prefix}/response.json (the last Completion.body) when a Completion came back, and,
    for a package with FIELDS, "fields": {name: {"outcome", "reason", "content", "signals",
    "contradictions"}} for every FIELDS name; when the item failed as a whole each field
    carries the item's outcome and reason and content None. It is registered as enrich_local
    does, except that a SERVICE_UNAVAILABLE outcome is written (put_if_absent) to
    requests/{request_id}/attempts/{run_id}/outcomes/{key}/outcome.json and never registered,
    so that a redrive sends again instead of reusing the failure.

    Errors (ProcessingFailure, all cause "platform", metadata {"item_id", ...}):
      an input missing or differing from its sha256  integrity     INPUT_DIGEST_MISMATCH
      MethodUnavailable                               configuration METHOD_UNAVAILABLE
      RequestRejected(status)                         configuration INFERENCE_REQUEST_REJECTED
                                                      (metadata also {"status"})
      a send beyond request_cap.per_item x (inventory items, all methods) + request_cap.extra
      sends in this attempt (receipts under requests/{request_id}/attempts/{run_id}/receipts/
      when the call starts, plus this call's)         configuration REQUEST_CAP_EXCEEDED
                                                      (metadata also {"limit"})
      any other exception from a method               method        METHOD_ERROR
    A content failure is an outcome, never an error.
    """
    raise NotImplementedError
