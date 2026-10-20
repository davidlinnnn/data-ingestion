"""Summarize observed client timings and token-rate estimate; no model calls."""
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / "observations.json").read_text())
assert len(rows) == 8 and all(r["http_status"] == 200 and r["finish_reason"] == "stop" for r in rows)
assert len({r["request_id"] for r in rows}) == 8
times = [r["seconds"] for r in rows]
tokens = {k: sum(r["usage"][k] for r in rows) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
tokens["reasoning_included_in_completion"] = sum(r["usage"].get("completion_tokens_details", {}).get("reasoning_tokens", 0) for r in rows)
tokens["cached_prompt_tokens"] = sum(r["usage"].get("prompt_tokens_details", {}).get("cached_tokens", 0) for r in rows)
assert tokens["prompt_tokens"] + tokens["completion_tokens"] == tokens["total_tokens"]
estimate = ((tokens["prompt_tokens"]-tokens["cached_prompt_tokens"])*0.10
            + tokens["cached_prompt_tokens"]*0.01 + tokens["completion_tokens"]*0.50)/1_000_000
result = {"requests": 8, "each_request_one_attempt": True, "model": "gpt-6-luna",
    "client_rtt_seconds": {"sum": sum(times), "median": statistics.median(times),
                           "min": min(times), "max": max(times), "mean": statistics.mean(times)},
    "tokens": tokens, "standard_token_rate_estimate_usd": estimate,
    "rate_source": "https://developers.openai.com/api/docs/models/gpt-6-luna",
    "rate_checked_on": "2026-10-15", "invoice_verified": False,
    "excluded_tariff_factors": ["account agreement", "service tier", "region", "tax", "credits"],
    "not_same_workload_as_old_36": True, "remote_gpu_timings_observed": False,
    "company_model_equivalence_claimed": False, "high_frequency_capacity_proved": False}
(HERE / "usage.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
print(json.dumps(result, ensure_ascii=False))
