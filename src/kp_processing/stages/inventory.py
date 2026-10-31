"""inventory: the enrichment inventory bound to one assembly (#129)."""

import asyncio
import json

from kp_processing.stages import (
    InventoryInput,
    InventoryRef,
    Ports,
    Runtime,
    register,
    registered,
    sha256,
)


async def run(input: InventoryInput, ports: Ports, runtime: Runtime) -> InventoryRef:
    """Register documents/{document_uid}/items/{key}/inventory.json, where
    key = sha256 of "<profile id>|<assembly digest>":

        {"schema": "pdf-inventory/v1", "profile": "<profile id>",
         "assembly_ref": "...", "assembly_digest": "...", "items": [...]}

    One item per enrichment target of each item-scope method the profile lists, grouped by
    method in profile order, then in document order:

        {"item_id": "<method id>:<target_ref>", "method": "<method id>",
         "target_ref": "#/pictures/0", "page": 1, "bbox": {l, t, r, b, coord_origin},
         "input_refs": [{"ref", "sha256"}, ...]}

    picture-ocr    every picture   input_refs [its registered picture image]
    code           every text with label "code"   input_refs [the source PDF]
    table-status   every table     input_refs [assembly.json, the image of the table's page]

    page and bbox are the target's first provenance entry as docling dumps it. Write-once;
    reused=True when it already existed.
    """
    profile = runtime.profile.profile
    key = sha256(f"{profile}|{input.assembly.digest}".encode())
    ref = f"documents/{input.document_uid}/items/{key}/inventory.json"
    if existing := await registered(ports.store, ref):
        body = json.loads(await ports.store.get(existing.ref))
        return InventoryRef(existing.ref, existing.digest, True, len(body["items"]))

    assembly = await asyncio.to_thread(json.loads, await ports.store.get(input.assembly.ref))
    document = assembly["document"]
    pictures = {picture["picture_id"]: picture for picture in assembly["picture_images"]}
    page_images = {}
    for group in input.groups:
        for image in json.loads(await ports.store.get(group.ref))["page_images"]:
            page_images[image["page"]] = image
    targets = {
        "picture-ocr": document["pictures"],
        "code": [text for text in document["texts"] if text["label"] == "code"],
        "table-status": document["tables"],
    }
    items = []
    for method_id in runtime.profile.methods:
        for target in targets.get(method_id, []):
            target_ref = target["self_ref"]
            provenance = target["prov"][0]
            page = provenance["page_no"]
            if method_id == "picture-ocr":
                picture = pictures[target_ref]
                refs = [{"ref": picture["ref"], "sha256": picture["sha256"]}]
            elif method_id == "code":
                refs = [{"ref": input.source_key, "sha256": input.source_sha256}]
            else:
                image = page_images[page]
                refs = [
                    {"ref": input.assembly.ref, "sha256": input.assembly.digest},
                    {"ref": image["ref"], "sha256": image["sha256"]},
                ]
            items.append(
                {
                    "item_id": f"{method_id}:{target_ref}",
                    "method": method_id,
                    "target_ref": target_ref,
                    "page": page,
                    "bbox": provenance["bbox"],
                    "input_refs": refs,
                }
            )
    data = json.dumps(
        {
            "schema": "pdf-inventory/v1",
            "profile": profile,
            "assembly_ref": input.assembly.ref,
            "assembly_digest": input.assembly.digest,
            "items": items,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    result = await register(ports.store, ref, data)
    count = len(items)
    if result.reused:
        count = len(json.loads(await ports.store.get(result.ref))["items"])
    return InventoryRef(result.ref, result.digest, result.reused, count)
