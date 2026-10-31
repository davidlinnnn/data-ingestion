"""inventory: the enrichment inventory bound to one assembly (#129)."""

import asyncio
import json

from kp_processing.methods import InventoryItem
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

    One InventoryItem per target of each item-scope method the profile lists (a method
    package that declares TARGET), grouped by method in profile order, then in document
    order; input_refs follow the package's INPUTS. Write-once; reused=True when it already
    existed.
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

    def source(kind: str, target_ref: str, page: int) -> dict[str, str]:
        match kind:
            case "source":
                return {"ref": input.source_key, "sha256": input.source_sha256}
            case "assembly":
                return {"ref": input.assembly.ref, "sha256": input.assembly.digest}
            case "picture_image":
                return {key: pictures[target_ref][key] for key in ("ref", "sha256")}
            case "page_image":
                return {key: page_images[page][key] for key in ("ref", "sha256")}
        raise ValueError(f"Unknown input kind {kind}")

    items: list[InventoryItem] = []
    for method_id, method in runtime.profile.methods.items():
        package = method.package
        if not hasattr(package, "TARGET"):
            continue
        collection, label = package.TARGET
        for target in document[collection]:
            if label is not None and target["label"] != label:
                continue
            target_ref = target["self_ref"]
            provenance = target["prov"][0]
            page = provenance["page_no"]
            items.append(
                {
                    "item_id": f"{method_id}:{target_ref}",
                    "method": method_id,
                    "target_ref": target_ref,
                    "page": page,
                    "bbox": provenance["bbox"],
                    "input_refs": [source(kind, target_ref, page) for kind in package.INPUTS],
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
