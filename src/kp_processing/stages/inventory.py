"""inventory: the enrichment inventory bound to one assembly (#129)."""

from kp_processing.stages import InventoryInput, Ports, Registered, Runtime


async def run(input: InventoryInput, ports: Ports, runtime: Runtime) -> Registered:
    """Register documents/{document_uid}/items/{key}/inventory.json, where
    key = sha256 of "<profile id>|<assembly digest>":

        {"schema": "pdf-inventory/v1", "profile": "<profile id>",
         "assembly_ref": "...", "assembly_digest": "...", "items": []}

    Items stay empty until the profile's enrichment methods arrive (#132). Write-once;
    reused=True when it already existed.
    """
    raise NotImplementedError
