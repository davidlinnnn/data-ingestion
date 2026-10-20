"""Source-independent code comparison primitives; no inference or target I/O."""
from __future__ import annotations

import re
from statistics import median


def levenshtein(a, b):
    """Exact unit-cost insertion/deletion/substitution distance, O(min(n,m)) RAM."""
    if isinstance(a, str) and isinstance(b, str):
        # Myers bit-vector algorithm; Python integers hold the whole pattern.
        if not a:
            return len(b)
        masks = {}
        for i, token in enumerate(a):
            masks[token] = masks.get(token, 0) | (1 << i)
        positive, negative, score = ~0, 0, len(a)
        high = 1 << (len(a) - 1)
        for token in b:
            equal = masks.get(token, 0)
            mixed = equal | negative
            horizontal = (((equal & positive) + positive) ^ positive) | equal
            plus = negative | ~(horizontal | positive)
            minus = positive & horizontal
            score += bool(plus & high) - bool(minus & high)
            plus = (plus << 1) | 1
            minus <<= 1
            positive = minus | ~(mixed | plus)
            negative = plus & mixed
        return score
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def cer(reference, candidate):
    if not reference:
        return {"status": "UNKNOWN_EMPTY_SOURCE", "distance": None,
                "source_chars": 0, "candidate_chars": len(candidate), "CER": None}
    distance = levenshtein(reference, candidate)
    return {"status": "MEASURED", "distance": distance,
            "source_chars": len(reference), "candidate_chars": len(candidate),
            "CER": distance / len(reference)}


def line_alignment(source, target):
    """Edit alignment of actual lines; substitution uses normalized char distance.

    No source tokens are injected into target. Exact alignment ties are recorded.
    This pairing is diagnostic, never proof of source-block identity.
    """
    a, b = source.splitlines(), target.splitlines()
    costs = [[float(i + j) for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    moves = {}
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            left, right = a[i - 1].strip(), b[j - 1].strip()
            substitution = levenshtein(left, right) / max(len(left), len(right), 1)
            options = [(costs[i-1][j-1] + substitution, "PAIR"),
                       (costs[i-1][j] + 1, "DELETE"),
                       (costs[i][j-1] + 1, "INSERT")]
            best = min(x[0] for x in options)
            tied = [x[1] for x in options if abs(x[0] - best) < 1e-10]
            costs[i][j] = best
            moves[i, j] = (tied[0], len(tied) > 1)
    i, j = len(a), len(b)
    result = []
    while i or j:
        move, ambiguous = moves.get((i, j), ("DELETE" if i else "INSERT", False))
        pair = {"source_line": i if move != "INSERT" else None,
                "target_line": j if move != "DELETE" else None,
                "operation": move, "alignment_tie": ambiguous}
        if move != "INSERT":
            pair["source_text"] = a[i - 1]
            i -= 1
        if move != "DELETE":
            pair["target_text"] = b[j - 1]
            j -= 1
        result.append(pair)
    return result[::-1]


TOKEN = re.compile(r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(?:<=|>=|!=|==|:=|\+=|-=|\*=|/=|\*\*|//|<<|>>|->|&&|\|\|)|(?:[<>+*/%=!&|^~−≤≥≠∈∉∧∨])|(?:\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|(?:[^\W\d]\w*)|(?:[^\s])''', re.UNICODE)


def lexical_tokens(text):
    """Keep literals, identifiers and operators, with no NFKC or source repair."""
    return TOKEN.findall(text)


def compare(source, target):
    aligned = line_alignment(source, target)
    source_lines, target_lines = source.splitlines(), target.splitlines()
    for row in aligned:
        if row["operation"] != "PAIR":
            row["indent_status"] = "UNKNOWN_UNPAIRED"
            continue
        a, b = row["source_text"], row["target_text"]
        row["source_indent_literal"] = a[:len(a)-len(a.lstrip())]
        row["target_indent_literal"] = b[:len(b)-len(b.lstrip())]
        row["indent_status"] = ("UNKNOWN_TAB_WIDTH" if "\t" in row["source_indent_literal"] + row["target_indent_literal"]
                                else "LITERAL_EQUAL" if row["source_indent_literal"] == row["target_indent_literal"]
                                else "DIFFERENT_NOT_AUTOMATIC_LOGIC_ERROR")
        row["source_tokens"] = lexical_tokens(a)
        row["target_tokens"] = lexical_tokens(b)
        row["token_edit_distance"] = levenshtein(row["source_tokens"], row["target_tokens"])
    def operators(text):
        return [t for t in lexical_tokens(text) if re.fullmatch(r"(?:<=|>=|!=|==|:=|\+=|-=|\*=|/=|\*\*|//|<<|>>|->|&&|\|\||[<>+*/%=!&|^~−≤≥≠∈∉∧∨-])",t)]
    def numbers(text):
        return [t for t in lexical_tokens(text) if re.fullmatch(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?",t)]
    aops,bops=operators(source),operators(target)
    anums,bnums=numbers(source),numbers(target)
    return {"raw": cer(source, target),
            "whitespace_removed_diagnostic": cer(re.sub(r"\s", "", source), re.sub(r"\s", "", target)),
            "operator_sequences":{"source":aops,"target":bops,"exact":aops==bops,"edit_distance":levenshtein(aops,bops)},
            "number_sequences":{"source":anums,"target":bnums,"exact":anums==bnums,"edit_distance":levenshtein(anums,bnums)},
            "source_lines": len(source_lines), "target_lines": len(target_lines),
            "line_alignment": aligned, "semantic_pass_inferred": False,
            "runtime_executed": False}


def native_char_lines(characters):
    """Group visible PDF characters geometrically without consulting gold.

    Input characters have text/raw_index/page/bbox=(left,bottom,right,top).
    Left-to-right x ordering is explicit and independent of the source.
    Absolute x and raw indices are retained; source spaces are never inserted.
    """
    groups = []
    ordered = sorted(characters, key=lambda c: (c["page"], -((c.get("line_bbox",c["bbox"])[1]+c.get("line_bbox",c["bbox"])[3])/2), c["bbox"][0], c["raw_index"]))
    for char in ordered:
        if char["text"] in ("\r", "\n", "\r\n", ""):
            continue
        if char["text"].isspace() and char["bbox"][2] <= char["bbox"][0]:
            continue
        x0, y0, x1, y1 = char.get("line_bbox",char["bbox"])
        center = (y0+y1)/2
        height = max(y1-y0, .1)
        candidates = [g for g in groups if g["page"] == char["page"] and abs(g["center_y"]-center) <= min(g["height"],height)*.3]
        if candidates:
            group = min(candidates, key=lambda g: abs(g["center_y"]-center))
        else:
            group = {"page": char["page"], "center_y": center, "height":height, "chars": []}
            groups.append(group)
        group["chars"].append(char)
    for group in groups:
        chars = sorted(group["chars"], key=lambda c:(c["bbox"][0],c["raw_index"]))
        widths = [c["bbox"][2]-c["bbox"][0] for c in chars if c["text"].isalnum() and c["bbox"][2]>c["bbox"][0]]
        group["x_left"] = min(c["bbox"][0] for c in chars)
        group["text_without_inferred_spaces"] = "".join(c["text"] for c in chars)
        group["whitespace_policy"] = "Keep positioned PDF whitespace; do not use gold to fill geometric gaps."
        group["median_glyph_width"] = median(widths) if widths else None
        group["raw_indices"] = [c["raw_index"] for c in chars]
        group["indent_columns"] = None
        group["indent_status"] = "X_COORDINATE_ONLY_FONT_ADVANCE_NOT_PROVEN"
    return sorted(groups, key=lambda g:(g["page"],-g["center_y"],g["x_left"]))


def selfcheck():
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("ab", "ba") == 2
    assert cer("a", "aaa")["CER"] == 2
    assert cer("", "x")["CER"] is None
    assert lexical_tokens("①") != lexical_tokens("1")
    assert lexical_tokens("a<=b") != lexical_tokens("a<b")
    assert lexical_tokens('x="SKILL.md"') != lexical_tokens('x="SKIL.md"')
    assert compare("if x:\n    y()", "if x:\ny()")["raw"]["distance"] == 4
    chars=[{"text":"x","raw_index":7,"page":1,"bbox":[20,10,25,20]},
           {"text":"y","raw_index":9,"page":1,"bbox":[40,0,45,9]}]
    lines=native_char_lines(chars)
    assert len(lines)==2 and lines[1]["x_left"]==40 and lines[1]["indent_columns"] is None
    return {"synthetic_checks":9,"passed":True,"target_data_read":False}


if __name__ == "__main__":
    import json
    print(json.dumps(selfcheck()))
