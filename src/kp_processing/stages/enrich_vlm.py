"""VLM enrichment: the item-scope methods that call the VLM, on the vlm worker (#133; #93 §3)."""

import asyncio
import dataclasses
import json
import random
import time
from datetime import UTC, datetime
from typing import Any

from kp_processing.identity import canonical_json
from kp_processing.methods import InvalidOutput, InventoryItem, MethodOutput, MethodUnavailable
from kp_processing.ports.inference import Completion, RequestRejected, ServiceUnavailable
from kp_processing.profile import ProcessingProfile
from kp_processing.stages import (
    EnrichInput,
    OutcomeRef,
    Ports,
    ProcessingFailure,
    Runtime,
    enrichment_body,
    enrichment_inputs,
    enrichment_key,
    in_thread,
    item_prefix,
    method_failure,
    register_enrichment,
    registered,
    sha256,
)

# Methods this Activity runs; inventory items of other methods belong to other Activities.
METHODS = ("picture-interpretation", "formula", "code")


def model(profile: ProcessingProfile) -> str:
    """The VLM model the profile names: the text after the first "/" of the one component that
    every METHODS entry of the profile lists, e.g. "gpt-6-luna" for "openai/gpt-6-luna".
    Raises ValueError when those methods do not all list exactly that one component."""
    components = []
    for name in METHODS:
        method = profile.methods.get(name)
        if method is None or len(method.components) != 1:
            raise ValueError("VLM methods must each list one shared component")
        components.append(method.components[0])
    if len(set(components)) != 1:
        raise ValueError("VLM methods disagree on their component")
    provider, separator, name = components[0].partition("/")
    if not provider or not separator or not name:
        raise ValueError("VLM component must name a provider and model")
    return name


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
    does, except that a SERVICE_UNAVAILABLE outcome and its files (response.json included)
    are written (put_if_absent) under requests/{request_id}/attempts/{run_id}/outcomes/{key}/
    instead of the prefix, its refs naming them there, and never registered: a redrive sends
    again instead of reusing the failure, and its own answer becomes the registered artifact.

    Errors (ProcessingFailure, all cause "platform", metadata {"item_id", ...}):
      an input missing or differing from its sha256  integrity     INPUT_DIGEST_MISMATCH
      MethodUnavailable                               configuration METHOD_UNAVAILABLE
      RequestRejected(status)                         configuration INFERENCE_REQUEST_REJECTED
                                                      (metadata also {"status"})
      a receipt number already taken (another worker
      sends the same item in this attempt)            integrity     RECEIPT_CONFLICT
      a send beyond request_cap.per_item x (inventory items, all methods) + request_cap.extra
      sends in this attempt (receipts under requests/{request_id}/attempts/{run_id}/receipts/
      when the call starts, plus this call's)         configuration REQUEST_CAP_EXCEEDED
                                                      (metadata also {"limit"})
      any other exception from a method               method        METHOD_ERROR
    A content failure is an outcome, never an error.
    """
    started = ports.clock.monotonic()
    inventory = json.loads(await ports.store.get(input.inventory.ref))
    settings = runtime.profile.runtime
    retry = settings["retry"]
    budget = settings["enrichment_stage_budget_s"]["hard"]
    attempt_prefix = f"requests/{input.request_id}/attempts/{input.run_id}"
    receipt_prefix = f"{attempt_prefix}/receipts/"
    keys = [
        key
        for key in await ports.store.list_prefix(receipt_prefix.rstrip("/"))
        if key.startswith(receipt_prefix)
    ]
    used = len(keys)
    limit = (
        settings["request_cap"]["per_item"] * len(inventory["items"])
        + settings["request_cap"]["extra"]
    )
    receipt_keys: dict[str, list[str]] = {}
    for key in keys:
        item_id = key[len(receipt_prefix) :].rsplit("/", 1)[0]
        receipt_keys.setdefault(item_id, []).append(key)
    cap_lock = asyncio.Lock()
    input_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(settings["vlm_concurrency_per_document"])
    verified: dict[str, tuple[bytes, str]] = {}

    async def process(item: InventoryItem) -> OutcomeRef:
        nonlocal used
        async with semaphore:
            item_id = item["item_id"]
            method = runtime.profile.methods[item["method"]]
            key = enrichment_key(input.document_uid, item, method)
            prefix = item_prefix(input.document_uid, key)
            if existing := await registered(ports.store, f"{prefix}/outcome.json"):
                ports.heartbeat()
                return OutcomeRef(item_id, existing.ref, existing.digest, True)
            inputs = await enrichment_inputs(ports.store, item, verified, input_lock)
            package = method.package
            try:
                request = await in_thread(package.request, item, inputs)
            except Exception as exc:
                raise method_failure(item_id, exc) from exc
            if isinstance(request, MethodOutput):
                output = request
            else:
                previous = [
                    json.loads(await ports.store.get(ref)) for ref in receipt_keys.get(item_id, [])
                ]
                previous.sort(key=lambda receipt: receipt["attempt"])
                attempts = len(previous)
                number = max((receipt["attempt"] for receipt in previous), default=0)
                unavailable = sum(
                    receipt.get("result", "unavailable") == "unavailable" for receipt in previous
                )
                invalid = sum(receipt.get("result") == "invalid" for receipt in previous)
                last_result = previous[-1].get("result", "unavailable") if previous else None
                last_reason = previous[-1].get("reason") if previous else None
                last_completion: Completion | None = None
                output = MethodOutput(outcome="failed", reason="SERVICE_UNAVAILABLE")
                params_digest = sha256(canonical_json(request))
                while True:
                    if last_result == "refused":
                        output = MethodOutput(outcome="failed", reason="MODEL_REFUSAL")
                        break
                    if last_result == "invalid" and invalid >= 2:
                        output = MethodOutput(outcome="failed", reason=last_reason)
                        break
                    if attempts >= retry["max_attempts"]:
                        break
                    delay = 0.0
                    if last_result == "unavailable":
                        delay = min(
                            retry["cap_s"],
                            retry["initial_s"] * retry["multiplier"] ** (unavailable - 1),
                        ) * random.uniform(0.5, 1.0)
                    if ports.clock.monotonic() - started + delay > budget:
                        break
                    if delay:
                        await ports.clock.sleep(delay)
                    number += 1
                    receipt: dict[str, Any] = {
                        "item_id": item_id,
                        "method": method.ref,
                        "attempt": number,
                        "params_digest": params_digest,
                        "sent_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    }
                    receipt_ref = f"{receipt_prefix}{item_id}/{number}.json"
                    if ports.vlm is None:
                        raise method_failure(
                            item_id, MethodUnavailable("VLM transport is not configured")
                        )
                    async with cap_lock:
                        if ports.clock.monotonic() - started > budget:
                            break
                        if used >= limit:
                            raise ProcessingFailure(
                                "platform",
                                "configuration",
                                "REQUEST_CAP_EXCEEDED",
                                "External request cap exceeded",
                                metadata={"item_id": item_id, "limit": str(limit)},
                            )
                        if not await ports.store.put_if_absent(
                            receipt_ref, canonical_json(receipt)
                        ):
                            # Another worker is sending this item in the same attempt.
                            raise ProcessingFailure(
                                "platform",
                                "integrity",
                                "RECEIPT_CONFLICT",
                                "External request receipt already exists",
                                metadata={"item_id": item_id},
                            )
                        used += 1
                    attempts += 1
                    answer: Completion | None = None
                    send_started = time.perf_counter()
                    try:
                        answer = await ports.vlm.complete(request)
                    except ServiceUnavailable as exc:
                        last_result, last_reason = "unavailable", exc.reason
                        unavailable += 1
                    except RequestRejected as exc:
                        raise ProcessingFailure(
                            "platform",
                            "configuration",
                            "INFERENCE_REQUEST_REJECTED",
                            "Inference request was rejected",
                            metadata={"item_id": item_id, "status": str(exc.status)},
                        ) from exc
                    except MethodUnavailable as exc:
                        raise method_failure(item_id, exc) from exc
                    latency_ms = (time.perf_counter() - send_started) * 1000
                    if answer is not None:
                        last_completion = answer
                        if answer.refusal:
                            last_result, last_reason = "refused", "MODEL_REFUSAL"
                        else:
                            try:
                                output = await in_thread(
                                    package.parse, item, inputs, answer.content or ""
                                )
                            except InvalidOutput as exc:
                                last_result, last_reason = "invalid", exc.reason
                                invalid += 1
                            except Exception as exc:
                                raise method_failure(item_id, exc) from exc
                            else:
                                last_result, last_reason = "ok", None
                    receipt.update(
                        result=last_result,
                        reason=last_reason,
                        latency_ms=latency_ms,
                        usage=answer.usage if answer else None,
                        result_digest=sha256(answer.body) if answer else None,
                        model=answer.model if answer else None,
                        system_fingerprint=answer.system_fingerprint if answer else None,
                    )
                    await ports.store.put(receipt_ref, canonical_json(receipt))
                    if last_result == "ok":
                        break
                if last_completion is not None:
                    output = dataclasses.replace(
                        output,
                        files={**output.files, "response.json": last_completion.body},
                        provider_artifact="response.json",
                    )
            if output.reason == "SERVICE_UNAVAILABLE":
                transient_prefix = f"{attempt_prefix}/outcomes/{key}"
                body = enrichment_body(method, transient_prefix, output)
                for name, data in output.files.items():
                    await ports.store.put_if_absent(f"{transient_prefix}/{name}", data)
                ref = f"{transient_prefix}/outcome.json"
                created = await ports.store.put_if_absent(ref, body)
                if not created:
                    body = await ports.store.get(ref)
                result = OutcomeRef(item_id, ref, sha256(body), not created)
            else:
                result = await register_enrichment(ports.store, item_id, method, prefix, output)
            ports.heartbeat()
            return result

    tasks: list[asyncio.Task[OutcomeRef]] = []
    try:
        async with asyncio.TaskGroup() as group:
            for item in inventory["items"]:
                if item["method"] in METHODS:
                    tasks.append(group.create_task(process(item)))
    except* ProcessingFailure as failures:
        raise failures.exceptions[0] from None
    return [task.result() for task in tasks]
