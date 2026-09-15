"""Versioned, bounded continuation policy; no upstream package mutation.

Conservative column-edge continuation, not general paragraph discovery. Thresholds
are explicit bounded policy, not trained/qualified universal document geometry.
"""
import re
from collections import Counter
from docling_core.types.doc import CoordOrigin
from docling_ibm_models.reading_order.reading_order_rb import ReadingOrderPredictor

METHOD = 'column-edge-continuation-v1'


def geometry(e):
    if e.coord_origin != CoordOrigin.BOTTOMLEFT:
        raise ValueError('continuation_requires_bottom_left_coordinates')
    w, h = e.page_size.width, e.page_size.height
    if w <= 0 or h <= 0:
        raise ValueError('invalid_page_size')
    return e.l / w, 1 - e.t / h, e.r / w, 1 - e.b / h


def boundary_pair(a, b):
    al, at, ar, ab = geometry(a)
    bl, bt, br, bb = geometry(b)
    aw, bw = ar - al, br - bl
    if min(aw, bw) < .2 or min(aw, bw) / max(aw, bw) < .65:
        return False
    if ab < .8 or bt > .25:
        return False
    if b.page_no == a.page_no + 1:
        return abs(al - bl) <= .06 and abs(ar - br) <= .06
    return b.page_no == a.page_no and ar < bl


def predict_merges(ordered):
    """Return disjoint ordered chains; preserve input elements, labels and text.

    A non-text first item at a column entrance blocks continuation. Margin-sized
    items cannot win a body-column match. Ambiguous targets/owners yield no edge.
    """
    edges = {}
    for a in ordered:
        if a.label != 'text' or not re.fullmatch(r'.+([a-z,\-\u00AD])\s*', a.text):
            continue
        candidates = [b for b in ordered if b.cid != a.cid and boundary_pair(a, b)
                      and b.label not in ('page_header', 'page_footer', 'footnote')]
        # Select the first geometric column entrance, regardless of text label.
        if not candidates:
            continue
        rank = lambda b: (b.page_no, geometry(b)[0] if b.page_no == a.page_no else 0, geometry(b)[1])
        candidates.sort(key=rank)
        b = candidates[0]
        if len(candidates) > 1 and rank(b) == rank(candidates[1]):
            continue
        # A wider/narrower header or container above the selected text is a barrier.
        bl, bt, br, bb = geometry(b)
        if any(c.page_no == b.page_no
               and min(br, geometry(c)[2]) > max(bl, geometry(c)[0])
               and min(bb, geometry(c)[3]) > max(bt, geometry(c)[1])
               for c in candidates[1:]):
            continue
        blockers = [c for c in ordered if c.page_no == b.page_no and c.cid != b.cid
                    and c.label not in ('page_header', 'page_footer', 'footnote')
                    and geometry(c)[1] <= bt
                    and min(geometry(c)[2], br)-max(geometry(c)[0], bl) > .5*(br-bl)]
        if blockers:
            continue
        if b.label == 'text' and re.fullmatch(r'\s*[a-zA-Z\u00C0-\u024F].+', b.text):
            edges[a.cid] = b.cid
    # Retain upstream inline joins. Only page/column transitions are replaced.
    by_id = {e.cid: e for e in ordered}
    for root, members in ReadingOrderPredictor().predict_merges(ordered).items():
        for left, right in zip([root, *members], members):
            a, b = by_id[left], by_id[right]
            if (a.page_no == b.page_no and a.r < b.l
                    and min(a.t, b.t) > max(a.b, b.b)):
                edges[left] = right
    owners = Counter(edges.values())
    edges = {a: b for a, b in edges.items() if owners[b] == 1}
    targets = set(edges.values())
    chains = {}
    for a in edges.keys() - targets:
        chain = []
        b = a
        while b in edges:
            b = edges[b]
            chain.append(b)
        chains[a] = chain
    return chains


class ContinuationPredictor(ReadingOrderPredictor):
    """Instance-scoped adapter retaining upstream order, captions and footnotes."""

    def predict_merges(self, sorted_elements):
        return predict_merges(sorted_elements)
