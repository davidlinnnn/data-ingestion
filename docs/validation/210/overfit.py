"""#210 overfit check: is the listing rule tuned to the 21 papers it was written on?

    PYTHONPATH=. .venv/bin/python docs/validation/210/overfit.py CORPUS_MANIFEST STORE_212 HELDOUT

Reads, without parsing, the rule-off assemblies of the 21 papers (#212's store STORE_212, whose
newest assembly per paper is docling-parse@1 before #210) and of the 30 held-out papers
(HELDOUT, heldout.py's OUT), and writes overfit.json here:

- margin: for each page that holds a code node, each font with at least 5 runs and the share
  of its runs that advance evenly (pipeline.monospaced's run definition), as a histogram in
  tenths per set, and every (page, font) between 0.15 and 0.65.
- variants: the nodes the rule relabels with each threshold moved (share of even runs 0.3 and
  0.7, step tolerance 2 % and 6 %, at least 3 and 8 runs), counted and compared with the
  shipped thresholds. A replica of pipeline.monospaced with the shipped values must give the
  shipped result on every paper, or the check stops.
- misses: text, list item and heading nodes the rule leaves, next to a code node in reading
  order, whose most common font is monospaced on their page; per paper, with the rule off (the
  positive control: corpus papers 1 and 4 must show some) and on.
- no_code_neighbour: such nodes with no code node next to them, the listings docling labels
  nowhere as code, which the rule does not reach (#210's limit), counted per held-out paper.

Paper text stays out.
"""

import copy
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

import pypdfium2 as pdfium
from docling.utils.locks import pypdfium2_lock

from kp_canonicalization.methods.docling_parse import pipeline

HERE = Path(__file__).resolve().parent
SHIPPED = pipeline.monospaced
VARIANTS = {"share 0.3": {"share": 0.3}, "share 0.7": {"share": 0.7}, "tolerance 2 %": {"tol": 0.02},
            "tolerance 6 %": {"tol": 0.06}, "runs 3": {"runs": 3}, "runs 8": {"runs": 8}}  # fmt: skip


def latest(folder: Path) -> dict:
    paths = sorted(glob.glob(str(folder / "items/*/assembly.json")), key=os.path.getmtime)
    return json.loads(Path(paths[-1]).read_text())["document"]


def run_shares(characters: list, tol: float = 0.04) -> dict[str, list[bool]]:
    """Per font, whether each run advances evenly; runs as pipeline.monospaced cuts them."""
    runs, run = [], []
    for c in characters:
        if run and (not c.glyph.strip() or c.font != run[-1].font
                    or abs(c.origin_y - run[-1].origin_y) > 0.1):  # fmt: skip
            runs.append(run)
            run = []
        if c.glyph.strip():
            run.append(c)
    runs.append(run)
    even = defaultdict(list)
    for run in runs:
        steps = [b.origin_x - a.origin_x for a, b in zip(run, run[1:], strict=False)]
        if run and len(steps) >= 5 and len({c.glyph for c in run}) >= 4:
            middle = median(steps)
            even[run[0].font].append(middle > 0 and all(abs(s - middle) <= tol * middle for s in steps))
    return even


def monospaced(runs: int = 5, tol: float = 0.04, share: float = 0.5):
    def check(characters: list, font: str) -> bool:
        even = run_shares(characters, tol)[font]
        return len(even) >= runs and sum(even) >= share * len(even)

    return check


def place(node: dict) -> str | None:
    return json.dumps([node["prov"][0]["page_no"], node["prov"][0]["bbox"]]) if node["prov"] else None


def relabeled(document: dict, data: bytes, check) -> tuple[set, dict]:
    pipeline.monospaced = check
    try:
        on = copy.deepcopy(document)
        pipeline.whole_listings(on, data)
    finally:
        pipeline.monospaced = SHIPPED
    before = {place(n): n["label"] for n in document["texts"]}
    return {place(n) for n in on["texts"] if n["label"] == "code" and before.get(place(n)) != "code"}, on


def monospaced_listing_nodes(document: dict, data: bytes) -> tuple[int, int]:
    """(next to a code node, not next to one): listing-label nodes in a monospaced font."""
    order = pipeline.reading_order(document)
    near = far = 0
    with pypdfium2_lock, pdfium.PdfDocument(data) as pdf:
        pages: dict[int, list] = {}

        def characters(number: int) -> list:
            return pages.setdefault(number, pipeline.page_characters(pdf, number))

        for at, node in enumerate(order):
            if node["label"] not in pipeline.LISTING_LABELS or not node["prov"]:
                continue
            fonts = pipeline.node_fonts(document, node, characters)
            if not fonts or not SHIPPED(characters(node["prov"][0]["page_no"]), fonts.most_common(1)[0][0]):
                continue
            if any(0 <= i < len(order) and order[i]["label"] == "code" for i in (at - 1, at + 1)):
                near += 1
            else:
                far += 1
    return near, far


def main(manifest: Path, store_212: Path, heldout: Path) -> None:
    papers = [("corpus", str(p["index"]), manifest.parent / p["file"], store_212 / f"doc_{p['index']}")
              for p in json.loads(manifest.read_text())["papers"]]  # fmt: skip
    papers += [("held-out", p["id"], heldout / "papers" / f"{p['id']}.pdf", heldout / "store/documents" / f"doc_h{i}")
               for i, p in enumerate(json.loads((heldout / "manifest.json").read_text()))]  # fmt: skip
    shares: dict[str, list[float]] = defaultdict(list)
    between: list[dict] = []
    variants = {name: Counter() for name in VARIANTS}
    misses, unreached = {}, {}
    for kind, name, path, folder in papers:
        data, document = path.read_bytes(), latest(folder)
        numbers = sorted({p["page_no"] for n in document["texts"] if n["label"] == "code" for p in n["prov"]})
        with pypdfium2_lock, pdfium.PdfDocument(data) as pdf:
            for number in numbers:
                for font, even in run_shares(pipeline.page_characters(pdf, number)).items():
                    if len(even) >= 5:
                        share = sum(even) / len(even)
                        shares[kind].append(share)
                        if 0.15 < share < 0.65:
                            between.append({"paper": name, "page": number, "font": font, "share": share})
        shipped, on = relabeled(document, data, SHIPPED)
        assert relabeled(document, data, monospaced())[0] == shipped, f"replica differs on {name}"
        for variant, values in VARIANTS.items():
            found = relabeled(document, data, monospaced(**values))[0]
            variants[variant].update({f"{kind} relabeled": len(found), f"{kind} added": len(found - shipped),
                                      f"{kind} dropped": len(shipped - found)})  # fmt: skip
        variants.setdefault("shipped", Counter()).update({f"{kind} relabeled": len(shipped)})
        off_near, _ = monospaced_listing_nodes(document, data)
        on_near, on_far = monospaced_listing_nodes(on, data)
        misses[f"{kind} {name}"] = {"rule_off": off_near, "rule_on": on_near}
        if kind == "held-out" and on_far:
            unreached[name] = on_far
        print(kind, name, len(shipped), flush=True)
    report = {
        "margin": {kind: dict(sorted(Counter(min(9, int(s * 10)) for s in values).items()))
                   for kind, values in shares.items()},  # fmt: skip
        "margin_between_0.15_and_0.65": between,
        "variants": {name: dict(counts) for name, counts in variants.items()},
        "misses": {k: v for k, v in misses.items() if v["rule_off"] or v["rule_on"]},
        "no_code_neighbour": unreached,
    }
    (HERE / "overfit.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: report[k] for k in ("margin", "variants", "misses")}))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
