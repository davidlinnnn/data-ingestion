"""Bounded real Docling assembly seam, no page inference or runtime compatibility claim."""
import json
from pathlib import Path
from types import SimpleNamespace
from docling.datamodel import base_models as bm
from docling.models.stages.reading_order.readingorder_model import ReadingOrderModel, ReadingOrderOptions
from docling_core.types.doc import Size
from pdf_processing.continuation import predict_merges
from replay import CHECKPOINTS, load


def assemble(candidate=False):
    # Hash validation precedes restoring any page structures.
    load()
    types = {c.__name__: c for c in (bm.TextElement, bm.Table, bm.FigureElement, bm.ContainerElement)}
    pages, elements = [], []
    for path in sorted(CHECKPOINTS.glob('page-*.json')):
        data = json.loads(path.read_text())
        unit = bm.AssembledUnit(**{k: [types[e['type']].model_validate(e['value']) for e in v]
                                  for k, v in data['assembled'].items()})
        pages.append(bm.Page(page_no=data['page_no'], size=Size.model_validate(data['size']), assembled=unit))
        elements.extend(unit.elements)
    context = SimpleNamespace(pages=pages, assembled=SimpleNamespace(elements=elements),
        input=SimpleNamespace(file=Path('08.pdf'), document_hash=12835515505658431872))
    model = ReadingOrderModel(ReadingOrderOptions())
    ordered = model.ro_model.predict_reading_order(model._assembled_to_readingorder_elements(context))
    merges = predict_merges(ordered) if candidate else model.ro_model.predict_merges(ordered)
    doc = model._readingorder_elements_to_docling_doc(context, ordered,
        model.ro_model.predict_to_captions(ordered), model.ro_model.predict_to_footnotes(ordered), merges)
    return doc.model_dump(mode='json'), {str(k): v for k, v in merges.items()}
