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
- fp8
---

d3: Decision 3.0 (`assets/banner.png`)

# d3-FP8

**d3-FP8** is [d3](https://huggingface.co/vllm-sr/d3), the 27B multimodal foundation decision model of Decision 3.0, with its decoder's projections in FP8. Give it an input (text or JSON, optionally with images and videos) and the questions you need answered: pick one of several options, say yes or no, or rate on a scale. It answers them all in one call and returns a probability for every answer, as d3 does, in 31.9 GB of weights instead of 52.2 GB.

| | |
| --- | --- |
| **Parameters** | 26.09B, including the 0.46B vision encoder |
| **Base model** | [vllm-sr/d3](https://huggingface.co/vllm-sr/d3) at revision `cbff3a3c` (v3.1.0, the same weights as the current main) |
| **Quantization** | FP8 W8A8 (compressed-tensors `float-quantized`, FP8_DYNAMIC): E4M3 weights with one BF16 scale per output channel, activations quantized to FP8 per token at run time. 304 projections; the Gated DeltaNet input projections, the vision tower, the embeddings and the readout stay as published |
| **Calibration data** | None: weight scales come from the weights, activation scales from each request |
| **Weights on disk** | 31.9 GB (d3: 52.2 GB) |
| **Needs** | FP8 matrix units: AMD Instinct MI300 / MI350 series, or NVIDIA compute capability 8.9 or later |
| **Inputs** | Text or JSON, plus images and videos (several per request) |
| **Decision types** | Choice · Yes / No · Score |
| **License** | Apache-2.0 |

## Highlights

- **Scores 65.40 on the Jev Decision Index 0.3 public suite** against d3's 65.45, giving d3's top answer on 99.15% of its 312,320 questions; every area within 0.3 points of d3.
- **31.9 GB of GPU memory for the weights instead of 52.2 GB** with the vLLM Semantic Router model runtime, on one AMD Instinct MI300X and on one NVIDIA RTX PRO 6000 alike.
- **0.72× d3's latency on one RTX PRO 6000 and 0.79× on one MI300X:** 45.0 ms against 62.1 ms and 36.8 ms against 46.4 ms per request (median) in the model runtime, both in one process, with the forward replayed as a graph ([#4999](https://github.com/vllm-project/semantic-router/pull/4999)). Without graphs the MI300X takes longer than for d3: each layer's activation quantization costs more host time than FP8 saves.
- **Reads images and videos** as d3 does: the vision tower is unchanged. On the vision board's public suite it scores 74.03 against d3's 74.15 and gives d3's top answer on 98.19% of its 12,210 questions.
- **Perception Test:** 77.57% on all 19,140 validation questions, the same as d3 on the same machine, giving d3's top answer on 98.10% of them.

## Quickstart

```bash
pip install "transformers==5.17.0" "compressed-tensors>=0.17" torch torchvision triton pillow opencv-python-headless safetensors accelerate
pip install flash-linear-attention  # optional: fast GPU kernels for the linear-attention layers
```

```python
import json
import sys

from huggingface_hub import hf_hub_download, snapshot_download

path = snapshot_download("vllm-sr/d3-FP8")
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
receipt = hf_hub_download("vllm-sr/d3-FP8", "assets/example-receipt.png")
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
clip = hf_hub_download("vllm-sr/d3-FP8", "assets/example-video.mp4")
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

`load_d3` is d3's own runtime (`d3_runtime.py`) with its backbone loader swapped for `d3q/`: transformers loads the checkpoint with its weights in FP8, and each quantized projection becomes a layer that quantizes its input to FP8 per row with one Triton kernel and multiplies in `torch._scaled_mm`. Prompting, noncausal full attention, the FP32 readout, images and videos are d3's own; images and videos are read as d3 reads them. `AutoModel.from_pretrained(..., trust_remote_code=True)` alone does not run FP8 weights.

## Run with vLLM Semantic Router

[vLLM Semantic Router](https://github.com/vllm-project/semantic-router) serves d3-FP8 in Engine mode, which runs one model behind the System One API on your own machine, as it serves d3. It verifies the package against its `MODEL_MANIFEST.json`, as it verifies d3, and keeps the weights in FP8 on the GPU.

```bash
curl -fsSL https://vllm-sr.ai/install.sh | bash -s -- --channel dev --no-launch
export PATH="$HOME/.local/bin:$PATH"
vllm-sr serve -e vllm-sr/d3-FP8
```

The platform is detected automatically; choose one with `--platform auto|cpu|cuda|rocm` (default `auto`), and a commit with `--revision`. FP8 needs a GPU with FP8 matrix units (see **Needs** above). Then ask questions about a request:

```bash
curl -s localhost:8899/v1/systemone -H 'content-type: application/json' -d '{
  "model": "vllm-sr/d3-FP8",
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

**On one NVIDIA RTX PRO 6000, the model runtime answers a request in 45.0 ms against d3's 62.1 ms, and on one AMD Instinct MI300X in 36.8 ms against 46.4 ms** (median, one request at a time, graphs replaying, both in one process), in 31.9 GB of GPU memory against 52.2 GB.

| GPU | | d3 (BF16) | d3-FP8 | Ratio |
| --- | --- | ---: | ---: | ---: |
| NVIDIA RTX PRO 6000 | Median latency, graphs (500 requests) | 62.1 ms | 45.0 ms | 0.72× |
| | p95 latency, graphs | 192.6 ms | 134.9 ms | 0.70× |
| | Median latency, no graphs (1,000 requests) | 62.5 ms | 46.0 ms | 0.74× |
| | GPU memory after loading | 52.2 GB | 31.9 GB | 0.61× |
| | GPU memory, peak of the 20 longest requests | 52.8 GB | 32.5 GB | 0.62× |
| AMD Instinct MI300X | Median latency, graphs (500 requests) | 46.4 ms | 36.8 ms | 0.79× |
| | p95 latency, graphs | 130.1 ms | 96.5 ms | 0.74× |
| | Median latency, no graphs (1,000 requests) | 67.1 ms | 80.9 ms | 1.21× |
| | GPU memory after loading | 52.2 GB | 31.9 GB | 0.61× |
| | GPU memory, peak of the 20 longest requests | 52.9 GB | 32.8 GB | 0.62× |

- **Graphs:** on the MI300X the gain needs the forward replayed as a graph ([#4999](https://github.com/vllm-project/semantic-router/pull/4999)). Without graphs the same requests take 80.9 ms against d3's 67.1 ms: the activation quantization and the scaled GEMM of each of the 304 FP8 layers cost more host time than FP8 saves. On the RTX PRO 6000 graphs change little, for d3 and for this package alike, and FP8 is faster either way.
- **Kernels:** one FP8 projection with its activation quantization takes 0.61× to 0.74× the time of the BF16 GEMM at 64 to 1,024 rows on the MI300X. On an NVIDIA Ada GPU the runtime takes the FP8 product unscaled and applies the scales after, since the per-row scaled product is slower than BF16 there from 256 rows on.
- **Throughput under load:** not measured yet.

<sub>Latency and memory measured on 2026-10-16 on one NVIDIA RTX PRO 6000 Blackwell Workstation Edition (driver 595.99.02): PyTorch 2.11.0+cu128, Triton 3.6.0, FLA 0.5.2, causal-conv1d 1.7.0; and on one AMD Instinct MI300X: ROCm image with PyTorch 2.12, Triton 3.7.1 and FLA 0.5.2. Both with the vLLM Semantic Router model runtime of [#5066](https://github.com/vllm-project/semantic-router/pull/5066) as of 2026-10-14 with the graph capture of #4999, exact profile, and the same weights as this revision. Requests: the 1,000 train rows of tasksource-jev-typed-decisions in the #5066 record, one question each. Both packages loaded in one process; every request answered by both in turn, alternating which goes first, the device synchronized around each: the first 500 rows answered a third time so that their shape's graph replays, or all 1,000 a second time without graphs. Memory: the runtime's weight bytes after loading and the peak allocated over the 20 longest of those rows (up to 5,928 characters of state), each package in its own process. Kernels measured on 2026-10-15 on the same MI300X, one of each of d3's projection shapes with random weights, `triton.testing.do_bench`.</sub>

## Evaluation

### Text: Jev Decision Index 0.3, public suite

| | d3 (BF16) | d3-FP8 | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| Public index ↑ | 65.45 | **65.40 (−0.05)** | 99.15% |
| &nbsp;&nbsp;Knowledge & Reasoning | 55.26 | 55.41 (+0.15) | 97.98% |
| &nbsp;&nbsp;Language Understanding | 68.04 | 67.88 (−0.16) | 99.67% |
| &nbsp;&nbsp;Retrieval & Classification | 66.86 | 66.65 (−0.21) | 99.36% |
| &nbsp;&nbsp;Tools & Automation | 82.57 | 82.67 (+0.10) | 99.69% |
| &nbsp;&nbsp;Arts & Human Taste | 51.02 | 50.76 (−0.26) | 98.34% |
| Raw index ↑ | 74.01 | 74.01 (+0.00) | – |
| Requests answered | 140,178 | 140,178 | – |

The five areas are the index's areas (chance-corrected skill; the public index averages them with fixed weights), with differences from d3 in parentheses. Agreement compares the top answer of every question with d3's official run (choice and score: the highest-probability option; yes / no: p ≥ 0.5): 312,320 questions in all, and per area the questions of that area's benchmarks.

The complete public suite (every request of d3's official run), run with the official kit ([apolinario/decision-index](https://github.com/apolinario/decision-index) `f8552a1`) through d3's own `d3_engine.py` with the backbone loaded by `d3q/`, and scored by it, against d3's official run in [vllm-sr/d3-decision-index](https://huggingface.co/datasets/vllm-sr/d3-decision-index). The board's full score (66.3 for d3) also needs private tests that only the maintainers run, so it is not measured here: compare with d3's public 65.45, not 66.3.

`d3q/kernels.py` before 2026-10-16 indexed the rows of the activation quantization in 32 bits, so a forward past 2**31 activation elements, such as a long multi-question request, returned NaN answers and changed the answers of later requests. It now indexes them in 64 bits, and the numbers above are from that version.

Also on the test split of [tasksource/tasksource-jev-typed-decisions](https://huggingface.co/datasets/tasksource/tasksource-jev-typed-decisions):

| | d3 (BF16) | d3-FP8 | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| Accuracy | 83.25% | 83.24% | 99.08% (129 of 14,031 answers changed) |

Every usable row of the split at revision `28c39125` (a state of at most 6,000 characters, no repeated options): 14,031 requests of one question each, answered by the vLLM Semantic Router model runtime on one AMD Instinct MI300X. Agreement compares the top answer of every question with d3 on the same requests (choice and score: the highest-probability option; yes / no: p ≥ 0.5).

### Images: Jev Decision Index vision board 0.3.2

| | d3 (BF16) | d3-FP8 | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| Public vision index ↑ | 74.15 | **74.03 (−0.12)** | 98.19% |

<details>
<summary>By benchmark (chance-corrected skill, %)</summary>

| Benchmark | Questions | d3 (BF16) | d3-FP8 | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: | ---: |
| CV-Bench | 2,038 | 76.28 | 76.36 (+0.08) | 99.46% |
| BLINK | 961 | 60.05 | 60.21 (+0.16) | 98.34% |
| RealWorldQA | 589 | 73.36 | 72.81 (−0.55) | 98.81% |
| CharXiv | 532 | 79.45 | 79.20 (−0.25) | 99.25% |
| InfographicVQA | 244 | 97.81 | 97.81 (+0.00) | 99.18% |
| Mind2Web | 973 | 84.10 | 83.42 (−0.68) | 98.66% |
| Winoground | 800 | 85.75 | 86.00 (+0.25) | 99.50% |
| KIE (CORD+FUNSD) | 2,465 | 92.65 | 92.72 (+0.07) | 99.92% |
| Moderation (Hateful Memes) | 1,213 | 45.42 | 45.75 (+0.33) | 98.27% |
| R-Bench-M | 665 | 33.22 | 31.96 (−1.26) | 94.14% |
| MMMU-Pro vision | 1,730 | 45.84 | 45.97 (+0.13) | 94.10% |

</details>

All 12,210 rows of the kit's public vision suite (11 benchmarks, matching the kit's pinned hashes), one image request per row, run with the official kit ([apolinario/decision-index](https://github.com/apolinario/decision-index) `f8552a1`) through `d3q_engine.py` on one AMD Instinct MI300X and scored by it. d3 (BF16) is the run reported in [d3-W4A16-GPTQ](https://huggingface.co/vllm-sr/d3-W4A16-GPTQ), made on another machine, which scores 74.15 against the official vision board's 74.1. d3 itself scores 73.93 on this MI300X, so differences of a few tenths are within what changes between machines. Agreement compares the top answer of every question with that same-machine d3 run (choice: the highest-probability option; yes / no: p ≥ 0.5). d3's example image question (`assets/example-receipt.png`) answers yes with 0.9996 (d3: 0.9997).

### Videos: Perception Test

| | d3 (BF16) | d3-FP8 | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| All 19,140 questions (validation) ↑ | 77.57 | **77.57 (±0.00)** | 98.10% |

<details>
<summary>By area (accuracy, %)</summary>

| Area | Questions | d3 (BF16) | d3-FP8 | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: | ---: |
| Abstraction | 5,607 | 71.14 | 71.05 (−0.09) | 97.29% |
| Memory | 746 | 80.70 | 80.97 (+0.27) | 97.99% |
| Physics | 6,938 | 73.05 | 73.08 (+0.03) | 97.85% |
| Semantics | 5,849 | 88.68 | 88.70 (+0.02) | 99.20% |

</details>

Every multiple-choice question of Perception Test validation (19,140 questions over 5,260 videos, three options each, chance 33.3): one request per video with all its questions and the state "A video.", videos read with d3's defaults, through `d3q/` on one AMD Instinct MI300X on 2026-10-14. d3 (BF16) answered the same requests the same way on the same machine and scores 77.57; d3's card reports 77.4 from its internal evaluation, whose prompt may differ. This run used `d3q/kernels.py` from before the 64-bit row index; none of its answers is NaN. d3's example video question (`assets/example-video.mp4`) answers yes with 0.924 (d3: 0.918).

<sub>Evaluated on 2026-10-15 on one AMD Instinct MI300X: ROCm 7.2 image with PyTorch 2.12, Triton 3.7.1, transformers 5.17.0 and FLA 0.5.2, with `causal_conv1d` on its torch reference as in d3's official run. Record: [decision3-quantized.md](https://github.com/vllm-project/semantic-router/blob/main/src/model-runtime/docs/records/decision3-quantized.md) in #5066. Built by `fp8_package.py` in [bench/d3-quant-eval](https://github.com/subin9/semantic-router/tree/research/d3-quant-eval/bench/d3-quant-eval): each output channel's scale is its largest absolute weight divided by 448, rounded to BF16. Keeping the Gated DeltaNet input projections in BF16 cut the changed answers on 1,000 train rows from 12 to 3, in an earlier comparison run through transformers. `d3q_engine.py` is the Decision Index engine for the kit (`--engine d3q_engine:D3QEngine --option model=<this folder>`).</sub>

## License

Apache-2.0 (`LICENSE`), as d3. Built on [vllm-sr/d3](https://huggingface.co/vllm-sr/d3), which is built on [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) (Apache-2.0).

## Citation

```bibtex
@misc{d3_2026,
  title        = {{d3}: A Multimodal Foundation Decision Model},
  author       = {{vLLM Semantic Router Team}},
  year         = {2026},
  howpublished = {\url{https://huggingface.co/vllm-sr/d3}}
}
```
