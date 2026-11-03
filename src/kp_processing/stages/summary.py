"""The Document Summary on the summary worker (#155): three Activities around the
document_summary package, which shapes the output; kp_processing.summarize runs them from the
workflow under the summary budget.

    documents/{document_uid}/items/{key}/sections.json        summary_sections, write-once
    documents/{document_uid}/items/{key}/chunks/{index}.json  summary_chunk, write-once
    documents/{document_uid}/items/{key}/responses/{sha256}.json  every answer body, by digest
    documents/{document_uid}/items/{key}/record.json, outcome.json  summary_overview
"""

import asyncio
import dataclasses
import json
import math
from typing import Any, NoReturn

from kp_processing.identity import canonical_json
from kp_processing.methods import MethodOutput
from kp_processing.ports.object_store import ObjectStore
from kp_processing.profile import Method
from kp_processing.stages import (
    ChunkInput,
    EnrichInput,
    OutcomeRef,
    OverviewInput,
    Ports,
    ProcessingFailure,
    Runtime,
    SummaryPlan,
    enrichment_inputs,
    enrichment_key,
    in_thread,
    item_prefix,
    method_failure,
    read_verified,
    register,
    register_enrichment,
    registered,
    sha256,
)
from kp_processing.stages.enrich_vlm import Sends, register_transient

Steps = dict[str, dict[str, int]]


class NoAnswer(Exception):
    """A request's retry chain ended without a usable answer; reason is Sent.reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _method(runtime: Runtime) -> Method:
    (method,) = [m for m in runtime.profile.methods.values() if m.service == "summary"]
    return method


async def run_sections(input: EnrichInput, ports: Ports, runtime: Runtime) -> SummaryPlan:
    """The plan of the inventory's Document Summary item: the item of the profile's one method
    whose service is "summary".

    With the reuse key and prefix of enrich_local: when {prefix}/outcome.json is registered, the
    plan carries it (reused) and nothing else. Otherwise the package's sections(item, inputs) of
    the verified inputs is registered write-once at {prefix}/sections.json (the first writer's
    wins) and the plan carries it and the number of its chunks.

    Errors (ProcessingFailure, cause "platform", metadata {"item_id"}): an input missing or
    differing from its sha256, integrity INPUT_DIGEST_MISMATCH; any exception from the package,
    method_failure().
    """
    method = _method(runtime)
    inventory = json.loads(await ports.store.get(input.inventory.ref))
    (item,) = [item for item in inventory["items"] if item["method"] == method.id]
    item_id = item["item_id"]
    key = enrichment_key(input.document_uid, item, method)
    prefix = item_prefix(input.document_uid, key)
    if existing := await registered(ports.store, f"{prefix}/outcome.json"):
        return SummaryPlan(item_id, key, None, 0, OutcomeRef(item_id, existing.ref,
                                                             existing.digest, True))  # fmt: skip
    inputs = await enrichment_inputs(ports.store, item, {}, asyncio.Lock())
    try:
        document = await in_thread(method.package.sections, item, inputs)
    except Exception as exc:
        raise method_failure(item_id, exc) from exc
    sections = await register(ports.store, f"{prefix}/sections.json", canonical_json(document))
    if sections.reused:
        document = json.loads(await ports.store.get(sections.ref))
    return SummaryPlan(item_id, key, sections, len(document["chunks"]), None)


async def run_chunk(input: ChunkInput, ports: Ports, runtime: Runtime) -> None:
    """Write {prefix}/chunks/{index}.json, unless it exists: the package's chunk(document, index,
    ask) plus {"steps": {step: {"calls", "prompt_tokens", "completion_tokens"}}, "responses":
    [names under prefix]} of this call's answers. ask(step, request, parse) is Sends.send in
    directory "{item_id}/c{index}" (no deadline: the workflow's budget cancels the Activity),
    storing each answer body at {prefix}/responses/{sha256}.json before it returns.

    The cap counts the receipts of the summary method's items, limit request_cap.per_section x
    (summarized sections) + request_cap.extra.

    A chain that ended with MODEL_REFUSAL, EMPTY_OUTPUT or SCHEMA_INVALID writes {"failed":
    reason} with the steps and responses instead; one that ended with SERVICE_UNAVAILABLE raises
    NoAnswer, so that Temporal retries the Activity, and writes nothing.

    Errors: Sends.send's; the sections.json missing or differing from the plan's digest,
    integrity SECTIONS_MISSING; any other exception from the package, method_failure().
    """
    plan = input.plan
    prefix = item_prefix(input.enrich.document_uid, plan.key)
    ref = f"{prefix}/chunks/{input.index}.json"
    if await ports.store.head(ref) is not None:
        return
    method, document = await _document(ports.store, runtime, plan)
    sends = await _sends(ports, runtime, input.enrich, document, math.inf)
    steps: Steps = {}
    responses: list[str] = []
    ask = _ask(ports.store, sends, plan, method, f"{plan.item_id}/c{input.index}", prefix,
               steps, responses)  # fmt: skip
    try:
        result = await method.package.chunk(document, input.index, ask)
    except Exception as exc:
        error = _leaf(exc)
        if not isinstance(error, NoAnswer) or error.reason == "SERVICE_UNAVAILABLE":
            _raise(plan.item_id, error, exc)
        result = {"failed": error.reason}
    record = {**result, "steps": steps, "responses": responses}
    await ports.store.put_if_absent(ref, canonical_json(record))


async def run_overview(input: OverviewInput, ports: Ports, runtime: Runtime) -> OutcomeRef:
    """The Document Summary's outcome record, from every chunk's result.

    When input.complete is False, a failed SERVICE_UNAVAILABLE outcome is written by
    register_transient (requests/{request_id}/attempts/{run_id}/outcomes/{key}) without a call.
    When a chunk's result is {"failed": reason}, outcome failed with that reason is registered.
    Otherwise the package's overview(document, chunks, ask) runs, ask as in run_chunk with
    directory "{item_id}/overview" and no send starting later than input.budget_s after this
    call started. Its output is registered at the prefix with record.json: the package's record
    plus {"schema": "document-summary-record/v1", "steps": the chunks' and this call's summed,
    "responses": theirs and this call's}, named as provider_artifact_ref.

    A chain that ended with SERVICE_UNAVAILABLE makes the outcome transient, as above; one that
    ended otherwise registers outcome failed with its reason. Errors are run_chunk's.
    """
    started = ports.clock.monotonic()
    plan, enrich = input.plan, input.enrich
    prefix = item_prefix(enrich.document_uid, plan.key)
    transient = f"requests/{enrich.request_id}/attempts/{enrich.run_id}/outcomes/{plan.key}"
    method, document = await _document(ports.store, runtime, plan)
    unavailable = MethodOutput(outcome="failed", reason="SERVICE_UNAVAILABLE")
    if not input.complete:
        return await register_transient(ports.store, plan.item_id, method, transient, unavailable)
    chunks = [
        json.loads(await ports.store.get(f"{prefix}/chunks/{index}.json"))
        for index in range(plan.chunks)
    ]
    if failed := next((c["failed"] for c in chunks if "failed" in c), None):
        output = MethodOutput(outcome="failed", reason=failed)
        return await register_enrichment(ports.store, plan.item_id, method, prefix, output)
    sends = await _sends(ports, runtime, enrich, document, started + input.budget_s)
    steps: Steps = {}
    responses: list[str] = []
    for result in chunks:
        _add(steps, result["steps"])
        responses += result["responses"]
    ask = _ask(ports.store, sends, plan, method, f"{plan.item_id}/overview", prefix, steps,
               responses)  # fmt: skip
    try:
        output, record = await method.package.overview(document, chunks, ask)
    except Exception as exc:
        error = _leaf(exc)
        if not isinstance(error, NoAnswer):
            _raise(plan.item_id, error, exc)
        if error.reason == "SERVICE_UNAVAILABLE":
            return await register_transient(
                ports.store, plan.item_id, method, transient, unavailable
            )
        output = MethodOutput(outcome="failed", reason=error.reason)
        return await register_enrichment(ports.store, plan.item_id, method, prefix, output)
    record = {"schema": "document-summary-record/v1", **record, "steps": steps,
              "responses": responses}  # fmt: skip
    output = dataclasses.replace(
        output, files={"record.json": canonical_json(record)}, provider_artifact="record.json"
    )
    return await register_enrichment(ports.store, plan.item_id, method, prefix, output)


async def _document(
    store: ObjectStore, runtime: Runtime, plan: SummaryPlan
) -> tuple[Method, dict[str, Any]]:
    method = _method(runtime)
    assert plan.sections is not None  # run_sections planned this call

    def missing() -> ProcessingFailure:
        return ProcessingFailure(
            "platform",
            "integrity",
            "SECTIONS_MISSING",
            "Summary sections are missing or differ from their declared digest",
            metadata={"item_id": plan.item_id},
        )

    data = await read_verified(store, plan.sections.ref, plan.sections.digest, missing)
    return method, json.loads(data)


async def _sends(
    ports: Ports, runtime: Runtime, enrich: EnrichInput, document: dict[str, Any], deadline: float
) -> Sends:
    cap = runtime.profile.runtime["request_cap"]
    limit = cap["per_section"] * len(document["sections"]) + cap["extra"]
    attempt = f"requests/{enrich.request_id}/attempts/{enrich.run_id}"
    return await Sends.start(ports, runtime, "summary", attempt, limit, deadline)


def _ask(
    store: ObjectStore,
    sends: Sends,
    plan: SummaryPlan,
    method: Method,
    directory: str,
    prefix: str,
    steps: Steps,
    responses: list[str],
):
    async def ask(step: str, request: dict[str, Any], parse: Any) -> Any:
        sent = await sends.send(plan.item_id, method.ref, directory, request, parse)
        for completion in sent.completions:
            name = f"responses/{sha256(completion.body)}.json"
            await store.put_if_absent(f"{prefix}/{name}", completion.body)
            responses.append(name)
            usage = completion.usage
            counts = {
                "calls": 1,
                "prompt_tokens": usage.get("prompt_tokens") or 0,
                "completion_tokens": usage.get("completion_tokens") or 0,
            }
            _add(steps, {step: counts})
        if sent.value is None:
            raise NoAnswer(sent.reason or "SERVICE_UNAVAILABLE")
        return sent.value

    return ask


def _add(steps: Steps, more: Steps) -> None:
    for step, counts in more.items():
        entry = steps.setdefault(step, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0})
        for name, value in counts.items():
            entry[name] += value


def _leaf(error: BaseException) -> BaseException:
    """The first exception inside nested task-group exception groups."""
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return error


def _raise(item_id: str, error: BaseException, original: Exception) -> NoReturn:
    if isinstance(error, ProcessingFailure | NoAnswer):
        raise error from None
    raise method_failure(item_id, error if isinstance(error, Exception) else original) from original
