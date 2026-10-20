# G2 temporary GPT-6 Luna API probe — request facts

Verified 2026-10-14 with the OpenAI Docs skill. Documentation research only: no API requests, credentials, environment lookup, SDK installation, or account-access check.

Use the user's exact `gpt-6-luna` and `https://api.openai.com/v1/chat/completions`. The [official model page](https://developers.openai.com/api/docs/models/gpt-6-luna) lists image input, Chat Completions, and `low` reasoning. Model availability for this account remains an execution check. Preserve the returned model identity; this is a temporary hosted comparison candidate, not company Qwen3 evidence.

## Minimal request shape

This is a syntactically valid JSON template, not an executable request: replace the image placeholder in memory, and use the task's frozen prompt/output contract and chosen cap. Authentication is an HTTP header and is intentionally absent.

```json
{
  "model": "gpt-6-luna",
  "reasoning_effort": "low",
  "max_completion_tokens": 8192,
  "response_format": {"type": "json_object"},
  "store": false,
  "messages": [
    {
      "role": "system",
      "content": "Read the supplied source image. Return one JSON object following the requested task contract. Preserve uncertainty and do not invent missing content."
    },
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "TASK_SPEC_AND_JSON_OUTPUT_CONTRACT"},
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,IMAGE_BYTES_PLACEHOLDER",
            "detail": "high"
          }
        }
      ]
    }
  ]
}
```

The [Chat reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) defines the nested `image_url` object and `detail`, `max_completion_tokens`, `response_format`, and `store`. The completion cap includes reasoning and visible tokens. The 8192 value above is an exploratory budget, not an accepted production limit. Chat uses `reasoning_effort`; Responses uses a different envelope. For `low` reasoning, omit `temperature`, `top_p`, `logprobs`, and `top_logprobs`, per the [GPT-6 guide](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-luna). No tools are needed for these image-to-text probes.

The [vision guide](https://developers.openai.com/api/docs/guides/images-vision) documents base64 data URLs and `high` detail. Its current sizing table does not state GPT-6 Luna's exact preprocessing/patch limits. Therefore `high` is the explicit request setting; no claim that the service keeps native dimensions or uses another model's image limits follows. Retain source PNG hash/dimensions and external PDF locator mapping; any model-returned coordinates need validation before use.

## JSON and response checks

JSON mode is not schema enforcement. The [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs) requires an explicit JSON instruction and describes incomplete-output edge cases. Validate the returned object, required keys/types, and task invariants locally; valid JSON alone proves no source fidelity. A subsequent `json_schema` trial would be a separately recorded request configuration, not a silent repair.

Before scoring, preserve the response, then check HTTP success, expected choice/message shape, refusal, nonempty content, JSON parsing, and task contract. Record `finish_reason`, usage including reasoning tokens when available, returned model, request ID, elapsed time, and input/prompt/settings hashes. Treat `length`, filtering, refusal, or transport failure as incomplete/unavailable execution outcomes rather than ordinary model-quality failures. The [Chat reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) defines those finish reasons. Avoid unbounded or silent retries; retain each attempted configuration separately.

`store:false` selects the Chat completion-storage option; it is not a claim of zero provider retention or an organizational privacy setting. Keep Authorization and credentials out of persisted method/request logs. The planned `getpass`/stdin handling belongs to the root execution lane, not this research note.

## Direct probe versus Docling integration

The installed prototype's `docling/models/inference_engines/vlm/api_openai_compatible_engine.py` injects `temperature=input_data.temperature` (normally 0) and `max_tokens`; an explicit `max_completion_tokens` removes `max_tokens`, but does not remove temperature. It also projects the provider response into text/stop/token metadata. Read source before trying a reasoning-enabled GPT-6 call through that engine; do not assume a preset alone produces the template above. This is an installed-code observation, not a claim about all Docling versions.

A minimal direct `httpx` request can preserve the complete provider response and avoid those inherited parameters. It establishes the selected remote model's task result on a frozen image/prompt. It does **not** validate Docling APIengine compatibility, full PDF detection, automatic crop selection, DocTags parsing, caption association, Canonical backfill, company Qwen3 accuracy, or GPU/high-frequency throughput. Keep task results separate from those integration gates.

Checked locally: fenced JSON parses; exact model/endpoint, nested Chat image shape, low reasoning and JSON mode were compared to the cited official pages. No live acceptance/quality result is claimed here.
