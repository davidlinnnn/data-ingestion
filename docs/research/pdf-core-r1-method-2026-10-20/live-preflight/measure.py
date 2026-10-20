"""Offline measurements, with unresolved model tokenization kept explicit."""
from decimal import Decimal
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys

import protocol as p

# Reuse an installed tokenizer without altering either retained runtime.
TOKENIZER_SITE = "/private/tmp/pdf-core-paddle-join-20261020/venv/lib/python3.12/site-packages"
sys.path.append(TOKENIZER_SITE)
os.environ["TIKTOKEN_CACHE_DIR"] = str(p.HERE / "tokenizer-cache")
import tiktoken


def main():
    encoder = tiktoken.get_encoding("o200k_base")
    try:
        mapped = tiktoken.encoding_for_model(p.MODEL).name
    except KeyError:
        mapped = None
    jobs = p.read(p.R1 / "planning/jobs.json")["jobs"]
    rows = []
    for job in jobs:
        body = p.materialize(job)
        text = [body["messages"][0]["content"], body["messages"][1]["content"][0]["text"]]
        # Count actual text strings; image base64 is not text-token input.
        text_tokens = sum(len(encoder.encode(value, disallowed_special=())) for value in text)
        minimum = p.mock_payload(job)
        rows.append({"job_id": job["job_id"], "task": job["task"], "baseline": job["baseline"],
            "physical_pages": job["binding"]["pages"], "request_sha256": p.sha(p.encoded(body)),
            "request_bytes": len(p.encoded(body)), "text_UTF8_bytes": sum(len(t.encode()) for t in text),
            "text_tokens_o200k_base_PROXY": text_tokens, "model_text_tokens_confirmed": None,
            "chat_framing_tokens_confirmed": None, "image_tokens_official_estimate": None,
            "input_tokens_estimate": None, "input_reservation_live_verified": False,
            "endpoint_capacity_input_ceiling_NOT_estimate": 922000,
            "image_dimensions": [a["pixels"] for a in job["image_assets"]],
            "image_count": len(job["image_assets"]), "completion_cap": body["max_completion_tokens"],
            "minimal_MOCK_response_tokens_PROXY": len(encoder.encode(json.dumps(minimum,ensure_ascii=False),disallowed_special=())),
            "cost_estimate_USD": None,
            "capacity_cost_ceiling_USD_including_cache_write": str(
                Decimal(922000)*Decimal(5)/Decimal(1000000) +
                Decimal(body["max_completion_tokens"])*Decimal(15)/Decimal(1000000)),
            "needs_split": "UNDETERMINED_IMAGE_AND_TOKENIZER_RULES",
            "input_byte_ceiling_pass": len(p.encoded(body)) <= 16777216})
    result = {"model": p.MODEL, "endpoint": p.ENDPOINT, "job_count": len(rows),
        "tokenizer": {"library_version":tiktoken.__version__, "encoding_used_for_proxy":"o200k_base",
            "installed_model_mapping":mapped, "official_model_mapping_verified":False,
            "reason":"Retained tiktoken has no gpt-6.1-sol mapping; official sources fetched do not specify its encoding."},
        "image_rule_verified":False,
        "image_rule_reason":"Official vision sizing/multiplier tables and calculator text omit gpt-6.1-sol; do not substitute Astra or GPT-5 rules.",
        "totals": {"text_tokens_o200k_base_PROXY":sum(x["text_tokens_o200k_base_PROXY"] for x in rows),
            "input_tokens_estimate":None,"official_image_tokens_estimate":None,
            "completion_cap":sum(x["completion_cap"] for x in rows),
            "request_bytes":sum(x["request_bytes"] for x in rows),
            "input_capacity_ceiling_NOT_estimate":922000*len(rows),
            "cost_estimate_USD":None,
            "output_only_ceiling_at_short_context_USD":str(Decimal(sum(x["completion_cap"] for x in rows))*Decimal(10)/Decimal(1000000)),
            "capacity_cost_ceiling_USD_including_cache_write":str(sum(Decimal(x["capacity_cost_ceiling_USD_including_cache_write"]) for x in rows))},
        "pricing_basis":{"input_per_million_USD":2,"output_per_million_USD":10,
            "cache_write_per_million_USD":2.5,"long_input_threshold":272000,
            "long_input_multiplier":2,"long_output_multiplier":1.5,
            "tier":"Standard; no fast, regional premium, tools or cache savings assumed",
            "capacity_ceiling_explanation":"At most 922000 input/job, all charged as long-context cache writes ($5/M), output at $15/M; finite API-capacity bound, not a practical estimate or approved budget."},
        "largest_five_by_text_PROXY":sorted(rows,key=lambda x:x["text_tokens_o200k_base_PROXY"],reverse=True)[:5],
        "jobs":rows,"new_inference_calls":0,"live_ready":False}
    (p.HERE/"token-budget.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("jobs","largest_five_by_text_PROXY")}))


if __name__ == "__main__":
    os.environ.pop("OPENAI_API_KEY",None)
    sys.addaudithook(lambda event,args: (_ for _ in ()).throw(RuntimeError("network forbidden"))
        if event in {"socket.connect","socket.getaddrinfo"} else None)
    main()
