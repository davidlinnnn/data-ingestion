"""Offline public-Core fragment ordering gate; no model, oracle or renderer."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from docling_core.transforms.serializer.markdown import MarkdownDocSerializer
from docling_core.types.doc import ContentLayer, DoclingDocument, DocItemLabel, RefItem

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def resolve(doc, reference):
    return RefItem(cref=reference).resolve(doc)


def serialize(doc):
    return MarkdownDocSerializer(doc=doc).serialize()


def scope(raw, targets):
    doc = DoclingDocument.model_validate(raw)
    doc.validate_tree(doc.body, raise_on_error=True)
    if not targets or len(set(targets)) != len(targets):
        raise ValueError("empty or duplicate targets")
    items = [resolve(doc, ref) for ref in targets]
    if any(not ref.startswith("#/texts/") or item.children or not item.prov
           for ref, item in zip(targets, items, strict=True)):
        raise ValueError("requires leaf text owners with complete native provenance")
    parents = {item.parent.cref for item in items if item.parent}
    if len(parents) != 1:
        raise ValueError("ordered scope requires one native parent")
    parent = resolve(doc, next(iter(parents)))
    caption_refs = {ref.cref for owner in [*doc.tables, *doc.pictures] for ref in owner.captions}
    if parent.label in {DocItemLabel.PICTURE, DocItemLabel.TABLE} or caption_refs.intersection(targets):
        raise ValueError("caption/picture child needs its own render owner")
    children = [ref.cref for ref in parent.children]
    if any(children.count(ref) != 1 for ref in targets):
        raise ValueError("nonreciprocal or duplicate ownership")
    for item in items:
        native_prov = raw["texts"][int(item.self_ref.rsplit("/", 1)[1])]["prov"]
        if [prov.model_dump(mode="json") for prov in item.prov] != native_prov:
            raise ValueError("source geometry was normalized by Core validation")
        for prov in item.prov:
            if prov.page_no not in doc.pages:
                raise ValueError("missing source page")
            size = doc.pages[prov.page_no].size
            box = prov.bbox.to_top_left_origin(page_height=size.height)
            if not (0 <= box.l < box.r <= size.width and 0 <= box.t < box.b <= size.height):
                raise ValueError("invalid source geometry")
    return {"format": "public-core-fragment-order-v1", "document_sha256": digest(raw),
            "targets": list(targets), "parent_ref": parent.self_ref,
            "anchors": [ref for ref in children if ref not in targets],
            "provenance": {ref: deepcopy(raw["texts"][int(ref.rsplit("/", 1)[1])]["prov"])
                           for ref in targets}}


def block_document(block, provenance, label=DocItemLabel.TEXT, native=None):
    if set(block) != {"fragment_indices", "kind", "segments"}:
        raise ValueError("unknown or missing block fields")
    segments = block["segments"]
    if block["kind"] not in {"paragraph", "heading", "formula", "code"} or not segments:
        raise ValueError("invalid or empty block")
    if any(set(s) != {"kind", "text"} or s["kind"] not in {"text", "math", "code"}
           or not isinstance(s["text"], str) or not s["text"] for s in segments):
        raise ValueError("unresolved, empty or invalid segment")
    temp = DoclingDocument(name="derived-fragment")
    text = "".join(s["text"] for s in segments)
    kind = block["kind"]
    if kind == "formula":
        root = temp.add_formula(text=text)
    elif kind == "code":
        root = temp.add_code(text=text)
    elif kind == "heading":
        root = temp.add_heading(text=text, level=getattr(native, "level", 1))
    else:
        if native is not None and native.label == DocItemLabel.LIST_ITEM:
            root = temp.add_list_item(text=text, marker=native.marker, enumerated=native.enumerated)
        else:
            root = temp.add_text(label=label, text=text)
        if any(s["kind"] != "text" for s in segments):
            root.text = ""
            inline = temp.add_inline_group(parent=root)
            for segment in segments:
                if segment["kind"] == "math":
                    temp.add_formula(text=segment["text"], parent=inline)
                elif segment["kind"] == "code":
                    temp.add_code(text=segment["text"], parent=inline)
                else:
                    temp.add_text(label=DocItemLabel.TEXT, text=segment["text"], parent=inline)
    # The source spans live in the binding; derived text gets its own charspan.
    root.prov = [p.model_copy(update={"charspan": (0, len(root.text))}, deep=True) for p in provenance]
    return temp, root


def apply_ordered(raw, bound, response):
    if bound != scope(raw, bound["targets"]):
        raise ValueError("stale document or scope")
    if not isinstance(response, dict) or set(response) != {"scope_sha256", "targets", "order"}:
        raise ValueError("invalid response root")
    if response["scope_sha256"] != digest(bound):
        raise ValueError("foreign response scope")
    if not isinstance(response["targets"], dict) or set(response["targets"]) != set(bound["targets"]):
        raise ValueError("missing or unknown response target")
    doc = DoclingDocument.model_validate(raw)
    originals = {ref: resolve(doc, ref) for ref in bound["targets"] + bound["anchors"]}
    anchor_markdown = {ref: MarkdownDocSerializer(doc=doc).serialize(item=originals[ref]).text
                       for ref in bound["anchors"]}
    generated = {}
    for ref, blocks in response["targets"].items():
        if not isinstance(blocks, list) or not blocks:
            raise ValueError("empty target")
        covered = []
        for index, block in enumerate(blocks):
            indices = block.get("fragment_indices")
            if not isinstance(indices, list) or not indices or any(type(i) is not int for i in indices):
                raise ValueError("invalid fragment indices")
            if any(i < 0 or i >= len(originals[ref].prov) for i in indices):
                raise ValueError("unknown fragment")
            covered.extend(indices)
            generated[f"target:{ref}:{index}"] = block_document(
                block, [originals[ref].prov[i] for i in indices], native=originals[ref])
        if Counter(covered) != Counter(range(len(originals[ref].prov))):
            raise ValueError("missing or duplicate source fragment")
    anchor_tokens = ["anchor:" + ref for ref in bound["anchors"]]
    order = response["order"]
    if (not isinstance(order, list) or not all(isinstance(token, str) for token in order)
            or Counter(order) != Counter(list(generated) + anchor_tokens)):
        raise ValueError("missing, duplicate or foreign ordering token")
    if [token for token in order if token.startswith("anchor:")] != anchor_tokens:
        raise ValueError("non-target anchor order changed")
    lineage = []
    previous = None
    for index, token in enumerate(order):
        if token.startswith("anchor:"):
            previous = originals[token.removeprefix("anchor:")]
            continue
        following = next((originals[t.removeprefix("anchor:")] for t in order[index + 1:]
                          if t.startswith("anchor:")), None)
        sibling = following or previous or originals[bound["targets"][0]]
        temp, root = generated[token]
        parent = sibling.parent.resolve(doc)
        before = {ref.cref for ref in parent.children}
        doc.insert_node_items(sibling=sibling, node_items=[root], doc=temp, after=following is None)
        inserted = [ref.resolve(doc) for ref in parent.children if ref.cref not in before]
        if len(inserted) != 1:
            raise ValueError("ambiguous Core insertion")
        previous = inserted[0]
        lineage.append((token, previous))
    doc.delete_items(node_items=[originals[ref] for ref in bound["targets"]])
    for ref, expected in anchor_markdown.items():
        if MarkdownDocSerializer(doc=doc).serialize(item=originals[ref]).text != expected:
            raise ValueError("non-target anchor content changed")
    rendered = serialize(doc)
    delivered_refs = {span.item.self_ref for span in rendered.spans}
    if any(item.self_ref not in delivered_refs for _, item in lineage):
        raise ValueError("derived fragment is not reachable in stock Markdown")
    return {"document": doc.model_dump(mode="json", by_alias=True), "markdown": rendered.text,
            "response": deepcopy(response),
            "binding": {"source_document_sha256": digest(raw), "scope": bound,
                        "derived_items": [{"token": token, "derived_ref": item.self_ref,
                                           "source_provenance_in_scope": True,
                                           "derived_charspans_are_not_native_source_spans": True}
                                          for token, item in lineage],
                        "anchor_derived_refs": {ref: originals[ref].self_ref for ref in bound["anchors"]}},
            "model_calls": 0, "source_quality_verified": False}


def apply_caption(raw, reference, block):
    """Keep the parent caption reference; stock caption text is a plain-text path."""
    doc = DoclingDocument.model_validate(raw)
    caption = resolve(doc, reference)
    owners = [item for item in [*doc.tables, *doc.pictures]
              if any(ref.cref == reference for ref in item.captions)]
    if len(owners) != 1 or caption.children or block["kind"] != "paragraph":
        raise ValueError("requires unique leaf caption owner and paragraph payload")
    if block["fragment_indices"] != list(range(len(caption.prov))):
        raise ValueError("missing or duplicate caption fragment")
    if any(segment["kind"] != "text" for segment in block["segments"]):
        raise ValueError("stock caption serializer does not serialize inline typed children at caption position")
    temp, root = block_document(block, caption.prov, DocItemLabel.CAPTION)
    caption.text = root.text
    rendered = serialize(doc)
    if Counter(span.item.self_ref for span in rendered.spans)[caption.self_ref] != 1:
        raise ValueError("caption was dropped or repeated")
    return {"document": doc.model_dump(mode="json", by_alias=True), "markdown": rendered.text,
            "source_document_sha256": digest(raw), "source_caption_ref": reference,
            "source_provenance": deepcopy(raw["texts"][int(reference.rsplit("/", 1)[1])]["prov"]),
            "source_quality_verified": False, "model_calls": 0}


def expose_formula_picture(raw, reference, blocks):
    """Retain the picture/caption and expose only its verified formula children."""
    doc = DoclingDocument.model_validate(raw)
    picture = resolve(doc, reference)
    caption_refs = {ref.cref for ref in picture.captions}
    children = [ref.resolve(doc) for ref in picture.children if ref.cref not in caption_refs]
    if (not reference.startswith("#/pictures/") or not children
            or any(item.label != DocItemLabel.FORMULA or item.children for item in children)
            or len(blocks) != len(children)):
        raise ValueError("not a pure formula picture envelope")
    previous = picture
    binding = []
    for child, block in zip(children, blocks, strict=True):
        if block["kind"] != "formula" or block["fragment_indices"] != list(range(len(child.prov))):
            raise ValueError("missing or incompatible formula child")
        temp, root = block_document(block, child.prov)
        parent = previous.parent.resolve(doc)
        before = {ref.cref for ref in parent.children}
        doc.insert_node_items(sibling=previous, node_items=[root], doc=temp)
        previous = next(ref.resolve(doc) for ref in parent.children if ref.cref not in before)
        binding.append((child.self_ref, deepcopy(child.prov), previous))
    doc.delete_items(node_items=children)
    rendered = serialize(doc)
    reachable = {span.item.self_ref for span in rendered.spans}
    if any(item.self_ref not in reachable for _, _, item in binding):
        raise ValueError("formula child not delivered")
    return {"document": doc.model_dump(mode="json", by_alias=True), "markdown": rendered.text,
            "binding": {"source_document_sha256": digest(raw), "source_picture_ref": reference,
                        "derived_picture_ref": picture.self_ref,
                        "formulas": [{"source_ref": ref, "source_provenance": [p.model_dump(mode="json") for p in prov],
                                      "derived_ref": item.self_ref} for ref, prov, item in binding]},
            "source_quality_verified": False, "model_calls": 0}


def native_inventory(raw):
    doc = DoclingDocument.model_validate(raw)
    rendered = serialize(doc)
    counts = Counter(span.item.self_ref for span in rendered.spans)
    caption_owner = {ref.cref: item.self_ref for item in [*doc.tables, *doc.pictures] for ref in item.captions}
    rows = []
    for item in [*doc.texts, *doc.tables, *doc.pictures]:
        ref = item.self_ref
        parent = item.parent.cref if item.parent else None
        is_caption = ref in caption_owner
        in_picture = bool(parent and parent.startswith("#/pictures/")) and not is_caption
        responsibility = ("caption" if is_caption else "table" if ref.startswith("#/tables/")
                          else "picture" if in_picture or ref.startswith("#/pictures/")
                          else "body" if item.content_layer == ContentLayer.BODY else "unresolved")
        owners = [caption_owner[ref]] if is_caption else [parent] if in_picture else [ref]
        row = {"target_ref": ref, "native_label": str(item.label), "parent_ref": parent,
               "responsibility": responsibility, "render_owner_refs": owners,
               "native_render_reachable": counts[ref] > 0,
               "render_owner_reachable": any(counts[owner] > 0 for owner in owners),
               "native_serialization_occurrences": counts[ref],
               "native_text": getattr(item, "text", None),
               "native_provenance": [p.model_dump(mode="json") for p in item.prov],
               "discovered": True, "scoped": bool(item.prov), "eligible": False,
               "delivered": counts[ref] > 0, "delivery_kind": "cached-native-serialization",
               "source_quality_verified": False, "scheduled": False, "model_calls": 0}
        if responsibility == "body" and ref.startswith("#/texts/"):
            try:
                scope(raw, [ref])
                row.update(eligible=True, method="public-core-fragment-order-v1")
            except ValueError as error:
                row["unresolved_reason"] = str(error)
        elif responsibility == "caption":
            row.update(eligible=counts[ref] == 1, method="stock-parent-caption-serialization",
                       required_work="A inline content if present; parent table/picture retains caption ownership",
                       enrichment_limit="Plain text caption transport only; typed inline enrichment at caption position unresolved")
        elif responsibility == "table":
            row.update(required_work="B table content, structure and cell association; never duplicate as A jobs",
                       method="stock-table-serialization")
        elif responsibility == "picture":
            row.update(required_work="C image content/OCR; formula children additionally need A content handoff",
                       unresolved_reason="native picture representation alone does not deliver hidden child text")
            owner = resolve(doc, parent) if in_picture else item
            caption_refs = {ref.cref for ref in getattr(owner, "captions", [])}
            children = [child.resolve(doc) for child in owner.children if child.cref not in caption_refs]
            if children and all(child.label == DocItemLabel.FORMULA and not child.children for child in children):
                row.update(eligible=not in_picture, owner_job_ref=owner.self_ref,
                           disposition="member_of_picture_envelope" if in_picture else "formula_picture_envelope",
                           method="public-core-expose-formula-picture",
                           required_work="A formula transcription from native picture envelope; preserve original image",
                           unresolved_reason="native child text hidden; only legal mock handoff verified")
        rows.append(row)
        if ref.startswith("#/tables/"):
            table_markdown = serialize(doc).text
            for index, cell in enumerate(item.data.table_cells):
                rows.append({"target_ref": f"{ref}/data/table_cells/{index}", "native_label": "table_cell",
                             "parent_ref": ref, "responsibility": "table", "render_owner_refs": [ref],
                             "native_render_reachable": counts[ref] > 0,
                             "native_text": cell.text, "cell": cell.model_dump(mode="json"),
                             "native_provenance": [p.model_dump(mode="json") for p in item.prov],
                             "provenance_scope": "table envelope; no invented cell bbox",
                             "literal_present_in_stock_markdown": cell.text in table_markdown,
                             "discovered": True, "scoped": bool(item.prov), "eligible": False,
                             "delivered": counts[ref] > 0, "delivery_kind": "cached-native-table-serialization",
                             "source_quality_verified": False, "scheduled": False, "model_calls": 0})
    return rows, rendered.text


def main():
    source_manifest = json.loads((REPO / "docs/research/pdf-core-g2-inline-2026-10-15/inputs/input-manifest.json").read_text())
    records = []
    for source in source_manifest["sources"]:
        name = source["name"]
        path = REPO / "docs/research/pdf-core-native-round-2026-10-17/S0" / name / "document.json"
        raw = json.loads(path.read_text())
        pdf = REPO / source["source"]["path"]
        assert hashlib.sha256(pdf.read_bytes()).hexdigest() == source["source"]["sha256"]
        result = json.loads((path.parent / "result.json").read_text())
        version = result["version"]
        assert (version["docling_slim_version"], version["docling_core_version"], version["docling_parse_version"]) == ("2.132.0", "2.99.0", "7.22.3")
        rows, markdown = native_inventory(raw)
        output = HERE / "native-replay" / name
        output.mkdir(parents=True, exist_ok=True)
        with (output / "document.md").open("x") as stream:
            stream.write(markdown)
        records.append({"source": name, "pdf": source["source"], "physical_pages": list(raw["pages"]),
                        "document_path": str(path.relative_to(REPO)),
                        "document_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "version": version, "upstream": "cached-S0", "rows": rows})
    value = {"format": "A-cross-component-inventory-v2", "sources": records,
             "method_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             "oracle_reads": 0, "model_calls": 0, "source_quality_verified": False,
             "N_CF": None, "N_CF_unready_reason": "Independent source coverage and C image-content responsibility gate pending",
             "official": "Public Core types, InlineGroup, insert_node_items/delete_items, stock MarkdownDocSerializer",
             "custom": "Cross-component ownership inventory, fragment tokens and source/anchor validation"}
    with (HERE / "inventory.json").open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"sources": len(records), "rows": sum(len(s["rows"]) for s in records), "model_calls": 0}))


if __name__ == "__main__":
    main()
