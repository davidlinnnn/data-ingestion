"""inventory: the enrichment inventory bound to one assembly (#129)."""

import json

from kp_processing.stages import InventoryInput, Ports, Registered, Runtime, sha256


async def run(input: InventoryInput, ports: Ports, runtime: Runtime) -> Registered:
    """Register documents/{document_uid}/items/{key}/inventory.json, where
    key = sha256 of "<profile id>|<assembly digest>":

        {"schema": "pdf-inventory/v1", "profile": "<profile id>",
         "assembly_ref": "...", "assembly_digest": "...", "items": []}

    Items stay empty until the profile's enrichment methods arrive (#132). Write-once;
    reused=True when it already existed.
    """
    profile = runtime.profile.profile
    key = sha256(f"{profile}|{input.assembly.digest}".encode())
    ref = f"documents/{input.document_uid}/items/{key}/inventory.json"
    if await ports.store.head(ref) is not None:
        return Registered(ref, sha256(await ports.store.get(ref)), True)
    body = json.dumps(
        {
            "schema": "pdf-inventory/v1",
            "profile": profile,
            "assembly_ref": input.assembly.ref,
            "assembly_digest": input.assembly.digest,
            "items": [],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    created = await ports.store.put_if_absent(ref, body)
    if not created:
        body = await ports.store.get(ref)
    return Registered(ref, sha256(body), not created)
