"""Caption-explicit continuation relations; isolated public TableData replacement."""
from copy import deepcopy
import re
from docling_core.types.doc import RefItem, TableData
from scoring import digest


def headers(data):
    return tuple(" ".join(c.text.split()).casefold() for c in
                 sorted(data.table_cells, key=lambda c: (c.start_row_offset_idx, c.start_col_offset_idx))
                 if c.column_header and c.start_row_offset_idx == 0)


def discover(document):
    candidates = {}
    inventory = []
    for item, _ in document.iterate_items():
        if not item.self_ref.startswith("#/tables/"):
            continue
        if len(item.prov) == 1:
            inventory.append((item.self_ref, item.prov[0].page_no, list(headers(item.data))))
        captions = [(r.cref, r.resolve(document).text) for r in item.captions]
        matches = [(ref, text, re.match(r"^Table\s+(\d+)\s*(\(continued\))?(?=\s|:|$)", text, re.I))
                   for ref, text in captions]
        matches = [(r, t, m) for r, t, m in matches if m]
        if len(matches) != 1 or len(item.prov) != 1 or not headers(item.data):
            continue
        ref, text, match = matches[0]
        candidates.setdefault(match[1], []).append(dict(
            table_ref=item.self_ref, page=item.prov[0].page_no,
            continued=bool(match[2]), caption_ref=ref, header=list(headers(item.data)),
            provenance=[p.model_dump(mode="json") for p in item.prov]))
    relations = []
    for number, fragments in candidates.items():
        if len(fragments) < 2:
            continue
        pages = [f["page"] for f in fragments]
        if (fragments[0]["continued"] or not all(f["continued"] for f in fragments[1:])
                or pages != list(range(pages[0], pages[0]+len(pages)))
                or any(f["header"] != fragments[0]["header"] for f in fragments)):
            continue
        refs = {f["table_ref"] for f in fragments}
        if any(ref not in refs and pages[0] <= page <= pages[-1]+1 and header == fragments[0]["header"]
               for ref, page, header in inventory):
            continue
        relations.append(dict(logical_id="table-"+number,
            source_revision=digest(document.model_dump(mode="json")),
            fragments=fragments, condition_caption_refs=[fragments[0]["caption_ref"]],
            header_policy="repeated headers remain fragment headers, not data rows"))
    return relations


def replace_data(document, relation, replacements):
    if relation not in discover(document):
        raise ValueError("stale, foreign or ambiguous logical-table relation")
    refs = [f["table_ref"] for f in relation["fragments"]]
    if set(replacements) != set(refs):
        raise ValueError("all fragments required exactly once")
    parsed = {r: TableData.model_validate(v) for r, v in replacements.items()}
    h = [headers(v) for v in parsed.values()]
    if not h[0] or any(v != h[0] for v in h):
        raise ValueError("incompatible replacement headers")
    if any(c.bbox is not None for v in parsed.values() for c in v.table_cells):
        raise ValueError("replacement cannot invent cell geometry")
    out = document.model_copy(deep=True)
    for ref, data in parsed.items():
        RefItem(cref=ref).resolve(out).data = deepcopy(data)
    before, after = document.model_dump(mode="json"), out.model_dump(mode="json")
    for ref in refs:
        index = int(ref.rsplit("/", 1)[1])
        before["tables"][index]["data"] = after["tables"][index]["data"] = None
    if before != after:
        raise ValueError("non-target graph, caption or provenance changed")
    sidecar = deepcopy(relation)
    sidecar["output_revision"] = digest(out.model_dump(mode="json"))
    sidecar["location_precision"] = "source fragment envelope only; no inferred cell boxes"
    return out, sidecar
