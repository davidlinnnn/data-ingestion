"""#199: requests and tokens per document and component, from the receipts of external requests.

    env KP_S3_ENDPOINT=... KP_S3_BUCKET=... AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \\
        .venv/bin/python docs/validation/199/tokens.py OUT_JSON [REQUEST_ID ...]

Reads the bucket's receipts (requests/{request_id}/attempts/*/receipts/...), one per send, of
the requests named, or of every request with a result or failure report. Writes OUT_JSON and
prints the tables: per document and component the requests, input, output and reasoning tokens
(when the usage reports them; a send without token counts is unmeasured), tokens per document
and per page, each component's share, and TPM at the pilot's and PROD's arrival rates. #203
runs it against the company environment's bucket.
"""

import asyncio
import json
import statistics
import sys
from pathlib import Path

from kp_canonicalization.ports.object_store import S3ObjectStore

COMPONENTS = {"picture-interpretation": "vlm", "formula": "vlm", "code": "vlm",
              "document-summary": "summary", "d3-check": "d3"}  # fmt: skip
# Documents per minute: the pilot's peak, 5 per 10 minutes (#93 section 8.1), and PROD's burst,
# 50 per minute for 10 minutes (the user, 2026-11-04).
RATES = {"pilot": 0.5, "prod_peak": 50.0}


def counts(usage: dict | None) -> tuple[int, int, int | None] | None:
    """(input, output, reasoning) tokens of an OpenAI-style or System One usage object; None when
    it counts no tokens. reasoning is None when the usage does not report it."""
    usage = usage or {}
    sent = usage.get("prompt_tokens", usage.get("input_tokens"))
    received = usage.get("completion_tokens", usage.get("output_tokens"))
    if sent is None and received is None:
        return None
    return sent or 0, received or 0, (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")


def row(paper: dict, component: str) -> dict:
    sent = [r for r in paper["receipts"] if r["method"].rpartition("@")[0] == component]
    measured = [c for c in map(counts, (r.get("usage") for r in sent)) if c is not None]
    reasoning = [c[2] for c in measured if c[2] is not None]
    return {
        "request_id": paper["request_id"], "pages": paper["pages"], "component": component,
        "requests": len(sent), "input_tokens": sum(c[0] for c in measured),
        "output_tokens": sum(c[1] for c in measured),
        "reasoning_tokens": sum(reasoning) if reasoning else None,
        "unmeasured": len(sent) - len(measured),
        "models": sorted({r["model"] for r in sent if r.get("model")}),
    }  # fmt: skip


def report(papers: list[dict]) -> dict:
    """papers: [{"request_id", "pages", "receipts"}]. A request's tokens are input + output;
    an OpenAI-style output count already holds the reasoning tokens. TPM at an arrival rate is
    the mean tokens per document times documents per minute."""
    rows = [row(paper, component) for paper in papers for component in COMPONENTS]
    tokens = lambda r: r["input_tokens"] + r["output_tokens"]  # noqa: E731
    documents = []
    for paper in papers:
        total = sum(tokens(r) for r in rows if r["request_id"] == paper["request_id"])
        documents.append({"request_id": paper["request_id"], "pages": paper["pages"],
                          "tokens": total,
                          "tokens_per_page": total / paper["pages"] if paper["pages"] else None})  # fmt: skip
    totals = [d["tokens"] for d in documents]
    per_page = [d["tokens_per_page"] for d in documents if d["tokens_per_page"] is not None]
    everything = sum(totals)
    by_service = {s: sum(tokens(r) for r in rows if COMPONENTS[r["component"]] == s) / len(papers)
                  for s in ("vlm", "summary", "d3")}  # fmt: skip
    by_service["total"] = sum(by_service.values())
    return {
        "rows": rows,
        "documents": documents,
        "aggregate": {
            "per_document": {"median": statistics.median(totals), "max": max(totals)},
            "per_page": {"median": statistics.median(per_page), "max": max(per_page)}
            if per_page else None,
            "shares": {c: round(sum(tokens(r) for r in rows if r["component"] == c)
                                / (everything or 1), 3) for c in COMPONENTS},
        },  # fmt: skip
        "tpm": {name: {s: round(n * rate) for s, n in by_service.items()}
                for name, rate in RATES.items()},
    }  # fmt: skip


async def from_store(store, request_ids: list[str]) -> list[dict]:
    """report()'s papers from an object store: each request's receipts, and its pages from its
    Processing Result (None for a request that failed)."""
    papers = []
    for request_id in request_ids:
        prefix = f"requests/{request_id}"
        pages = None
        if await store.head(f"{prefix}/result.json") is not None:
            pages = len(json.loads(await store.get(f"{prefix}/result.json"))["native"]["page_images"])
        keys = sorted(k for k in await store.list_prefix(f"{prefix}/attempts/") if "/receipts/" in k)
        papers.append({"request_id": request_id, "pages": pages,
                       "receipts": [json.loads(await store.get(k)) for k in keys]})  # fmt: skip
    return papers


def markdown(report: dict, labels: dict[str, str] | None = None) -> str:
    """The tables of report(), each document named by labels (default: its request ID)."""
    name = lambda request_id: (labels or {}).get(request_id, request_id)  # noqa: E731
    lines = ["| Document | Pages | Component | Requests | Input | Output | Reasoning | Model |",
             "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in report["rows"]:
        if r["requests"] and r["unmeasured"] == r["requests"]:
            sent = received = "not measured"
        else:
            sent, received = f"{r['input_tokens']:,}", f"{r['output_tokens']:,}"
            sent += f" ({r['unmeasured']} sends unmeasured)" if r["unmeasured"] else ""
        reasoning = "—" if r["reasoning_tokens"] is None else f"{r['reasoning_tokens']:,}"
        lines.append(f"| {name(r['request_id'])} | {r['pages']} | {r['component']} | {r['requests']} "
                     f"| {sent} | {received} | {reasoning} | {', '.join(r['models'])} |")  # fmt: skip
    lines += ["", "| Document | Pages | Tokens | Tokens per page |", "|---|---|---|---|"]
    for d in report["documents"]:
        per_page = "—" if d["tokens_per_page"] is None else f"{d['tokens_per_page']:,.0f}"
        lines.append(f"| {name(d['request_id'])} | {d['pages']} | {d['tokens']:,} | {per_page} |")
    a = report["aggregate"]
    lines += ["", "| | Median | Max |", "|---|---|---|",
              f"| Tokens per document | {a['per_document']['median']:,.0f} | {a['per_document']['max']:,} |",
              f"| Tokens per page | {a['per_page']['median']:,.0f} | {a['per_page']['max']:,.0f} |"
              if a["per_page"] else "| Tokens per page | — | — |",
              "", "| Component | Share of tokens |", "|---|---|"]  # fmt: skip
    lines += [f"| {c} | {share:.1%} |" for c, share in a["shares"].items()]
    lines += ["", "| TPM | VLM | Summary | d3 | Total |", "|---|---|---|---|---|"]
    for rate, tpm in report["tpm"].items():
        lines.append(f"| {rate} ({RATES[rate]:g} documents/min) | {tpm['vlm']:,} | "
                     f"{tpm['summary']:,} | {tpm['d3']:,} | {tpm['total']:,} |")  # fmt: skip
    return "\n".join(lines) + "\n"


async def main(out: Path, request_ids: list[str]) -> None:
    store = S3ObjectStore.from_env()
    if not request_ids:
        keys = await store.list_prefix("requests/")
        request_ids = sorted({k.split("/")[1] for k in keys
                              if k.endswith(("/result.json", "/failure.json"))})  # fmt: skip
    result = report(await from_store(store, request_ids))
    out.write_text(json.dumps(result, indent=1) + "\n")
    print(markdown(result))


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), sys.argv[2:]))
