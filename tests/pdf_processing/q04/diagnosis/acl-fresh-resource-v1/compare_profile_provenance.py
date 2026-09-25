"""Build the retained ACL reference/current method comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def method_digest(value: Any) -> str:
    """Use the exact JSON identity convention recorded by T09a R3."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def compare(r3_methods: dict[str, dict], bundle: dict) -> dict:
    if len(r3_methods) != 1:
        raise ValueError("R3 method evidence must identify one actual method")
    reference_sha, reference_method = next(iter(r3_methods.items()))
    if method_digest(reference_method) != reference_sha:
        raise ValueError("R3 method evidence hash does not match its payload")
    current_method = bundle["base_profile"]["method"]
    current_without_continuation = {
        key: value for key, value in current_method.items() if key != "continuation"
    }
    fixture = next(value for value in bundle["fixtures"] if value["id"] == "09")
    return {
        "reference_provenance": {
            "run_id": "20260914-0b537d0-c",
            "trial": "fresh-09",
            "document_sha256": "aaa62538d423472fd4999675fdcd39501eaa11bce89d630843c8609177533c6c",
            "actual_method_sha256": reference_sha,
            "profile_has_continuation_attestation": "continuation"
            in reference_method,
        },
        "current_provenance": {
            "document_sha256": "ff3cdcb6142e7046f5e248827548a1cd303f68c9317b2488d9dd251805c3f506",
            "actual_method_sha256": method_digest(current_method),
            "profile_continuation": current_method.get("continuation"),
            "producer": bundle["producer"],
        },
        "profile_comparison": {
            "all_non_continuation_fields_equal": current_without_continuation
            == reference_method,
            "only_current_field_added": (
                "continuation"
                if current_without_continuation == reference_method
                else None
            ),
            "reference_and_current_method_hash_equal": reference_method
            == current_method,
            # Retain the complete common packages/models/options/platform/Python
            # payload so the field-level equality is reviewable without trust in
            # the derived boolean above.
            "shared_non_continuation_method": (
                reference_method
                if current_without_continuation == reference_method
                else None
            ),
        },
        "source": {
            "id": fixture["id"],
            "name": fixture["name"],
            "source_revision": fixture["source_revision"],
            "original_sha256": fixture["original_sha256"],
            "sha256": fixture["sha256"],
            "original_pages": fixture["original_pages"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r3-methods", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = compare(
        json.loads(args.r3_methods.read_text()),
        json.loads(args.bundle.read_text()),
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
