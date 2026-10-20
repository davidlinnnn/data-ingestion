"""Reproduce the three Set P paragraph-order spot checks; no conversion/OCR."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import re

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parent
PILOT = ROOT.parents[2] / "fixtures/agent-self-evolution-pilot-2026-10-11"
CASES = [
    ("07-2504.15228v2", "2504.15228v2/sections/01_introduction.tex", [
        "have recently made impressive advancements across a range of domains and tasks",
        "These agent systems often show dramatic improvements in benchmark performance",
        "Recent improvements in coding agents raise the question of whether these agents themselves can autonomously modify",
        "Our contributions are",
        "We make our code available",
    ]),
    ("08-2505.20286v1", "2505.20286v1/templateArxiv.tex", [
        "Large language models (LLMs) have rapidly evolved from merely generating text to autonomous agents capable of independently planning",
        "However, most of the current general-purpose agents heavily rely on large-scale manual engineering",
        "In contrast to the prevailing trend of growing complexity",
        "We conduct comprehensive experiments on several benchmarks to assess Alita in real-world applications",
        "We propose a new agent architecture centered on minimal predefinition and maximal self-evolution",
        "We present Alita, a generalist agent that achieves scalable agentic reasoning with a radically simple design",
    ]),
    ("11-2508.19828v5", "2508.19828v5/latex/acl_latex.tex", [
        "Large Language Models (LLMs) have shown remarkable ability in understanding and generating natural language",
        "One early effort is the Tensor Brain framework",
        "deciding what to remember, update, or discard",
        "These challenges of retrieving and managing memory remain largely unsolved",
        "In this paper, we present Memory-R1",
        "Our contributions are summarized as follows",
        "LLMs have emerged as powerful general-purpose reasoners",
    ]),
]


def norm(text):
    # shortcut: anchor lookup ignores punctuation; never use this to judge Q4 meaning.
    return "".join(c.casefold() for c in text if c.isalnum())


def main():
    assert norm("re\ufffe\nmarkable") == norm("remarkable")
    results = []
    for stem, tex_path, anchors in CASES:
        pdf = PILOT / (stem + ".pdf")
        source = (ROOT / tex_path).read_text()
        doc = pdfium.PdfDocument(pdf)
        pages = [doc[i].get_textpage().get_text_range() for i in range(4)]
        normalized_source = norm(source)
        rows = []
        for anchor in anchors:
            needle = norm(anchor)
            assert normalized_source.count(needle) == 1, (stem, anchor, "source")
            hits = [(i + 1, norm(text).find(needle)) for i, text in enumerate(pages) if needle in norm(text)]
            assert len(hits) == 1, (stem, anchor, hits)
            page, offset = hits[0]
            rows.append({"anchor": anchor, "source_normalized_offset": normalized_source.index(needle),
                         "pdf_page": page, "pdf_normalized_offset": offset})
        source_order = sorted(range(len(rows)), key=lambda i: rows[i]["source_normalized_offset"])
        pdf_order = sorted(range(len(rows)), key=lambda i: (rows[i]["pdf_page"], rows[i]["pdf_normalized_offset"]))
        results.append({"pdf": str(pdf.relative_to(ROOT.parents[3])), "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                        "source_file": tex_path, "source_url": "https://arxiv.org/src/" + stem[3:],
                        "source_archive_sha256": hashlib.sha256((ROOT / (stem[3:] + ".source")).read_bytes()).hexdigest(),
                        "sampled_pdf_pages": [1, 2, 3, 4], "anchors": rows,
                        "source_order": source_order, "pdf_order": pdf_order,
                        "anchor_order_agrees": source_order == pdf_order})
    output = {"method": "Manually selected body paragraph anchors; unique alphanumeric-normalized lookup in source and PDFium character stream. This is a spot check, not full-sentence semantic validation.",
              "pypdfium2_version": importlib.metadata.version("pypdfium2"), "cases": results}
    (ROOT / "set-p-checks.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
