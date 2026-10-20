"""Bound whole-item substitutions; source semantic quality is a separate review.

``bind_scope`` freezes native targets/context. ``bind_input`` freezes the exact
image/request and scope; ``bind_response`` records that association. ``apply``
validates a response for that unchanged contract, and ``render_batch`` replaces
only the declared serializer boundaries. No lexical content gate is used.
"""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

from docling_core.types.doc import DoclingDocument

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parser = _load("context_adapter_frozen_parser", REPO / "docs/research/pdf-core-g2-inline-api-2026-10-15/parsed/parse.py")
renderer = _load("context_adapter_frozen_renderer", REPO / "docs/research/pdf-core-g2-inline-boundary-2026-10-15/reinsertion/apply.py")
ROLES = {"text": "paragraph", "section_header": "heading", "code": "code", "formula": "formula",
         "caption": "caption", "footnote": "footnote", "list_item": "list_item", "unspecified": "other"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def item(raw, reference):
    if not isinstance(reference, str) or not re.fullmatch(r"#/([a-z_]+)/([0-9]+)", reference):
        raise ValueError("foreign or malformed item reference")
    collection, index = reference[2:].split("/")
    try:
        result = raw[collection][int(index)]
    except (KeyError, IndexError, TypeError):
        raise ValueError("foreign or missing item reference") from None
    if not isinstance(result, dict) or result.get("self_ref") != reference:
        raise ValueError("item identity differs from its exact reference")
    return result


def _references(values):
    if not isinstance(values, (list, tuple)) or any(not isinstance(v, str) for v in values):
        raise ValueError("item refs must be a list of exact strings")
    if len(set(values)) != len(values):
        raise ValueError("duplicate item refs")
    return list(values)


def _entry(raw, reference):
    native = item(raw, reference)
    text = native.get("text")
    span = None
    if isinstance(text, str):
        span = [0, len(text)]
        cursor = 0
        for prov in native.get("prov", []):
            bounds = prov.get("charspan")
            if (not isinstance(bounds, list) or len(bounds) != 2
                    or any(isinstance(n, bool) or not isinstance(n, int) for n in bounds)):
                raise ValueError("invalid native provenance charspan")
            start, end = bounds
            if not cursor <= start <= end <= len(text) or text[cursor:start].strip():
                raise ValueError("overlapping or incomplete native charspan coverage")
            cursor = end
        if text[cursor:].strip():
            raise ValueError("unlocated native text suffix")
    return {"item_ref": reference, "item_sha256": digest(native), "native_label": native.get("label"),
            "replacement_charspan": span, "provider_provenance": deepcopy(native.get("prov", []))}


def _descendants(raw, reference):
    result, pending = set(), [reference]
    while pending:
        current = pending.pop()
        if current in result:
            raise ValueError("cyclic or duplicate child ownership")
        result.add(current)
        for child in item(raw, current).get("children", []):
            child_ref = child.get("$ref")
            if item(raw, child_ref).get("parent", {}).get("$ref") != current:
                raise ValueError("nonreciprocal child ownership")
            pending.append(child_ref)
    return result


def bind_scope(raw, targetrefs, contextrefs):
    """Freeze full native identities, including every formula-envelope member."""
    targets, contexts = _references(targetrefs), _references(contextrefs)
    if not targets or set(targets) & set(contexts):
        raise ValueError("empty targets or context item consumed as target")
    target_entries, members, effects, roles = [], [], [], []
    for reference in targets:
        native = item(raw, reference)
        subtree = _descendants(raw, reference)
        if any(subtree & previous for previous in effects):
            raise ValueError("overlapping target subtrees")
        effects.append(subtree)
        target_entries.append(_entry(raw, reference))
        if native.get("label") == "picture":
            children = [child["$ref"] for child in native.get("children", [])]
            if (not children or any(item(raw, r).get("label") != "formula"
                                    or item(raw, r).get("children") for r in children)):
                raise ValueError("picture target is not a bounded direct-formula envelope")
            pages = {p["page_no"] for r in [reference, *children] for p in item(raw, r).get("prov", [])}
            if len(pages) != 1 or any(not item(raw, r).get("prov") for r in [reference, *children]):
                raise ValueError("formula envelope lacks one-page provenance")
            members.extend(_entry(raw, r) for r in children)
            roles.append("formula")
        else:
            if native.get("children") or native.get("label") not in ROLES or not isinstance(native.get("text"), str):
                raise ValueError("unsupported native target role or child structure")
            roles.append(ROLES[native["label"]])
    consumed = set().union(*effects)
    for reference in contexts:
        if _descendants(raw, reference) & consumed:
            raise ValueError("context overlaps consumed target subtree")
    parents = [raw[key] for key in ("body", "furniture") if key in raw]
    for key in ("groups", "texts", "pictures", "tables", "key_value_items", "form_items"):
        parents.extend(raw.get(key, []))
    for reference in consumed | set(contexts):
        owners = [parent["self_ref"] for parent in parents
                  for child in parent.get("children", []) if child.get("$ref") == reference]
        if owners != [item(raw, reference).get("parent", {}).get("$ref")]:
            raise ValueError("target/member/context ownership is not unique and reciprocal")
    scope = {"format": "g2-bound-whole-native-scope-v1", "document_sha256": digest(raw),
             "target_item_refs": targets, "context_only_refs": contexts, "targets": target_entries,
             "members": members, "context": [_entry(raw, r) for r in contexts],
             "consumption_effect_refs": sorted(consumed), "expected_block_roles": roles}
    return {**scope, "scope_sha256": digest(scope)}


def validate_scope(raw, scope):
    if bind_scope(raw, scope["target_item_refs"], scope["context_only_refs"]) != scope:
        raise ValueError("stale document, changed scope, target span, role, member, or context")


def bind_input(scope, *, image_sha256, image_pixels_wh, request_sha256, manifest_row_sha256):
    """Create before inference; image, prompt/request, targets and contexts are inseparable."""
    for value in (image_sha256, request_sha256, manifest_row_sha256, scope["scope_sha256"]):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("input contract requires exact SHA-256 identities")
    if (not isinstance(image_pixels_wh, list) or len(image_pixels_wh) != 2
            or any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in image_pixels_wh)):
        raise ValueError("input contract requires positive integer image dimensions")
    contract = {"format": "g2-exact-inference-input-v1", "scope_sha256": scope["scope_sha256"],
                "image_sha256": image_sha256, "image_pixels_wh": image_pixels_wh,
                "request_sha256": request_sha256, "manifest_row_sha256": manifest_row_sha256,
                "output_policy": "exactly_one_compatible_block_per_target_in_target_order_context_not_output"}
    return {**contract, "input_fingerprint": digest(contract)}


def bind_response(contract, output, *, response_sha256):
    if not re.fullmatch(r"[0-9a-f]{64}", response_sha256):
        raise ValueError("response record requires exact response SHA-256")
    return {"input_fingerprint": contract["input_fingerprint"], "response_sha256": response_sha256,
            "output_sha256": digest(output), "data": deepcopy(output)}


def apply(raw, scope, contract, response, *, expected_input_fingerprint, proposal_id):
    """Accept structure only; never infer source truth from native/model vocabulary."""
    validate_scope(raw, scope)
    expected = bind_input(scope, **{key: contract[key] for key in
                          ("image_sha256", "image_pixels_wh", "request_sha256", "manifest_row_sha256")})
    if (contract != expected or response["input_fingerprint"] != contract["input_fingerprint"]
            or expected_input_fingerprint != contract["input_fingerprint"]):
        raise ValueError("needs_new_inference: image/request/target/context fingerprint differs")
    output = response["data"]
    if digest(output) != response["output_sha256"]:
        raise ValueError("saved model output changed after response association")
    parser.validate(output, contract["image_pixels_wh"])
    if any(s["kind"] == "unknown" or s["text"] is None for b in output["blocks"] for s in b["segments"]):
        raise ValueError("unknown/null source segments remain")
    if [b["kind"] for b in output["blocks"]] != scope["expected_block_roles"]:
        raise ValueError("model block count or role differs from exact native target roles")
    markdown, offsets = parser.render(output)
    proposal = {"id": proposal_id, "consumed_item_refs": scope["target_item_refs"], "markdown": markdown,
                "scope": deepcopy(scope), "input_contract": deepcopy(contract), "response_record": deepcopy(response),
                "segment_offsets": offsets, "structural_application_is_not_semantic_acceptance": True}
    renderer.render(DoclingDocument.model_validate(raw), [proposal])
    return proposal


def render_batch(raw, proposals):
    """Reuse frozen marker substitution and prove all other literal spans unchanged."""
    before = digest(raw)
    effects = set()
    for proposal in proposals:
        verified = apply(raw, proposal["scope"], proposal["input_contract"], proposal["response_record"],
                         expected_input_fingerprint=proposal["input_contract"]["input_fingerprint"], proposal_id=proposal["id"])
        if verified != proposal:
            raise ValueError("proposal content or consumed targets changed after validation")
        current = set(proposal["scope"]["consumption_effect_refs"])
        if effects & current:
            raise ValueError("duplicate or overlapping replacement scopes")
        effects.update(current)
    document = DoclingDocument.model_validate(raw)
    baseline = document.export_to_markdown()
    if renderer.render(document, [])[0] != baseline:
        raise ValueError("frozen renderer differs from stock baseline")
    working, spans, outside = renderer.render(document, proposals)
    native = [{**p, "markdown": None} for p in proposals]
    for proposal in native:
        reference = proposal["consumed_item_refs"][0]
        # The same markers establish literal boundaries before and after substitution.
        proposal["markdown"] = "NATIVEBOUNDARY" + hashlib.sha256(reference.encode()).hexdigest()
    _, _, original_outside = renderer.render(document, native)
    if [s["sha256"] for s in outside] != [s["sha256"] for s in original_outside]:
        raise ValueError("outside serialized literals changed")
    if digest(raw) != before:
        raise ValueError("original provider graph mutated")
    return {"baseline": baseline, "working": working, "replacement_spans": spans,
            "outside_literal_spans": outside, "provider_document_sha256": before,
            "provider_graph_unchanged": True, "outside_literal_spans_unchanged": True,
            "structural_application_is_not_semantic_acceptance": True}
