"""External enrichment: the methods that call the VLM, on the vlm worker (#133), and the retry
chain and receipt scheme that every external request goes through, the Document Summary's (#155)
included (#93 §3)."""

import asyncio
import dataclasses
import functools
import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from kp_processing import metrics
from kp_processing.identity import canonical_json
from kp_processing.methods import (
    DocumentItem,
    InvalidOutput,
    InventoryItem,
    MethodOutput,
    MethodUnavailable,
)
from kp_processing.ports.inference import (
    Completion,
    InferenceTransport,
    RequestRejected,
    ServiceUnavailable,
)
from kp_processing.ports.object_store import ObjectStore
from kp_processing.profile import Method, ProcessingProfile, Service
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


def model(profile: ProcessingProfile, service: Service = "vlm") -> str:
    """The model the profile names for service: the text after the first "/" of the one
    component that every method whose service it is lists, e.g. "gpt-6-luna" for
    "openai/gpt-6-luna". Raises ValueError when those methods do not all list exactly that one
    component."""
    components = []
    for method in profile.methods.values():
        if method.service != service:
            continue
        if len(method.components) != 1:
            raise ValueError(f"{service} methods must each list one shared component")
        components.append(method.components[0])
    if len(set(components)) != 1:
        raise ValueError(f"{service} methods disagree on their component")
    provider, separator, name = components[0].partition("/")
    if not provider or not separator or not name:
        raise ValueError(f"{service} component must name a provider and model")
    return name


async def run(input: EnrichInput, ports: Ports, runtime: Runtime) -> list[OutcomeRef]:
    """Run every inventory item of a method whose Method.service is "vlm", at most runtime
    vlm_concurrency_per_document items at once, and record one outcome per item; ports.heartbeat()
    after each item. Requests go only through ports.vlm. Returns one OutcomeRef per such item, in
    inventory order. Parameters below are runtime keys.

    Per item, the reuse key, the prefix documents/{document_uid}/items/{key}, the reuse of an
    already registered {prefix}/outcome.json (nothing is sent) and the reading of inputs are
    those of enrich_local. Otherwise the package's request(item, inputs) runs off the event
    loop; a MethodOutput it returns is recorded as below, a request body is sent with
    Sends.send (directory: the item_id), parse being the package's parse(item, inputs, content),
    resuming the chain of the item's receipts already present when the call starts. The cap
    counts the receipts of the vlm methods' items, limit request_cap.per_item x (inventory
    items, all methods) + request_cap.extra; sends stop at enrichment_stage_budget_s.hard
    seconds after this call started. The item's sends at the end of its chain, earlier receipts
    included, are counted by metrics.item_attempts. The output is parse's, or outcome failed with
    the chain's reason.

    The record is enrich_local's enrichment-outcome/v1 record ("scope" from the package), with
    "provider_artifact_ref"
    naming {prefix}/response.json (the last Completion.body) when a Completion came back, and,
    for a package with FIELDS, "fields": {name: {"outcome", "reason", "content", "signals",
    "contradictions"}} for every FIELDS name; when the item failed as a whole each field
    carries the item's outcome and reason and content None. It is registered as enrich_local
    does, except that a SERVICE_UNAVAILABLE outcome is written by register_transient.

    Errors: Sends.send's, and (ProcessingFailure, cause "platform", metadata {"item_id"})
      an input missing or differing from its sha256  integrity     INPUT_DIGEST_MISMATCH
      MethodUnavailable                               configuration METHOD_UNAVAILABLE
      any other exception from a method               method        METHOD_ERROR
    A content failure is an outcome, never an error.
    """
    inventory = json.loads(await ports.store.get(input.inventory.ref))
    methods = runtime.profile.methods
    items = [item for item in inventory["items"] if methods[item["method"]].service == "vlm"]
    return await send_items(input, ports, runtime, "vlm", items, len(inventory["items"]))


async def send_items(
    input: EnrichInput,
    ports: Ports,
    runtime: Runtime,
    service: Service,
    items: list[InventoryItem | DocumentItem],
    counted: int,
) -> list[OutcomeRef]:
    """run()'s procedure for the given items of service's methods, through ports.<service>: at
    most runtime <service>_concurrency_per_document at once, the cap limit request_cap.per_item
    x counted + request_cap.extra. Returns one OutcomeRef per item, in order."""
    started = ports.clock.monotonic()
    settings = runtime.profile.runtime
    attempt_prefix = f"requests/{input.request_id}/attempts/{input.run_id}"
    limit = settings["request_cap"]["per_item"] * counted + settings["request_cap"]["extra"]
    sends = await Sends.start(
        ports, runtime, service, attempt_prefix, limit,
        started + settings["enrichment_stage_budget_s"]["hard"],
    )  # fmt: skip
    input_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(settings[f"{service}_concurrency_per_document"])
    verified: dict[str, tuple[bytes, str]] = {}

    async def process(item: InventoryItem | DocumentItem) -> OutcomeRef:
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
                    json.loads(await ports.store.get(ref)) for ref in sends.receipts(item_id)
                ]
                sent = await sends.send(
                    item_id, method.ref, item_id, request,
                    functools.partial(package.parse, item, inputs), previous,
                )  # fmt: skip
                metrics.item_attempts.labels(service).observe(sent.attempts)
                output = (
                    sent.value
                    if sent.value is not None
                    else MethodOutput(outcome="failed", reason=sent.reason)
                )
                if sent.completions:
                    output = dataclasses.replace(
                        output,
                        files={**output.files, "response.json": sent.completions[-1].body},
                        provider_artifact="response.json",
                    )
            if output.reason == "SERVICE_UNAVAILABLE":
                result = await register_transient(
                    ports.store, item_id, method, f"{attempt_prefix}/outcomes/{key}", output
                )
            else:
                result = await register_enrichment(ports.store, item_id, method, prefix, output)
            ports.heartbeat()
            return result

    tasks: list[asyncio.Task[OutcomeRef]] = []
    try:
        async with asyncio.TaskGroup() as group:
            for item in items:
                tasks.append(group.create_task(process(item)))
    except* ProcessingFailure as failures:
        raise failures.exceptions[0] from None
    return [task.result() for task in tasks]


async def register_transient(
    store: ObjectStore, item_id: str, method: Method, prefix: str, output: MethodOutput
) -> OutcomeRef:
    """Write a SERVICE_UNAVAILABLE outcome and its files (put_if_absent) under prefix,
    requests/{request_id}/attempts/{run_id}/outcomes/{key}, its refs naming them there, and never
    register it: a redrive sends again instead of reusing the failure, and its own answer
    becomes the registered artifact."""
    body = enrichment_body(method, prefix, output)
    for name, data in output.files.items():
        await store.put_if_absent(f"{prefix}/{name}", data)
    ref = f"{prefix}/outcome.json"
    created = await store.put_if_absent(ref, body)
    if not created:
        body = await store.get(ref)
    return OutcomeRef(item_id, ref, sha256(body), not created)


@dataclass(frozen=True)
class Sent:
    value: Any  # parse's result; None when the chain ended without one
    reason: str | None  # set exactly when value is None (the chain's end below)
    attempts: int  # sends in the chain, resumed receipts included
    completions: list[Completion] = field(default_factory=list)  # this call's answers, in order


class Sends:
    """One Activity's sends to one service (#93 §3.4): receipts, the attempt's request cap and
    the retry chain. Build it with start()."""

    def __init__(
        self,
        ports: Ports,
        runtime: Runtime,
        service: Service,
        attempt_prefix: str,
        limit: int,
        deadline: float,
    ) -> None:
        self.ports = ports
        self.retry = runtime.profile.runtime["retry"]
        self.service = service
        self.transport: InferenceTransport | None = getattr(ports, service)
        self.prefix = f"{attempt_prefix}/receipts/"
        self.methods = runtime.profile.methods
        self.keys: list[str] = []
        self.limit = limit
        self.deadline = deadline
        self.lock = asyncio.Lock()
        self.numbers: dict[str, int] = {}

    @classmethod
    async def start(
        cls,
        ports: Ports,
        runtime: Runtime,
        service: Service,
        attempt_prefix: str,
        limit: int,
        deadline: float,
    ) -> "Sends":
        """Sends that count, toward limit, the receipts under {attempt_prefix}/receipts/ whose
        item (the path after the prefix starts with its id, "<method id>:...") is of a method
        whose service is service, and send nothing once ports.clock.monotonic() passes
        deadline."""
        sends = cls(ports, runtime, service, attempt_prefix, limit, deadline)
        sends.keys = await sends.listed()
        for key in sends.keys:
            directory, name = key[len(sends.prefix) :].rsplit("/", 1)
            number = int(name.removesuffix(".json"))
            sends.numbers[directory] = max(sends.numbers.get(directory, 0), number)
        return sends

    async def listed(self) -> list[str]:
        """The keys of the receipts under the attempt prefix of this service's methods."""
        return [
            key
            for key in await self.ports.store.list_prefix(self.prefix.rstrip("/"))
            if key.startswith(self.prefix)
            and (method := self.methods.get(key[len(self.prefix) :].split(":", 1)[0]))
            and method.service == self.service
        ]

    def receipts(self, directory: str) -> list[str]:
        """The keys of the receipts directly in directory when start() listed them."""
        return [key for key in self.keys if key[len(self.prefix) :].rsplit("/", 1)[0] == directory]

    async def send(
        self,
        item_id: str,
        method_ref: str,
        directory: str,
        request: dict[str, Any],
        parse: Callable[[str], Any],
        previous: list[dict[str, Any]] | None = None,
    ) -> Sent:
        """Send request with the service's transport complete() through the retry chain, and
        return parse's result for the first usable answer.

        Receipts, one per send, at requests/{request_id}/attempts/{run_id}/receipts/{directory}/
        {n}.json, n = 1, 2, ... per directory, after the highest taken. Written write-once before
        the send:
            {"item_id", "method": method_ref, "attempt": n,
             "params_digest": sha256 of the request body's compact sorted-key JSON,
             "sent_at": RFC 3339 UTC}
        rewritten after it with the same fields plus
            {"result": "ok" | "unavailable" | "invalid" | "refused", "reason": str | None,
             "latency_ms", "usage", "result_digest": sha256 of Completion.body | None,
             "model", "system_fingerprint"}   (the last four None when no Completion came back)
        Each completed send is counted by kp_processing.metrics.external_request. previous
        receipts (an earlier Activity attempt's, of the same chain) each count as one attempt
        used; one without "result" (the worker died between send and completion) counts as
        "unavailable".

        Retry chain (#93 §3.4):
          ServiceUnavailable(r)  result unavailable, reason r; send again after a backoff of
                                 min(retry.cap_s, retry.initial_s * retry.multiplier ** (u - 1))
                                 * uniform(0.5, 1.0) seconds on ports.clock, u = unavailable
                                 results so far
          Completion.refusal     result refused, reason MODEL_REFUSAL; never sent again
          parse raising InvalidOutput(r)  (content None is passed as "")
                                 result invalid, reason r; sent again at once the first time only
          parse returning        result ok; Sent.value
        The chain ends without a value, Sent.reason, with
          MODEL_REFUSAL          on a refusal
          EMPTY_OUTPUT | SCHEMA_INVALID   on the second invalid result (its reason)
          SERVICE_UNAVAILABLE    when retry.max_attempts sends exist and the last is not ok, or
                                 when the next send (after its backoff) would start past the
                                 deadline

        Errors (ProcessingFailure, all cause "platform", metadata {"item_id", ...}):
          no transport for the service                    configuration METHOD_UNAVAILABLE
          RequestRejected(status)                         configuration INFERENCE_REQUEST_REJECTED
                                                          (metadata also {"status"})
          a receipt number already taken (another worker
          sends the same chain in this attempt)           integrity     RECEIPT_CONFLICT
          a send beyond the limit (the service's receipts
          in the attempt, listed before each send, so
          Activities sending at once share it)            configuration REQUEST_CAP_EXCEEDED
                                                          (metadata also {"limit"})
          any exception from parse but InvalidOutput,
          or MethodUnavailable from the transport          method_failure()
        """
        retry, clock, transport = self.retry, self.ports.clock, self.transport
        previous = sorted(previous or [], key=lambda receipt: receipt["attempt"])
        attempts = len(previous)
        unavailable = sum(
            receipt.get("result", "unavailable") == "unavailable" for receipt in previous
        )
        invalid = sum(receipt.get("result") == "invalid" for receipt in previous)
        last_result = previous[-1].get("result", "unavailable") if previous else None
        last_reason = previous[-1].get("reason") if previous else None
        completions: list[Completion] = []
        value: Any = None
        params_digest = sha256(canonical_json(request))
        while True:
            if last_result == "refused":
                return Sent(None, "MODEL_REFUSAL", attempts, completions)
            if last_result == "invalid" and invalid >= 2:
                return Sent(None, last_reason, attempts, completions)
            if attempts >= retry["max_attempts"]:
                break
            delay = 0.0
            if last_result == "unavailable":
                delay = min(
                    retry["cap_s"],
                    retry["initial_s"] * retry["multiplier"] ** (unavailable - 1),
                ) * random.uniform(0.5, 1.0)
            if clock.monotonic() + delay > self.deadline:
                break
            if delay:
                await clock.sleep(delay)
            if transport is None:
                raise method_failure(
                    item_id, MethodUnavailable(f"{self.service} transport is not configured")
                )
            async with self.lock:
                if clock.monotonic() > self.deadline:
                    break
                if len(await self.listed()) >= self.limit:
                    raise ProcessingFailure(
                        "platform",
                        "configuration",
                        "REQUEST_CAP_EXCEEDED",
                        "External request cap exceeded",
                        metadata={"item_id": item_id, "limit": str(self.limit)},
                    )
                number = self.numbers.get(directory, 0) + 1
                self.numbers[directory] = number
                receipt: dict[str, Any] = {
                    "item_id": item_id,
                    "method": method_ref,
                    "attempt": number,
                    "params_digest": params_digest,
                    "sent_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                }
                receipt_ref = f"{self.prefix}{directory}/{number}.json"
                if not await self.ports.store.put_if_absent(receipt_ref, canonical_json(receipt)):
                    # Another worker is sending this chain in the same attempt.
                    raise ProcessingFailure(
                        "platform",
                        "integrity",
                        "RECEIPT_CONFLICT",
                        "External request receipt already exists",
                        metadata={"item_id": item_id},
                    )
            attempts += 1
            answer: Completion | None = None
            send_started = time.perf_counter()
            try:
                answer = await transport.complete(request)
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
                completions.append(answer)
                if answer.refusal:
                    last_result, last_reason = "refused", "MODEL_REFUSAL"
                else:
                    try:
                        value = await in_thread(parse, answer.content or "")
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
            await self.ports.store.put(receipt_ref, canonical_json(receipt))
            metrics.external_request(self.service, receipt["result"], receipt["reason"],
                                     latency_ms / 1000, receipt["usage"])  # fmt: skip
            if last_result == "ok":
                return Sent(value, None, attempts, completions)
        return Sent(None, "SERVICE_UNAVAILABLE", attempts, completions)
