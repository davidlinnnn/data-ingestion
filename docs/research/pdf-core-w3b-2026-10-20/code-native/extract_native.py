"""PDF text-layer only. Importing this module does not open target data."""
from __future__ import annotations

import hashlib
from statistics import median
from pathlib import Path

from metrics import native_char_lines


def extract(pdf_path, regions):
    """Extract char centers inside fixed native provenance boxes.

    regions: page (1-based), bbox [l,b,r,t] in PDF bottom-left coordinates,
    ref. Source text is deliberately absent from this API.
    Overlapping boxes preserve each physical char only once; bbox clipping
    and incomplete source extents remain limitations of the fixed identity.
    """
    import pypdfium2 as pdfium

    path = Path(pdf_path)
    document = pdfium.PdfDocument(path)
    characters = []
    by_page = {}
    for region in regions:
        by_page.setdefault(region["page"], []).append(region)
    try:
        for page_number, boxes in sorted(by_page.items()):
            page = document[page_number - 1]
            text = page.get_textpage()
            try:
                for index in range(text.count_chars()):
                    glyph = text.get_text_range(index, 1)
                    bbox = list(text.get_charbox(index))
                    x, y = (bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2
                    refs = []
                    for region in boxes:
                        left, bottom, right, top = region["bbox"]
                        if left <= x <= right and bottom <= y <= top:
                            refs.append(region["ref"])
                    if refs:
                        characters.append({"text":glyph,"page":page_number,
                                           "raw_index":index,"bbox":bbox,
                                           "line_bbox":list(text.get_charbox(index,loose=True)),
                                           "region_refs":refs})
            finally:
                text.close()
                page.close()
    finally:
        document.close()
    lines = native_char_lines(characters)
    # Use PDF whitespace widths, never gold indentation, to estimate one space.
    space_widths = [c['bbox'][2]-c['bbox'][0] for c in characters
                    if c['text'] == ' ' and c['bbox'][2] > c['bbox'][0]]
    widths = [c['line_bbox'][2]-c['line_bbox'][0] for c in characters
              if c['text'].isalnum() and c['line_bbox'][2] > c['line_bbox'][0]]
    unit = median(space_widths) if space_widths else None
    method = 'PDF_POSITIONED_SPACE_BBOX' if unit else None
    if not unit and len(widths) >= 8:
        middle = median(widths)
        if median(abs(w-middle) for w in widths) <= middle * .03:
            advances = []
            for line in lines:
                cs=sorted(line['chars'],key=lambda c:c['bbox'][0])
                advances += [b['bbox'][0]-a['bbox'][0] for a,b in zip(cs,cs[1:])
                             if middle*.7 <= b['bbox'][0]-a['bbox'][0] <= middle*1.5]
            if advances:
                unit = median(advances)
                method = 'NATIVE_MONOSPACED_GLYPH_ADVANCE_ESTIMATE'
    origins = {}
    for line in lines:
        origins[line['page']] = min(origins.get(line['page'],line['x_left']),line['x_left'])
    levels = sorted(set(round(l['x_left']-origins[l['page']],1) for l in lines))
    for line in lines:
        delta = line['x_left']-origins[line['page']]
        line['x_indent_relative'] = delta
        line['visual_indent_rank'] = levels.index(round(delta,1))
        if unit:
            columns=round(delta/unit)
            line['indent_columns'] = columns
            line['indent_quantization_residual'] = abs(delta/unit-columns)
            line['indent_status'] = (method if abs(delta/unit-columns)<=.3
                                     else 'UNKNOWN_NONQUANTIZED_X_INDENT')
            indent=' '*max(0,columns)
        else:
            line['indent_status']='UNKNOWN_SPACE_UNIT_VISUAL_RANK_ONLY'
            indent=' '*(4*line['visual_indent_rank'])
        cs=sorted(line['chars'],key=lambda c:(c['bbox'][0],c['raw_index']))
        parts=[]
        for i,c in enumerate(cs):
            if i and unit and not c['text'].isspace() and not cs[i-1]['text'].isspace():
                gap=c['bbox'][0]-cs[i-1]['bbox'][2]
                if gap > unit*.65:
                    parts.append(' '*max(1,round(gap/unit)))
            parts.append(c['text'])
        line['reconstructed_text']=indent+''.join(parts).strip()
    return {"pdf":str(path.resolve()),
            "pdf_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "regions":regions,"characters":characters,"lines":lines,
            "text":"\n".join(line["reconstructed_text"] for line in lines),
            "space_unit":unit,"space_unit_method":method,
            "space_bbox_sample_count":len(space_widths),
            "space_bbox_widths":space_widths,
            "display_visual_rank_4spaces_only":unit is None,
            "method":"PDFium char centers in fixed ref bbox union; geometric line/x ordering",
            "gold_used_to_repair_native":False,"inference":False,
            "source_extent_verified_by_this_function":False}
