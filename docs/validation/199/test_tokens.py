"""tokens.py's tables, from hand-worked receipts.

    .venv/bin/python -m pytest docs/validation/199/test_tokens.py
"""

import tokens


def receipt(method: str, usage: dict | None, model: str | None = "gpt-6-luna") -> dict:
    return {"item_id": "i", "method": method, "result": "ok" if usage else "unavailable",
            "usage": usage, "model": model}  # fmt: skip


def row(report: dict, request_id: str, component: str) -> dict:
    (found,) = [r for r in report["rows"] if (r["request_id"], r["component"]) == (request_id, component)]
    return found


def test_a_row_sums_one_components_requests_and_tokens():
    paper = {"request_id": "req_a", "pages": 10, "receipts": [
        receipt("formula@1", {"prompt_tokens": 1000, "completion_tokens": 600,
                              "completion_tokens_details": {"reasoning_tokens": 400}}),
        receipt("formula@1", {"prompt_tokens": 500, "completion_tokens": 100,
                              "completion_tokens_details": {"reasoning_tokens": 0}}),
        receipt("document-summary@2", {"prompt_tokens": 3000, "completion_tokens": 200},
                "claude-sonnet-5-5"),
    ]}  # fmt: skip
    report = tokens.report([paper])
    assert row(report, "req_a", "formula") == {
        "request_id": "req_a", "pages": 10, "component": "formula", "requests": 2,
        "input_tokens": 1500, "output_tokens": 700, "reasoning_tokens": 400, "unmeasured": 0,
        "models": ["gpt-6-luna"],
    }  # fmt: skip
    summary = row(report, "req_a", "document-summary")
    assert (summary["input_tokens"], summary["output_tokens"]) == (3000, 200)
    assert summary["reasoning_tokens"] is None  # the usage does not report it
    # every component has a row, also one that sent nothing
    assert row(report, "req_a", "code")["requests"] == 0
    assert {r["component"] for r in report["rows"]} == {
        "picture-interpretation", "formula", "code", "document-summary", "d3-check"}  # fmt: skip


def test_sends_without_token_counts_are_counted_as_unmeasured():
    paper = {"request_id": "req_a", "pages": 10, "receipts": [
        receipt("d3-check@1", {}, "d3-mini"),  # a reply without usage
        receipt("d3-check@1", {"input_tokens": 672}, "d3-mini"),
        receipt("picture-interpretation@1", None, None),  # no reply: deadline passed
    ]}  # fmt: skip
    report = tokens.report([paper])
    d3 = row(report, "req_a", "d3-check")
    assert (d3["requests"], d3["input_tokens"], d3["output_tokens"], d3["unmeasured"]) == (2, 672, 0, 1)
    picture = row(report, "req_a", "picture-interpretation")
    assert (picture["requests"], picture["input_tokens"], picture["unmeasured"]) == (1, 0, 1)
    assert picture["models"] == []


def test_aggregates_and_tpm_at_the_pilot_and_prod_peak_arrival_rates():
    a = {"request_id": "req_a", "pages": 10, "receipts": [
        receipt("formula@1", {"prompt_tokens": 1000, "completion_tokens": 1000}),
        receipt("document-summary@2", {"prompt_tokens": 2000, "completion_tokens": 0}),
        receipt("d3-check@1", {"input_tokens": 1000}),
    ]}  # fmt: skip
    b = {"request_id": "req_b", "pages": 40, "receipts": [
        receipt("picture-interpretation@1", {"prompt_tokens": 3000, "completion_tokens": 1000}),
        receipt("document-summary@2", {"prompt_tokens": 4000, "completion_tokens": 0}),
        receipt("d3-check@1", {"input_tokens": 2000}),
    ]}  # fmt: skip
    report = tokens.report([a, b])
    assert report["documents"] == [
        {"request_id": "req_a", "pages": 10, "tokens": 5000, "tokens_per_page": 500.0},
        {"request_id": "req_b", "pages": 40, "tokens": 10000, "tokens_per_page": 250.0},
    ]
    assert report["aggregate"]["per_document"] == {"median": 7500, "max": 10000}
    assert report["aggregate"]["per_page"] == {"median": 375.0, "max": 500.0}
    assert report["aggregate"]["shares"] == {
        "picture-interpretation": 0.267, "formula": 0.133, "code": 0.0,
        "document-summary": 0.4, "d3-check": 0.2}  # fmt: skip
    # mean tokens per document x documents per minute: 0.5 (pilot), 50 (PROD peak)
    assert report["tpm"] == {
        "pilot": {"vlm": 1500, "summary": 1500, "d3": 750, "total": 3750},
        "prod_peak": {"vlm": 150000, "summary": 150000, "d3": 75000, "total": 375000},
    }
