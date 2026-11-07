"""#174 held-out corpus (freeze.md §7): 20 new arXiv papers in the original corpus's three strata.

    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/heldout_corpus.py ORIGINAL DIR

ORIGINAL is the 20-paper corpus manifest. For each stratum, in the order below, the arXiv API
lists matching papers first submitted 2026-07-01..2026-10-31, newest first; papers are taken in
that order when they are not in ORIGINAL nor taken already, and their PDF has 10-50 pages and
at least 1,000 text characters per page on average. DIR (outside git) gets the PDFs and a
manifest.json the Seam B runner reads; here, heldout-corpus.json records the queries, every
candidate's disposition and each paper's arXiv id, pages and SHA-256 (no paper text).
"""

import hashlib
import io
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pypdf

HERE = Path(__file__).resolve().parent
API = "https://export.arxiv.org/api/query"
WINDOW = "submittedDate:[202607010000 TO 202610312359]"
CATS = "(cat:cs.AI OR cat:cs.CL OR cat:cs.LG OR cat:cs.MA)"
STRATA = [  # the original corpus's strata and counts; the topic word must be in the title
    ("skill_tool_procedure", 8, '(ti:skill OR ti:skills OR ti:tool OR ti:tools OR ti:procedural) '
                                'AND (abs:agent OR abs:agents) AND (abs:"self-evolving" OR '
                                'abs:"self-improving" OR abs:evolution OR abs:evolve OR abs:evolving)'),
    ("memory", 6, '(ti:memory) AND (abs:agent OR abs:agents) AND (abs:"self-evolving" OR '
                  'abs:evolving OR abs:evolution OR abs:experience)'),
    ("agent_evolution", 6, '(ti:"self-evolving" OR ti:"self-improving" OR ti:"self-evolution" OR '
                           'ti:"self-improvement") AND (ti:agent OR ti:agents OR ti:agentic)'),
]  # fmt: skip
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def listing(http: httpx.Client, query: str) -> list[dict]:
    reply = http.get(API, params={"search_query": f"({query}) AND {CATS} AND {WINDOW}",
                                  "sortBy": "submittedDate", "sortOrder": "descending",
                                  "max_results": 100})  # fmt: skip
    reply.raise_for_status()
    time.sleep(3)  # arXiv asks for one request every three seconds
    entries = []
    for e in ET.fromstring(reply.text).findall("a:entry", ATOM):
        full = e.find("a:id", ATOM).text.rsplit("/", 1)[-1]
        arxiv, version = re.fullmatch(r"(\d{4}\.\d{4,5})(v\d+)", full).groups()
        entries.append({"arxiv": arxiv, "version": version,
                        "title": " ".join(e.find("a:title", ATOM).text.split()),
                        "published": e.find("a:published", ATOM).text})  # fmt: skip
    return entries


def main(original: Path, out: Path) -> None:
    taken = {re.search(r"(\d{4}\.\d{4,5})", p["pdf_url"]).group(1)
             for p in json.loads(original.read_text())["papers"]}  # fmt: skip
    out.mkdir(parents=True, exist_ok=True)
    papers, log = [], []
    with httpx.Client(timeout=120, follow_redirects=True) as http:
        for stratum, count, query in STRATA:
            kept = 0
            for e in listing(http, query):
                if kept == count:
                    break
                if e["arxiv"] in taken:
                    log.append({**e, "stratum": stratum, "disposition": "taken"})
                    continue
                taken.add(e["arxiv"])
                url = f"https://arxiv.org/pdf/{e['arxiv']}{e['version']}"
                data = http.get(url).content
                time.sleep(3)
                try:
                    reader = pypdf.PdfReader(io.BytesIO(data))
                    pages = len(reader.pages)
                    chars = sum(len(p.extract_text() or "") for p in reader.pages) / max(pages, 1)
                except Exception as exc:  # a PDF pypdf cannot read is not a candidate
                    log.append({**e, "stratum": stratum, "disposition": f"unreadable: {exc!r}"[:200]})
                    continue
                ok = 10 <= pages <= 50 and chars >= 1000
                log.append({**e, "stratum": stratum, "pages": pages, "chars_per_page": round(chars),
                            "disposition": "kept" if ok else "pages or text layer"})  # fmt: skip
                if not ok:
                    continue
                kept += 1
                index = len(papers) + 1
                name = f"{index:02d}-{e['arxiv']}{e['version']}.pdf"
                (out / name).write_bytes(data)
                papers.append({"index": index, "file": name, "bytes": len(data), "pages": pages,
                               "sha256": hashlib.sha256(data).hexdigest(), "title": e["title"],
                               "stratum": stratum, "arxiv": e["arxiv"], "version": e["version"],
                               "pdf_url": url, "published": e["published"]})  # fmt: skip
            assert kept == count, f"{stratum}: only {kept} of {count}"
    (out / "manifest.json").write_text(json.dumps({"papers": papers}, indent=1) + "\n")
    (HERE / "heldout-corpus.json").write_text(json.dumps(
        {"window": WINDOW, "categories": CATS, "strata": [{"stratum": s, "count": c, "query": q}
                                                          for s, c, q in STRATA],
         "papers": [{k: p[k] for k in ("index", "stratum", "arxiv", "version", "pages", "sha256")}
                    for p in papers],
         "candidates": log}, indent=1) + "\n")  # fmt: skip
    print(json.dumps({"papers": len(papers), "candidates": len(log)}))


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]).expanduser())
