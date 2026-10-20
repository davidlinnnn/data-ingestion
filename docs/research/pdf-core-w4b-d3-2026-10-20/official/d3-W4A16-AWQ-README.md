---
pipeline_tag: zero-shot-classification
license: apache-2.0
base_model: vllm-sr/d3
base_model_relation: quantized
library_name: transformers
tags:
- zero-shot-classification
- decision-model
- classification
- system-one
- multimodal
- vision
- video
- safetensors
- quantized
- compressed-tensors
- awq
- w4a16
---

![d3: Decision 3.0](assets/banner.png)

# d3-W4A16-AWQ

**d3-W4A16-AWQ** is [d3](https://huggingface.co/vllm-sr/d3), the 27B multimodal foundation decision model of Decision 3.0, with its decoder's projections in int4 rounded by AWQ. Give it an input (text or JSON, optionally with images and videos) and the questions you need answered: pick one of several options, say yes or no, or rate on a scale. It answers them all in one call and returns a probability for every answer, as d3 does, in 16.2 GB of weights instead of 52.2 GB.

| | |
| --- | --- |
| **Parameters** | 26.09B, including the 0.46B vision encoder |
| **Base model** | [vllm-sr/d3](https://huggingface.co/vllm-sr/d3) at revision `cbff3a3c` (v3.1.0, the same weights as the current main) |
| **Quantization** | INT4 weight-only W4A16 (compressed-tensors `pack-quantized`): asymmetric int4 weights with zero points in groups of 128 with BF16 scales, from AWQ (activation-aware scales folded into the preceding norms and `up_proj`, clipping searched per row and group); activations stay in BF16. 400 projections; the Gated DeltaNet `in_proj_a` / `in_proj_b`, the vision tower, the embeddings and the readout stay as published, except where the scales were folded |
| **Calibration data** | 128 text prompts from the first train shard of [tasksource-jev-typed-decisions](https://huggingface.co/datasets/tasksource/tasksource-jev-typed-decisions), rendered with d3's prompt template |
| **Weights on disk** | 16.2 GB (d3: 52.2 GB) |
| **Needs** | No special matrix units: a GPU with about 18 GB free. Tested on AMD Instinct MI300X with `d3q/` and with the vLLM Semantic Router model runtime |
| **Inputs** | Text or JSON, plus images and videos (several per request) |
| **Decision types** | Choice · Yes / No · Score |
| **License** | Apache-2.0 |

## Highlights

- **Scores 65.00 on the Jev Decision Index 0.3 public suite** against d3's 65.45, giving d3's top answer on 97.80% of its 312,320 questions; every area within 0.8 points of d3.
- **Keeps 97.76% of d3's answers** on the 14,031 test requests of tasksource-jev-typed-decisions, with accuracy 83.09% against d3's 83.25%.
- **16.5 GB of GPU memory for the weights instead of 52.2 GB** with the vLLM Semantic Router model runtime on one AMD Instinct MI300X, and 17.5 GB at the peak of the 20 longest requests.
- **1.29× d3's latency on the same GPU:** 62.0 ms against 48.2 ms per request (median) in the model runtime on one MI300X, both in one process. The int4 layers unpack their weights to BF16 for every product, so they save memory rather than time.
- **Reads images and videos** as d3 does: the vision tower is unchanged. On the vision board's public suite it scores 73.53 against d3's 74.15 and gives d3's top answer on 95.79% of its 12,210 questions.
- **Perception Test:** 77.30% on all 19,140 validation questions against d3's 77.57% on the same machine, giving d3's top answer on 95.42% of them.

## Quickstart

```bash
pip install "transformers==5.17.0" "compressed-tensors>=0.17" torch torchvision triton pillow opencv-python-headless safetensors accelerate
pip install flash-linear-attention  # optional: fast GPU kernels for the linear-attention layers
```

```python
import json
import sys

from huggingface_hub import hf_hub_download, snapshot_download

path = snapshot_download("vllm-sr/d3-W4A16-AWQ")
sys.path.insert(0, path)
from d3q.load import load_d3

model = load_d3(path, device="cuda:0")

# Text
result = model.system_one(
    state="The order arrived damaged yesterday. The customer has a receipt and asks for a replacement today.",
    questions={
        "route": {
            "type": "choice",
            "instructions": "Which team should handle this request?",
            "criteria": {
                "returns": "Refunds, replacements and damaged deliveries",
                "billing": "Payments, invoices and charges",
                "technical": "Product setup and faults"
            }
        },
        "receipt": {
            "type": "noul",
            "instructions": "Does the customer have a receipt?"
        },
        "urgency": {
            "type": "score",
            "instructions": "How urgent is this request?",
            "criteria": [
                "Routine",
                "Soon",
                "Today"
            ]
        }
    },
)
print(json.dumps(result["answers"], indent=2))

# Text and an image (or several)
receipt = hf_hub_download("vllm-sr/d3-W4A16-AWQ", "assets/example-receipt.png")
result = model.system_one(
    state="The customer says the blender arrived cracked and attached the receipt.",
    images=[receipt],  # local paths, http(s) URLs, PIL images or base64 data URLs
    questions={
        "on_receipt": {
            "type": "noul",
            "instructions": "Does the receipt list the blender?"
        }
    },
)
print(json.dumps(result["answers"], indent=2))

# Text and a video (or several)
clip = hf_hub_download("vllm-sr/d3-W4A16-AWQ", "assets/example-video.mp4")
result = model.system_one(
    state="A short clip from a test camera.",
    videos=[clip],  # local paths, http(s) URLs, base64 data URLs or frame arrays
    questions={
        "color_change": {
            "type": "noul",
            "instructions": "Does the square change color?"
        }
    },
)
print(json.dumps(result["answers"], indent=2))
```

`load_d3` is d3's own runtime (`d3_runtime.py`) with its backbone loader swapped for `d3q/`: transformers loads the checkpoint with its int4 weights still packed, and each quantized projection becomes a layer that unpacks its weights to BF16 with one Triton kernel on every call and multiplies in BF16. Prompting, noncausal full attention, the FP32 readout, images and videos are d3's own; images and videos are read as d3 reads them. `AutoModel.from_pretrained(..., trust_remote_code=True)` alone does not run these weights.

## Run with vLLM Semantic Router

[vLLM Semantic Router](https://github.com/vllm-project/semantic-router) serves d3-W4A16-AWQ in Engine mode, which runs one model behind the System One API on your own machine, as it serves d3. It verifies the package against its `MODEL_MANIFEST.json`, as it verifies d3, and keeps the weights in int4 on the GPU, with its own int4 layers rather than `d3q/`.

```bash
curl -fsSL https://vllm-sr.ai/install.sh | bash -s -- --channel dev --no-launch
export PATH="$HOME/.local/bin:$PATH"
vllm-sr serve -e vllm-sr/d3-W4A16-AWQ
```

The platform is detected automatically; choose one with `--platform auto|cpu|cuda|rocm` (default `auto`), and a commit with `--revision`. Int4 needs no special matrix units, only about 18 GB of free GPU memory (see **Needs** above). Then ask questions about a request:

```bash
curl -s localhost:8899/v1/systemone -H 'content-type: application/json' -d '{
  "model": "vllm-sr/d3-W4A16-AWQ",
  "state": "Write a Python function that merges two sorted lists.",
  "questions": {
    "kind": {"type": "choice", "instructions": "What kind of work is this?",
             "criteria": {"code": "Writing or fixing code", "math": "Mathematics", "chat": "Anything else"}},
    "reasoning": {"type": "noul", "instructions": "Does answering this need multi-step reasoning?"}
  }
}'
```

Images and videos go in `images` and `videos` as for d3. `vllm-sr stop` stops it. See [Router and Engine modes](https://github.com/vllm-project/semantic-router/blob/main/src/vllm-sr/INSTANCE_MODES.md#ask-about-images-and-videos) for limits and options.

### Serving performance

**On one AMD Instinct MI300X, the model runtime answers a request in 62.0 ms against d3's 48.2 ms** (median, one request at a time, graphs replaying, both in one process), in 16.5 GB of GPU memory against 52.2 GB.

| GPU | | d3 (BF16) | d3-W4A16-AWQ | Ratio |
| --- | --- | ---: | ---: | ---: |
| AMD Instinct MI300X | Median latency, graphs (500 requests) | 48.2 ms | 62.0 ms | 1.29× |
| | p95 latency, graphs | 130.8 ms | 140.6 ms | 1.07× |
| | Median latency, no graphs (1,000 requests) | 72.5 ms | 86.9 ms | 1.20× |
| | GPU memory after loading | 52.2 GB | 16.5 GB | 0.32× |
| | GPU memory, peak of the 20 longest requests | 52.9 GB | 17.5 GB | 0.33× |

- **Graphs:** replaying the forward as a graph ([#4999](https://github.com/vllm-project/semantic-router/pull/4999)) takes d3 from 72.5 to 48.2 ms on the MI300X and this package from 86.9 to 62.0 ms.
- **Kernels:** each int4 layer unpacks its weights to BF16 with one Triton kernel on every call and then multiplies in BF16: the int4 layers save memory, not time. Under the runtime's approximate profile (`max_speed`), NVIDIA GPUs multiply straight from the packed weights for inputs of up to 256 rows instead.
- **NVIDIA GPUs:** not measured for this package; see [d3-W4A16-GPTQ](https://huggingface.co/vllm-sr/d3-W4A16-GPTQ) for the same int4 layers on an RTX PRO 6000.
- **Throughput under load:** not measured yet.

<sub>Latency and memory measured on 2026-10-16 on one AMD Instinct MI300X: ROCm image with PyTorch 2.12, Triton 3.7.1 and FLA 0.5.2, with the vLLM Semantic Router model runtime of [#5066](https://github.com/vllm-project/semantic-router/pull/5066) as of 2026-10-14 with the graph capture of #4999, exact profile, and the same weights as this revision. Requests: the 1,000 train rows of tasksource-jev-typed-decisions in the #5066 record, one question each. Both packages loaded in one process; every request answered by both in turn, alternating which goes first, the device synchronized around each: the first 500 rows answered a third time so that their shape's graph replays, or all 1,000 a second time without graphs. Memory: the runtime's weight bytes after loading and the peak allocated over the 20 longest of those rows (up to 5,928 characters of state), each package in its own process.</sub>

## Evaluation

### Text: Jev Decision Index 0.3, public suite

| | d3 (BF16) | d3-W4A16-AWQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| Public index ↑ | 65.45 | **65.00 (−0.45)** | 97.80% |
| &nbsp;&nbsp;Knowledge & Reasoning | 55.26 | 54.62 (−0.64) | 94.83% |
| &nbsp;&nbsp;Language Understanding | 68.04 | 67.39 (−0.65) | 99.10% |
| &nbsp;&nbsp;Retrieval & Classification | 66.86 | 66.72 (−0.14) | 98.53% |
| &nbsp;&nbsp;Tools & Automation | 82.57 | 82.46 (−0.11) | 99.06% |
| &nbsp;&nbsp;Arts & Human Taste | 51.02 | 50.27 (−0.75) | 96.02% |
| Raw index ↑ | 74.01 | 73.69 (−0.32) | – |
| Requests answered | 140,178 | 140,178 | – |

The five areas are the index's areas (chance-corrected skill; the public index averages them with fixed weights), with differences from d3 in parentheses. Agreement compares the top answer of every question with d3's official run (choice and score: the highest-probability option; yes / no: p ≥ 0.5): 312,320 questions in all, and per area the questions of that area's benchmarks. [d3-FP8](https://huggingface.co/vllm-sr/d3-FP8) scores 65.40 with 99.15% agreement on the same suite.

The complete public suite (every request of d3's official run), run with the official kit ([apolinario/decision-index](https://github.com/apolinario/decision-index) `f8552a1`) through d3's own `d3_engine.py` with the backbone loaded by `d3q/`, and scored by it, against d3's official run in [vllm-sr/d3-decision-index](https://huggingface.co/datasets/vllm-sr/d3-decision-index), on one AMD Instinct MI300X, finished on 2026-10-16. The board's full score (66.3 for d3) also needs private tests that only the maintainers run, so it is not measured here: compare with d3's public 65.45, not 66.3.

Also on the test split of [tasksource/tasksource-jev-typed-decisions](https://huggingface.co/datasets/tasksource/tasksource-jev-typed-decisions):

| | d3 (BF16) | d3-W4A16-AWQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| Accuracy | 83.25% | 83.09% | 97.76% (314 of 14,031 answers changed) |

Every usable row of the split at revision `28c39125` (a state of at most 6,000 characters, no repeated options): 14,031 requests of one question each, answered by the vLLM Semantic Router model runtime on one AMD Instinct MI300X. Agreement compares the top answer of every question with d3 on the same requests (choice and score: the highest-probability option; yes / no: p ≥ 0.5). None of the 128 calibration states appears in the test split.

### Images: Jev Decision Index vision board 0.3.2

| | d3 (BF16) | d3-W4A16-AWQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| Public vision index ↑ | 74.15 | **73.53 (−0.62)** | 95.79% |

<details>
<summary>By benchmark (chance-corrected skill, %)</summary>

| Benchmark | Questions | d3 (BF16) | d3-W4A16-AWQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: | ---: |
| CV-Bench | 2,038 | 76.28 | 75.96 (−0.32) | 98.58% |
| BLINK | 961 | 60.05 | 58.44 (−1.61) | 97.29% |
| RealWorldQA | 589 | 73.36 | 70.87 (−2.49) | 96.77% |
| CharXiv | 532 | 79.45 | 81.45 (+2.00) | 96.62% |
| InfographicVQA | 244 | 97.81 | 98.36 (+0.55) | 99.59% |
| Mind2Web | 973 | 84.10 | 82.87 (−1.23) | 97.43% |
| Winoground | 800 | 85.75 | 85.75 (±0.00) | 98.88% |
| KIE (CORD+FUNSD) | 2,465 | 92.65 | 92.65 (±0.00) | 99.59% |
| Moderation (Hateful Memes) | 1,213 | 45.42 | 43.94 (−1.48) | 96.70% |
| R-Bench-M | 665 | 33.22 | 30.70 (−2.52) | 81.50% |
| MMMU-Pro vision | 1,730 | 45.84 | 45.17 (−0.67) | 87.63% |

</details>

All 12,210 rows of the kit's public vision suite (11 benchmarks, matching the kit's pinned hashes), one image request per row, run with the official kit ([apolinario/decision-index](https://github.com/apolinario/decision-index) `f8552a1`) through `d3q_engine.py` on one AMD Instinct MI300X on 2026-10-15 and scored by it. d3 (BF16) is the run reported in [d3-W4A16-GPTQ](https://huggingface.co/vllm-sr/d3-W4A16-GPTQ), made on another machine, which scores 74.15 against the official vision board's 74.1. d3 itself scores 73.93 on this MI300X, so differences of a few tenths are within what changes between machines. Agreement compares the top answer of every question with that same-machine d3 run (choice: the highest-probability option; yes / no: p ≥ 0.5).

### Videos: Perception Test

| | d3 (BF16) | d3-W4A16-AWQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| All 19,140 questions (validation) ↑ | 77.57 | **77.30 (−0.27)** | 95.42% |

<details>
<summary>By area (accuracy, %)</summary>

| Area | Questions | d3 (BF16) | d3-W4A16-AWQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: | ---: |
| Abstraction | 5,607 | 71.14 | 70.41 (−0.73) | 93.65% |
| Memory | 746 | 80.70 | 81.77 (+1.07) | 95.44% |
| Physics | 6,938 | 73.05 | 72.74 (−0.31) | 94.83% |
| Semantics | 5,849 | 88.68 | 88.73 (+0.05) | 97.81% |

</details>

Every multiple-choice question of Perception Test validation (19,140 questions over 5,260 videos, three options each, chance 33.3): one request per video with all its questions and the state "A video.", videos read with d3's defaults, through `d3q/` on one AMD Instinct MI300X on 2026-10-14. d3 (BF16) answered the same requests the same way on the same machine and scores 77.57; d3's card reports 77.4 from its internal evaluation, whose prompt may differ.

<sub>Evaluated on one AMD Instinct MI300X: ROCm 7.2 image with PyTorch 2.12, Triton 3.7.1, transformers 5.17.0 and FLA 0.5.2, with `causal_conv1d` on its torch reference as in d3's official run. Record: [decision3-quantized.md](https://github.com/vllm-project/semantic-router/blob/main/src/model-runtime/docs/records/decision3-quantized.md) in #5066. Built by `awq.py` in [bench/d3-quant-eval](https://github.com/subin9/semantic-router/tree/research/d3-quant-eval/bench/d3-quant-eval) on the same MI300X in 12 minutes: for each group of projections that read one input (`q/k/v_proj`; `in_proj_qkv/z` with `in_proj_a/b`; `gate/up_proj`; `down_proj`), a per-input-channel scale x^a / w^(1-a) is searched over a in [0, 1) to minimise the squared error of the decoder layer's output with those projections quantized, and folded into what produces their input, so the BF16 model is unchanged by it; `o_proj` and `linear_attn.out_proj` take no scale. Each projection except `q_proj` / `k_proj` then searches its clipping range per row and group over 10 steps, from its largest weight down to half of it. The calibration rows are the train split's (state of at most 6,000 characters, revision `28c39125`). `d3q_engine.py` is the Decision Index engine for the kit (`--engine d3q_engine:D3QEngine --option model=<this folder>`).</sub>

## License

Apache-2.0 ([LICENSE](LICENSE)), as d3. Built on [vllm-sr/d3](https://huggingface.co/vllm-sr/d3), which is built on [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) (Apache-2.0).

## Citation

```bibtex
@misc{d3_2026,
  title        = {{d3}: A Multimodal Foundation Decision Model},
  author       = {{vLLM Semantic Router Team}},
  year         = {2026},
  howpublished = {\url{https://huggingface.co/vllm-sr/d3}}
}
```
