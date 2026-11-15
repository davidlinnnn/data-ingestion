"""check: the Quality Check on the d3 worker (#161, ADR-0011), after enrichment and before
finalize."""

import json
from functools import partial

from kp_canonicalization.methods import DocumentItem, InventoryItem
from kp_canonicalization.stages import (
    CheckInput,
    OutcomeRef,
    Ports,
    Runtime,
    outcome_record_missing,
    read_verified,
    registered,
)
from kp_canonicalization.stages.enrich_vlm import send_items


async def run(input: CheckInput, ports: Ports, runtime: Runtime) -> list[OutcomeRef]:
    """Judge the enrichment outcomes with the profile's Quality Check (its one method with
    Method.checks; see kp_canonicalization.methods), and record one outcome per check item.
    Returns one OutcomeRef per check item, in inventory order.

    A check item exists for each inventory item whose method ref is in Method.checks and
    whose outcome record (input.outcomes) says success; failed and no_text items are not judged:

        {"item_id": "<check id>:<judged item_id>", "method": "<check id>",
         "target_ref", "page", "bbox": the judged item's,
         "input_refs": one per kind of the Check's inputs}

    The items then go through enrich_vlm.send_items with service "d3": reuse of a registered
    outcome, the retry chain, receipts, the stage budget and the transient SERVICE_UNAVAILABLE
    outcome are the VLM items'. The cap counts the check items' receipts, limit
    request_cap.per_item x (inventory items + check items) + request_cap.extra.

    Errors: send_items', and (ProcessingFailure, platform, integrity, OUTCOME_RECORD_MISSING,
    metadata {"item_id"}) when a judged item has no OutcomeRef, its outcome record is missing
    or differs from its digest, or its first evidence file is not registered.
    """
    profile = runtime.profile
    method = profile.quality_check
    assert method is not None  # the workflow schedules this Activity only when plan.check
    inventory = json.loads(await ports.store.get(input.enrich.inventory.ref))
    outcomes = {outcome.item_id: outcome for outcome in input.outcomes}
    items: list[InventoryItem | DocumentItem] = []
    for judged in inventory["items"]:
        judged_method = profile.methods[judged["method"]]
        check = method.checks.get(judged_method.ref)
        if check is None:
            continue
        missing = partial(outcome_record_missing, judged["item_id"])
        outcome = outcomes.get(judged["item_id"])
        if outcome is None:
            raise missing()
        record = json.loads(await read_verified(ports.store, outcome.ref, outcome.digest, missing))
        if record["outcome"] != "success":
            continue
        input_refs = []
        for kind in check.inputs:
            if kind == "outcome":
                input_refs.append({"ref": outcome.ref, "sha256": outcome.digest})
            elif kind == "evidence":
                evidence = await registered(ports.store, record["evidence_refs"][0])
                if evidence is None:
                    raise missing()
                input_refs.append({"ref": evidence.ref, "sha256": evidence.digest})
            else:
                index = judged_method.package.INPUTS.index(kind)
                input_refs.append(judged["input_refs"][index])
        items.append(
            {
                "item_id": f"{method.id}:{judged['item_id']}",
                "method": method.id,
                "target_ref": judged["target_ref"],
                "page": judged["page"],
                "bbox": judged["bbox"],
                "input_refs": input_refs,
            }
        )
    counted = len(inventory["items"]) + len(items)
    return await send_items(input.enrich, ports, runtime, "d3", items, counted)
