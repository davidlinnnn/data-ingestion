"""inventory: the enrichment inventory bound to one assembly (#129)."""

from kp_processing.stages import InventoryInput, InventoryRef, Ports, Runtime


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
    raise NotImplementedError
