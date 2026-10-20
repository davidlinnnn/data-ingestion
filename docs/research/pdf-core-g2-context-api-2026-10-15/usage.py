"""Summarize observed client RTT/tokens; pricing is a dated estimate, not an invoice."""
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def ref(path):
    return {"path": str(path.relative_to(REPO)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    observations = HERE / "api/observations.json"
    rows = json.loads(observations.read_text())
    assert len(rows) == 36 and len({r["request_id"] for r in rows}) == 36
    assert all(r["http_status"] == 200 and r["finish_reason"] == "stop" and r["attempts"] == 1 for r in rows)
    times = sorted(r["client_round_trip_seconds"] for r in rows)
    prompt = sum(r["usage"]["prompt_tokens"] for r in rows)
    completion = sum(r["usage"]["completion_tokens"] for r in rows)
    total = sum(r["usage"]["total_tokens"] for r in rows)
    cached = sum(r["usage"].get("prompt_tokens_details", {}).get("cached_tokens", 0) for r in rows)
    reasoning = sum(r["usage"].get("completion_tokens_details", {}).get("reasoning_tokens", 0) for r in rows)
    assert prompt + completion == total and cached <= prompt and reasoning <= completion
    prices = {"input": .10, "cached_input": .01, "output": .50}
    estimate = ((prompt-cached)*prices["input"] + cached*prices["cached_input"] + completion*prices["output"]) / 1_000_000
    result = {"observations_ref": ref(observations), "method_ref": ref(HERE / "api/method.json"),
        "summarizer_ref": ref(Path(__file__).resolve()), "request_count": 36,
        "each_request_one_attempt": True, "all_finish_stop": True,
        "returned_models": sorted({r["returned_model"] for r in rows}),
        "client_rtt_seconds": {"sum": sum(times), "min": min(times), "median": statistics.median(times),
                               "mean": statistics.mean(times), "p95_nearest_rank": times[math.ceil(.95*len(times))-1], "max": max(times)},
        "tokens": {"prompt": prompt, "cached_prompt": cached, "completion": completion,
                   "reasoning_included_in_completion": reasoning, "total": total},
        "standard_token_rate_estimate_usd": estimate,
        "price_per_million_tokens_usd": prices,
        "price_source": "https://developers.openai.com/api/docs/models/gpt-6-luna",
        "price_observed_date": "2026-10-15",
        "limits": ["Token-rate estimate assumes standard unregionalized service; not verified billing or invoice",
                   "Usage does not establish cache-write fees, routing premiums, taxes, credits, or exact account tariff",
                   "Reasoning tokens are already included in completion and are not charged twice in this arithmetic",
                   "Client RTT includes network/remote queue/inference; no server GPU timings or production SLO",
                   "Sum is sequential request RTT only, excludes preparation, annotation, mapping and Canonical Acceptance",
                   "36 selected requests do not estimate production tail latency or high-frequency capacity"]}
    (HERE / "usage.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
