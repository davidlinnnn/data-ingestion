"""Offline proposal: preserve native caption ownership and retain observations."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
FROZEN = Path(__file__).resolve().parent.parent / "pdf-core-direct-cell-2026-10-17"
spec = importlib.util.spec_from_file_location("frozen_cell_adapter", FROZEN / "adapter.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def map_preserving_ownership(baseline, response, page_no, registered_keys):
    parsed = adapter.parse_response(response, registered_keys)
    original = {target.target_key: target for target in parsed.targets}
    safe = parsed.model_dump(mode="json")
    # Missing native links do not establish that a source caption is absent.
    for target in safe["targets"]:
        target["caption"] = ""
    doc, bindings = adapter.map_response(baseline, safe, page_no, registered_keys)
    native = adapter.inventory(baseline, page_no)
    for binding in bindings:
        key = binding["target_key"]
        provider = original[key].model_dump(mode="json")
        binding["provider"] = deepcopy(provider)
        linked = bool(native[key].captions)
        binding["caption_ownership"] = {
            "native_link_preserved": linked,
            "provider_caption_applied": False,
            "provider_caption_observation": provider["caption"],
            "unresolved_provider_observation": bool(provider["caption"] and not linked),
            "status": "native_ownership_preserved" if linked else (
                "unresolved_provider_observation" if provider["caption"] else
                "no_native_link_or_provider_observation"),
            "source_completeness_verified": False,
        }
    return doc, bindings
