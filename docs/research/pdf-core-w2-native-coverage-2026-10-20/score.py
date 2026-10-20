"""Strict smoke alignment and review candidates; never a semantic pass detector."""
import argparse
from collections import Counter, defaultdict
import difflib
import hashlib
import json
from pathlib import Path
import re
import unicodedata

HERE = Path(__file__).resolve().parent
BODY = {"text", "paragraph", "list_item"}
LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
                         "‘": "'", "’": "'", "“": '"', "”": '"'})


def norm(text):
    text = unicodedata.normalize("NFC", text).translate(LIGATURES)
    text = re.sub(r"(?<=[A-Za-z])(?:-|\ufffe)\s*\n\s*(?=[A-Za-z])", "", text)
    return re.sub(r"\s+", "", text.replace("\u00ad", ""))


def sentences(text):
    text = re.sub(r"^\s*[•]\s*", "", text)
    start = 0
    pieces = []
    for match in re.finditer(r'[.!?][”\'\"]?\s+(?=[A-Z(])', text):
        prefix = text[start:match.end()].rstrip()
        if re.search(r"(?:\bet al|\be\.g|\bi\.e|\bFig|\bEq|\bSec|\bDr|\b[A-Z])\.$", prefix):
            continue
        pieces.append(text[start:match.end()].strip())
        start = match.end()
    if text[start:].strip():
        pieces.append(text[start:].strip())
    return pieces


def positions(haystack, needle):
    assert needle
    result, start = [], 0
    while True:
        pos = haystack.find(needle, start)
        if pos < 0:
            return result
        result.append(pos)
        start = pos + len(needle)


def score(reference, items):
    body = [i for i in items if i["label"] in BODY and i["content_layer"] == "body"]
    stream, spans = "", []
    for item in body:
        start = len(stream)
        stream += norm(item["text"])
        spans.append((start, len(stream), item))
    units = []
    boundary_fragments = []
    for paragraph in reference["paragraphs"]:
        parts = sentences(paragraph["text"])
        for index, text in enumerate(parts):
            unit = dict(id=f'{paragraph["id"]}:s{index+1}', paragraph=paragraph["id"],
                        column=paragraph["column"], page=reference["page"], text=text)
            is_fragment = (index == 0 and paragraph.get("begins_in_previous_page")) or (
                index == len(parts)-1 and paragraph.get("continues_next_page"))
            (boundary_fragments if is_fragment else units).append(unit)
    source_counts = Counter(norm(u["text"]) for u in units)
    missing, duplicates, unresolved, alignment = [], [], [], []
    for unit in units + boundary_fragments:
        needle = norm(unit["text"])
        found = positions(stream, needle)
        hits = [[i["id"] for start, end, i in spans if pos < end and pos+len(needle) > start]
                for pos in found]
        row = dict(**unit, positions=found, output_items=hits,
                   boundary_fragment=unit in boundary_fragments)
        alignment.append(row)
        if unit in boundary_fragments:
            continue
        if not found:
            closest = sorted(body, key=lambda i: difflib.SequenceMatcher(None, needle, norm(i["text"])).ratio(),
                             reverse=True)[:1]
            missing.append(dict(**unit, nearest_output_item=closest[0] if closest else None))
        elif len(found) > source_counts[needle]:
            duplicates.append(row)
        if len(found) != 1 or source_counts[needle] != 1:
            unresolved.append(unit["id"])
    rows = [a for a in alignment if not a["boundary_fragment"]]
    adjacent, inversions = [], []
    for left, right in zip(rows, rows[1:]):
        if left["id"] not in unresolved and right["id"] not in unresolved:
            pair = dict(before=left["id"], after=right["id"],
                        output_positions=[left["positions"][0], right["positions"][0]])
            adjacent.append(pair)
            if pair["output_positions"][0] > pair["output_positions"][1]:
                inversions.append(pair)
    by_item = defaultdict(list)
    by_paragraph = defaultdict(list)
    for row in rows:
        if row["id"] not in unresolved:
            by_paragraph[row["paragraph"]].append(row)
            for item in row["output_items"][0]:
                by_item[item].append(row)
    mixed = []
    for item, matched in by_item.items():
        if {m["column"] for m in matched} >= {"L", "R"}:
            mixed.append(dict(output_item=item, sentence_ids=[m["id"] for m in matched],
                              source_paragraphs=sorted({m["paragraph"] for m in matched}),
                              needs_continuation_review=True))
    complete_paragraphs = {}
    for paragraph in reference["paragraphs"]:
        relevant = [r for r in rows if r["paragraph"] == paragraph["id"]]
        if relevant and all(r["id"] not in unresolved for r in relevant):
            complete_paragraphs[paragraph["id"]] = dict(column=paragraph["column"],
                start=min(r["positions"][0] for r in relevant),
                end=max(r["positions"][0]+len(norm(r["text"])) for r in relevant))
    insertions = []
    for rid, right in complete_paragraphs.items():
        if right["column"] != "R":
            continue
        left = [(pid, p) for pid, p in complete_paragraphs.items() if p["column"] == "L"]
        for (aid, a), (bid, b) in zip(left, left[1:]):
            if a["end"] <= right["start"] and right["end"] <= b["start"]:
                insertions.append(dict(left_before=aid, right=rid, left_after=bid))
                break
    structure = []
    for heading in reference.get("headings", []):
        found = [i for i in items if norm(i["text"]) == norm(heading["text"])]
        structure.append(dict(reference=heading, output=found,
            text_matched=bool(found), role_correct=bool(found) and all(i["label"] == "section_header" for i in found),
            level_correct=bool(found) and all(i.get("level") == heading["level"] for i in found)))
    separation = []
    for region in reference.get("nonbody", []):
        # Short page numbers require geometry/role review; never substring-match them in prose.
        needle = norm(region["text"])
        found = [i for i in items if norm(i["text"]) == needle or
                 (len(needle) >= 8 and needle in norm(i["text"]))]
        separation.append(dict(reference=region, exact_item_matches=found,
            in_body_candidates=[i["id"] for i in found if i in body],
            status="REVIEW_GEOMETRY" if len(norm(region["text"])) < 8 else "REVIEW"))
    return dict(paper_id=reference["paper_id"], page=reference["page"],
        denominator=dict(complete_sentence_units=len(units), boundary_fragments=len(boundary_fragments),
            uniquely_aligned_sentences=sum(r["id"] not in unresolved for r in rows),
            adjacent_pairs=len(adjacent), reference_paragraphs=len(reference["paragraphs"]),
            completely_aligned_paragraphs=len(complete_paragraphs)),
        missing_candidates=missing, duplicate_candidates=duplicates, adjacent_inversions=inversions,
        right_into_left=insertions, mixed_column_items=mixed, unresolved_sentence_ids=unresolved,
        candidate_counts_are_lower_bounds=bool(unresolved),
        alignment=alignment, heading_text_level=structure, nonbody_separation=separation,
        absent_source_regions=reference.get("no_regions_present", []),
        q4={k: "UNKNOWN" for k in ["meaning_changing_omission", "meaning_changing_duplication",
             "meaning_changing_order_or_join", "furniture_or_list_scope_error"]},
        cross_page="NOT_EXERCISED", semantics="Manual review required; zero candidates is not a pass")


def document_items(path):
    from docling_core.types.doc import DoclingDocument
    doc = DoclingDocument.load_from_json(path)
    return [dict(id=item.self_ref, text=item.text, label=item.label.value,
        content_layer=item.content_layer.value, level=getattr(item, "level", None),
        parent=item.parent.cref if item.parent else None,
        prov=[p.model_dump(mode="json") for p in item.prov])
        for item, _ in doc.iterate_items(traverse_pictures=True) if hasattr(item, "text")]


def selfcheck():
    def item(i, text, label="text", layer="body", level=None):
        return dict(id=i, text=text, label=label, content_layer=layer, level=level, prov=[])
    ref = dict(paper_id="control", page=2, paragraphs=[
        dict(id="l1", column="L", text="The treatment is not effective."),
        dict(id="l2", column="L", text="The dose is 10 mg."),
        dict(id="r1", column="R", text="Right column follows the left.")],
        headings=[dict(text="2.1 Details", level=2)], nonbody=[dict(id="f",label="footnote",text="A separate footnote.")])
    correct = [item("a", ref["paragraphs"][0]["text"]), item("b", ref["paragraphs"][1]["text"]),
               item("c", ref["paragraphs"][2]["text"]), item("h", "2.1 Details", "section_header", level=2),
               item("f", "A separate footnote.", "footnote")]
    result = score(ref, correct)
    assert not result["missing_candidates"] and not result["adjacent_inversions"]
    assert result["heading_text_level"][0]["level_correct"]
    assert not result["nonbody_separation"][0]["in_body_candidates"]
    assert len(score(ref, [correct[0], correct[2], correct[1]])["right_into_left"]) == 1
    assert len(score(ref, [correct[0], correct[2], correct[1]])["adjacent_inversions"]) == 1
    assert len(score(ref, correct + [correct[0]])["duplicate_candidates"]) == 1
    assert len(score(ref, [item("x", "The treatment is effective.")] + correct[1:])["missing_candidates"]) == 1
    assert len(score(ref, [item("x", "The dose is 100 mg.")] + [correct[0], correct[2]])["missing_candidates"]) == 1
    assert len(score(ref, [item("x", correct[0]["text"]+" "+correct[2]["text"]), correct[1]])["mixed_column_items"]) == 1
    assert score(ref, [item("f", "A separate footnote.")])["nonbody_separation"][0]["in_body_candidates"] == ["f"]
    assert score(ref, [item("f", "Prose. A separate footnote. More prose.")])["nonbody_separation"][0]["in_body_candidates"] == ["f"]
    assert len(sentences("Radford et al. (2018) agree. A second sentence.")) == 2
    assert norm("10 mg") != norm("-10 mg") and norm("not safe") != norm("safe")
    assert norm("ofﬁce\n space") == norm("office space")
    assert norm("pre-\ntrain") == norm("pretrain")
    assert result["q4"]["meaning_changing_omission"] == "UNKNOWN"
    print("Alignment/order/structure/negation/number/normalization controls passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selfcheck", action="store_true")
    parser.add_argument("--job")
    args = parser.parse_args()
    if args.selfcheck:
        selfcheck()
    else:
        jobs = json.loads((HERE / "smoke-jobs.json").read_text())["jobs"]
        job = next(j for j in jobs if j["id"] == args.job)
        reference = json.loads((HERE / job["reference"]).read_text())
        items = document_items(HERE / "smoke" / args.job / "document.json")
        result = score(reference, items)
        result["reference_sha256"] = hashlib.sha256((HERE / job["reference"]).read_bytes()).hexdigest()
        result["scorer_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        (HERE / "smoke" / args.job / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
        (HERE / "smoke" / args.job / "ordered-items.json").write_text(json.dumps(items, ensure_ascii=False, indent=2)+"\n")
        print(json.dumps({k: v for k, v in result.items() if k in ("paper_id", "denominator", "q4")}, ensure_ascii=False))
