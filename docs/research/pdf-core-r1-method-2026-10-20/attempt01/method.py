"""Public-Core source-group transport prototype; no inference or semantic repair."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument, ProvenanceItem, BoundingBox

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("r1_public_fragment", ROOT / "docs/research/pdf-core-stage1-followup-2026-10-17/A/method.py")
image_types = load("r1_existing_picture_types", ROOT / "docs/research/pdf-core-eval-interfaces-2026-10-18/C/producer.py")


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def groups(raw, component):
    """Page connectivity is native provenance only, never text/figure semantics."""
    doc = DoclingDocument.model_validate(raw)
    components = [{p} for p in sorted(doc.pages)]
    owners = doc.texts if component == "A" else doc.pictures
    for owner in owners:
        pages = {p.page_no for p in owner.prov}
        linked = [g for g in components if g & pages]
        if linked:
            joined = set().union(*linked)
            components = [g for g in components if g not in linked] + [joined]
    if component == "C":
        components = [g for g in components if any(g & {p.page_no for p in x.prov} for x in doc.pictures)]
    return sorted([sorted(g) for g in components])


def bind(raw, pages, views, images=()):
    doc = DoclingDocument.model_validate(raw)
    pages = sorted(pages)
    if not pages or len(pages) != len(set(pages)) or not set(pages) <= set(doc.pages):
        raise ValueError("missing, duplicate or foreign page")
    if sorted(v["page_no"] for v in views) != pages:
        raise ValueError("missing or duplicate source view")
    candidates = []
    for item in doc.texts:
        touched = {p.page_no for p in item.prov}
        if touched & set(pages):
            if not touched <= set(pages) or item.children:
                raise ValueError("partial owner/page or non-leaf source requires explicit support")
            candidates.append(item.self_ref)
    rendered = old.serialize(doc)
    visible = {s.item.self_ref for s in rendered.spans}
    anchors = []
    for item in [*doc.texts, *doc.pictures, *doc.tables]:
        parent = item.parent.resolve(doc) if item.parent else None
        floating = False
        while parent and parent.self_ref not in {"#/body", "#/furniture"}:
            floating |= parent.self_ref.startswith(("#/pictures/", "#/tables/"))
            parent = parent.parent.resolve(doc) if parent.parent else None
        if (item.self_ref in visible and not floating
                and any(p.page_no in pages for p in item.prov)):
            anchors.append(item.self_ref)
    image_records = []
    for image in images:
        ref = image["owner_ref"]
        picture = old.resolve(doc, ref)
        if (not ref.startswith("#/pictures/") or image["document_revision"] != digest(raw)
                or image["image_key"] != digest([digest(raw), ref, image["crop_sha256"]])
                or not {p.page_no for p in picture.prov} <= set(pages)):
            raise ValueError("foreign/stale image or crop identity")
        image_records.append(deepcopy(image))
    if len({x["image_key"] for x in image_records}) != len(image_records):
        raise ValueError("duplicate image key")
    return {"method": "source-group-v1", "document_revision": digest(raw), "pages": pages,
        "views": deepcopy(views), "text_candidates": candidates, "visible_anchors": anchors,
        "images": image_records, "context_key": digest([digest(raw), pages, views]),
        "source_precision": "page-envelope; native owner geometry retained separately"}


def provenance(doc, pages):
    return [ProvenanceItem(page_no=p, bbox=BoundingBox(l=0, t=0,
        r=doc.pages[p].size.width, b=doc.pages[p].size.height, coord_origin="TOPLEFT"),
        charspan=(0, 0)) for p in pages]


def stable_content(item):
    value = item.model_dump(mode="json", by_alias=True)
    return {k: v for k, v in value.items() if k not in {"self_ref", "parent", "children", "captions", "footnotes", "references"}}


def apply(raw, bound, response):
    if bound != bind(raw, bound["pages"], bound["views"], bound["images"]):
        raise ValueError("stale source group")
    if set(response) != {"group_sha256", "keep", "actions"} or response["group_sha256"] != digest(bound):
        raise ValueError("foreign group or unknown response fields")
    doc = DoclingDocument.model_validate(raw)
    originals = {x.self_ref: x for x in [*doc.texts, *doc.pictures, *doc.tables]}
    kept = response["keep"]
    actions = response["actions"]
    consumed = [ref for action in actions for ref in action["consume"]]
    if (len(kept) != len(set(kept)) or len(consumed) != len(set(consumed))
            or set(kept) & set(consumed)
            or Counter(kept + consumed) != Counter(bound["text_candidates"])):
        raise ValueError("missing, duplicate or foreign source disposition")
    ids = [a["id"] for a in actions]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate action identity")
    captions = {r.cref: x for x in [*doc.pictures, *doc.tables] for r in x.captions}
    non_targets = {ref: stable_content(x) for ref, x in originals.items() if ref not in consumed}
    before_order = [id(x) for x, _ in doc.iterate_items() if x.self_ref in non_targets]
    caption_edges = {id(x): [id(r.resolve(doc)) for r in x.captions] for x in [*doc.pictures, *doc.tables]}
    inserted, binding, remove = [], [], []
    after_positions = {}
    for action in actions:
        if set(action) != {"id", "consume", "evidence_refs", "source_pages", "placement", "blocks"}:
            raise ValueError("unknown action fields")
        if not action["blocks"] or not action["evidence_refs"]:
            raise ValueError("empty output or unbound pixel reconstruction")
        evidence = set(action["evidence_refs"])
        if not evidence <= set(originals) or not set(action["consume"]) <= evidence:
            raise ValueError("unknown or incomplete source evidence")
        pages = action["source_pages"]
        required = {p.page_no for ref in evidence for p in originals[ref].prov}
        if (not pages or len(pages) != len(set(pages)) or not required <= set(pages)
                or not set(pages) <= set(bound["pages"])):
            raise ValueError("missing or foreign source page/fragment")
        placement = action["placement"]
        if set(placement) != {"reference", "side"} or placement["side"] not in {"before", "after"}:
            raise ValueError("invalid output placement")
        anchor = placement["reference"]
        if anchor not in bound["visible_anchors"]:
            raise ValueError("unreachable or foreign output anchor")
        if not action["consume"] and not any(ref.startswith("#/pictures/") for ref in evidence):
            raise ValueError("new occurrence requires explicit retained picture evidence")
        caption_sources = [ref for ref in action["consume"] if ref in captions]
        if caption_sources and (len(action["consume"]) != 1 or len(action["blocks"]) != 1):
            raise ValueError("caption edge cannot be merged with unrelated source owners")
        for block_index, block in enumerate(action["blocks"]):
            if set(block) != {"kind", "segments"}:
                raise ValueError("unknown block fields")
            temp, root = old.block_document({**block, "fragment_indices": list(range(len(pages)))},
                provenance(doc, pages))
            for text in temp.texts:
                text.orig = ""
            if caption_sources:
                if block["kind"] != "paragraph":
                    raise ValueError("caption replacement must retain its source role")
                target = originals[caption_sources[0]]
                target.text = old.serialize(temp).text
                target.prov = root.prov
                derived = target
            else:
                sibling = after_positions.get(anchor, originals[anchor]) if placement["side"] == "after" else originals[anchor]
                parent = sibling.parent.resolve(doc)
                before = {id(r.resolve(doc)) for r in parent.children}
                doc.insert_node_items(sibling=sibling, node_items=[root], doc=temp, after=placement["side"] == "after")
                new = [r.resolve(doc) for r in parent.children if id(r.resolve(doc)) not in before]
                if len(new) != 1:
                    raise ValueError("ambiguous public Core insertion")
                derived = new[0]
                if placement["side"] == "after":
                    after_positions[anchor] = derived
                inserted.append(derived)
            binding.append({"action": action["id"], "block": block_index, "item": derived,
                "evidence_refs": list(action["evidence_refs"]), "source_pages": list(pages),
                "native_source": {ref: deepcopy(raw[ref.split('/')[1]][int(ref.split('/')[2])]) for ref in evidence},
                "precision": "page-envelope", "charspans_are_derived_not_native": True})
        remove.extend(originals[r] for r in action["consume"] if r not in captions)
    if remove:
        doc.delete_items(node_items=remove)
    doc.validate_tree(doc.body, raise_on_error=True)
    for ref, expected in non_targets.items():
        if stable_content(originals[ref]) != expected:
            raise ValueError("non-target source content changed")
    protected_ids = {id(originals[r]) for r in non_targets}
    if [id(x) for x, _ in doc.iterate_items() if id(x) in protected_ids] != before_order:
        raise ValueError("non-target source reading order changed")
    for x in [*doc.pictures, *doc.tables]:
        if caption_edges[id(x)] != [id(r.resolve(doc)) for r in x.captions]:
            raise ValueError("original caption edge changed")
    rendered = old.serialize(doc)
    refs = {s.item.self_ref for s in rendered.spans}
    if any(row["item"].self_ref not in refs for row in binding):
        raise ValueError("reconstructed content not delivered in stock Markdown")
    for row in binding:
        row["derived_ref"] = row.pop("item").self_ref
    return {"document": doc.model_dump(mode="json", by_alias=True), "markdown": rendered.text,
        "binding": {"group": bound, "outputs": binding}, "raw_response": deepcopy(response),
        "source_quality_verified": False, "new_model_calls": 0}


def supplement(raw, bound, responses):
    if bound != bind(raw, bound["pages"], bound["views"], bound["images"]):
        raise ValueError("stale source context")
    if set(responses) != {x["image_key"] for x in bound["images"]}:
        raise ValueError("missing or foreign picture work")
    records = []
    for image in bound["images"]:
        value = responses[image["image_key"]]
        if set(value) != {"context_key", "image_ocr", "context_ocr", "description", "chart"} or value["context_key"] != bound["context_key"]:
            raise ValueError("wrong context or incomplete required work")
        for name in ("image_ocr", "context_ocr"):
            observation = value[name]
            if (set(observation) != {"scope", "text", "status"}
                    or observation["scope"] != ("crop" if name == "image_ocr" else "page_context")
                    or observation["status"] not in {"ok", "no_text", "unreadable"}
                    or not isinstance(observation["text"], str)
                    or (observation["status"] == "ok" and not observation["text"].strip())
                    or (observation["status"] == "no_text" and observation["text"])):
                raise ValueError("OCR source view/state is not explicit")
        image_types.Description.model_validate(value["description"])
        image_types.Chart.model_validate(value["chart"])
        records.append({"image": deepcopy(image), "context": deepcopy(bound["views"]),
            "source_precision": "crop envelope or full-page context, as labeled",
            "observations": deepcopy(value), "raw_provider_payload": deepcopy(value)})
    return {"method": "source-group-v1", "document_revision": digest(raw),
        "context_key": bound["context_key"], "images": records,
        "source_quality_verified": False, "model_calls": 0}
