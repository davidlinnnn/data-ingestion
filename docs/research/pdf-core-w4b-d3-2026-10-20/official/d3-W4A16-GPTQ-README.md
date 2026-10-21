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
- gptq
- w4a16
---

![d3: Decision 3.0](https://huggingface.co/vllm-sr/d3/resolve/main/assets/banner.png)

# d3-W4A16-GPTQ

**d3-W4A16-GPTQ** is [d3](https://huggingface.co/vllm-sr/d3), the 27B multimodal foundation decision model of Decision 3.0, with its decoder's projections in int4. Give it an input (text or JSON, optionally with images and videos) and the questions you need answered: pick one of several options, say yes or no, or rate on a scale. It answers them all in one call and returns a probability for every answer, as d3 does, in 16.1 GB of weights instead of 52.2 GB.

| | |
| --- | --- |
| **Parameters** | 26.09B, including the 0.46B vision encoder |
| **Base model** | [vllm-sr/d3](https://huggingface.co/vllm-sr/d3) at revision `093cffba` (the same weights as v3.1.0 and the current main) |
| **Quantization** | INT4 weight-only W4A16 (compressed-tensors `pack-quantized`): symmetric int4 weights in groups of 128 with BF16 scales, rounded by GPTQ (`actorder=weight`, dampening 0.01, block 128); activations stay in BF16. 400 projections; the Gated DeltaNet `in_proj_a` / `in_proj_b`, the vision tower, the embeddings and the readout stay as published |
| **Calibration data** | 512 text prompts (338,463 tokens) from the validation split of [tasksource-jev-typed-decisions](https://huggingface.co/datasets/tasksource/tasksource-jev-typed-decisions), rendered with d3's prompt template |
| **Weights on disk** | 16.1 GB (d3: 52.2 GB) |
| **Needs** | No special matrix units: a GPU with about 17 GB free. Tested on NVIDIA GeForce RTX 5090 and RTX PRO 6000 with `d3q/`, and on AMD Instinct MI300X with the vLLM Semantic Router model runtime |
| **Inputs** | Text or JSON, plus images and videos (several per request) |
| **Decision types** | Choice · Yes / No · Score |
| **License** | Apache-2.0 |

## Highlights

- **Scores 65.15 on the Jev Decision Index 0.3 public suite** against d3's 65.45, giving d3's top answer on 97.93% of its 312,320 questions; every area within 0.5 points of d3.
- **Keeps 97.98% of d3's answers** on the 14,031 test requests of tasksource-jev-typed-decisions, with accuracy 83.10% against d3's 83.25%.
- **16.4 GB of GPU memory for the weights instead of 52.2 GB** with the vLLM Semantic Router model runtime, on one AMD Instinct MI300X and on one NVIDIA RTX PRO 6000 alike.
- **1.28× to 1.47× d3's latency on the same GPU:** 61.5 ms against 47.9 ms per request on one AMD Instinct MI300X and 91.2 ms against 61.9 ms on one RTX PRO 6000 (median, graphs replaying, model runtime). The int4 layers unpack their weights to BF16 for every product, so they save memory rather than time.
- **Reads images and videos** as d3 does: the vision tower is unchanged. On the vision board's public suite it scores 73.55 against d3's 74.15 on the same machine and gives d3's top answer on 95.69% of its 12,210 questions.
- **Perception Test:** 76.94% on all 19,140 validation questions against d3's 77.73% on the same machine, giving d3's top answer on 95.13% of them.

## Quickstart

```bash
pip install "transformers==5.17.0" "compressed-tensors>=0.19" torch torchvision triton pillow opencv-python-headless safetensors accelerate
pip install flash-linear-attention causal-conv1d  # optional: fast GPU kernels for the linear-attention layers
```

```python
import json
import sys

from huggingface_hub import hf_hub_download, snapshot_download

path = snapshot_download("vllm-sr/d3-W4A16-GPTQ")
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
receipt = hf_hub_download("vllm-sr/d3", "assets/example-receipt.png")
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
clip = hf_hub_download("vllm-sr/d3", "assets/example-video.mp4")
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

`load_d3` is d3's own runtime (`d3_runtime.py`) with its backbone loader swapped for `d3q/`: transformers loads the checkpoint with its int4 weights still packed (`dequantize=False`), and each quantized projection becomes a layer that unpacks its weights to BF16 with one Triton kernel and multiplies in cuBLAS, bit for bit as compressed-tensors would dequantize them. Prompting, noncausal full attention, the FP32 readout, images and videos are d3's own; images and videos are read as d3 reads them. `AutoModel.from_pretrained(..., trust_remote_code=True)` alone dequantizes the whole checkpoint to BF16 and needs about 52 GB of GPU memory again.

## Run with vLLM Semantic Router

[vLLM Semantic Router](https://github.com/vllm-project/semantic-router) serves d3-W4A16-GPTQ in Engine mode, which runs one model behind the System One API on your own machine, as it serves d3. It verifies the package against its `MODEL_MANIFEST.json`, as it verifies d3, and keeps the weights in int4 on the GPU, with its own int4 layers rather than `d3q/`.

```bash
curl -fsSL https://vllm-sr.ai/install.sh | bash -s -- --channel dev --no-launch
export PATH="$HOME/.local/bin:$PATH"
vllm-sr serve -e vllm-sr/d3-W4A16-GPTQ
```

The platform is detected automatically; choose one with `--platform auto|cpu|cuda|rocm` (default `auto`), and a commit with `--revision`. Int4 needs no special matrix units, only about 17 GB of free GPU memory (see **Needs** above). Then ask questions about a request:

The first start downloads the package (about 16 GB) before loading it; if it stops with `did not become ready within 10m0s`, run the same command again: the download is kept and the second start only loads.

```bash
curl -s localhost:8899/v1/systemone -H 'content-type: application/json' -d '{
  "model": "vllm-sr/d3-W4A16-GPTQ",
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

**On one NVIDIA RTX PRO 6000, the model runtime answers a request in 91.2 ms against d3's 61.9 ms** (median, one request at a time, graphs replaying, both in one process), in 16.4 GB of GPU memory against 52.2 GB.

| GPU | | d3 (BF16) | d3-W4A16-GPTQ | Ratio |
| --- | --- | ---: | ---: | ---: |
| NVIDIA RTX PRO 6000 | Median latency, graphs (500 requests) | 61.9 ms | 91.2 ms | 1.47× |
| | p95 latency, graphs | 192.2 ms | 220.2 ms | 1.15× |
| | Median latency, no graphs (1,000 requests) | 62.5 ms | 92.5 ms | 1.48× |
| | GPU memory after loading | 52.2 GB | 16.4 GB | 0.31× |
| | GPU memory, peak of the 20 longest requests | 52.8 GB | 17.1 GB | 0.32× |
| AMD Instinct MI300X | Median latency, graphs (500 requests) | 47.9 ms | 61.5 ms | 1.28× |
| | p95 latency, graphs | 131.0 ms | 140.4 ms | 1.07× |
| | Median latency, no graphs (1,000 requests) | 69.2 ms | 83.6 ms | 1.21× |
| | GPU memory after loading | 52.2 GB | 16.4 GB | 0.32× |
| | GPU memory, peak of the 20 longest requests | 52.9 GB | 17.4 GB | 0.33× |

- **Graphs:** replaying the forward as a graph ([#4999](https://github.com/vllm-project/semantic-router/pull/4999)) changes little on this GPU, for d3 and for this package alike: without graphs the same requests take 92.5 ms against d3's 62.5 ms. On the MI300X graphs help both: d3 from 69.2 to 47.9 ms and this package from 83.6 to 61.5 ms, so the gap to d3 is 1.28× with graphs and 1.21× without.
- **Kernels:** one int4 projection with its unpacking takes 1.1× to 1.4× the time of the BF16 GEMM at 64 to 1,024 rows on the MI300X: the int4 layers save memory, not time. Under the runtime's approximate profile (`max_speed`), NVIDIA GPUs multiply straight from the packed weights for inputs of up to 256 rows instead.

<sub>Latency and memory measured on 2026-10-16, one NVIDIA RTX PRO 6000 Blackwell Workstation Edition (driver 595.99.02): PyTorch 2.11.0+cu128, Triton 3.6.0, FLA 0.5.2, causal-conv1d 1.7.0; vLLM Semantic Router model runtime of [#5066](https://github.com/vllm-project/semantic-router/pull/5066) (`da21a679`) with the graph capture of #4999 (`02423e85`), exact profile. Requests: the 1,000 train rows of tasksource-jev-typed-decisions in the #5066 record, one question each. Both packages loaded in one process; every request answered by both in turn, alternating which goes first, the device synchronized around each: the first 500 rows answered a third time so that their shape's graph replays, or all 1,000 a second time without graphs. Memory: allocated after loading and at the peak of the 20 longest of those rows (up to 5,928 characters of state), each package in its own process. Kernels measured on 2026-10-14, one AMD Instinct MI300X: ROCm image with PyTorch 2.12, Triton 3.7.1 and FLA 0.5.2, one of each of d3's projection shapes with random weights, `triton.testing.do_bench`. MI300X rows: measured on one AMD Instinct MI300X with the same vLLM Semantic Router model runtime, requests, passes and memory measurement.</sub>

## Evaluation

### Text: Jev Decision Index 0.3, public suite

| | d3 (BF16) | d3-W4A16-GPTQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| Public index ↑ | 65.45 | **65.15 (−0.30)** | 97.93% |
| &nbsp;&nbsp;Knowledge & Reasoning | 55.26 | 54.80 (−0.46) | 95.02% |
| &nbsp;&nbsp;Language Understanding | 68.04 | 68.02 (−0.02) | 99.28% |
| &nbsp;&nbsp;Retrieval & Classification | 66.86 | 66.53 (−0.33) | 98.27% |
| &nbsp;&nbsp;Tools & Automation | 82.57 | 82.09 (−0.48) | 99.26% |
| &nbsp;&nbsp;Arts & Human Taste | 51.02 | 50.75 (−0.27) | 96.58% |
| Raw index ↑ | 74.01 | 73.78 (−0.23) | – |
| Requests answered | 140,178 | 140,178 | – |

The five areas are the index's areas (chance-corrected skill; the public index averages them with fixed weights), with differences from d3 in parentheses. Agreement compares the top answer of every question with d3's official run (choice and score: the highest-probability option; yes / no: p ≥ 0.5): 312,320 questions in all, and per area the questions of that area's benchmarks.

The complete public suite (every request of d3's official run), run with the official kit ([apolinario/decision-index](https://github.com/apolinario/decision-index) `f8552a1`) through `d3q/` and scored by it, against d3's official run in [vllm-sr/d3-decision-index](https://huggingface.co/datasets/vllm-sr/d3-decision-index); rescoring that run with the same kit reproduces 65.45 exactly. The board's full score (66.3 for d3) also needs private tests that only the maintainers run, so it is not measured here: compare with d3's public 65.45, not 66.3.

Also on the test split of [tasksource/tasksource-jev-typed-decisions](https://huggingface.co/datasets/tasksource/tasksource-jev-typed-decisions):

| | d3 (BF16) | d3-W4A16-GPTQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| Accuracy | 83.25% | 83.10% | 97.98% (284 of 14,031 answers changed) |

Every usable row of the split at revision `28c39125` (a state of at most 6,000 characters, no repeated options): 14,031 requests of one question each, answered by the vLLM Semantic Router model runtime on one AMD Instinct MI300X. Agreement compares the top answer of every question with d3 on the same requests (choice and score: the highest-probability option; yes / no: p ≥ 0.5). Two calibration states, an LSAT logic-game passage and a news article, are also the states of 2 of these 14,031 requests.

The evaluation results listed on this page (LocalLLaMA/typed-decisions) are a separate run: that benchmark's own test split scored with its `score_model.py`, accuracy 0.751 against d3's 0.7485 on the same setup (the vLLM Semantic Router model runtime on one AMD Instinct MI300X).

### Images: Jev Decision Index vision board 0.3.2

| | d3 (BF16) | d3-W4A16-GPTQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| Public vision index ↑ | 74.15 | **73.55 (−0.60)** | 95.69% |

<details>
<summary>By benchmark (chance-corrected skill, %)</summary>

| Benchmark | Questions | d3 (BF16) | d3-W4A16-GPTQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: | ---: |
| CV-Bench | 2,038 | 76.28 | 75.31 (−0.97) | 98.43% |
| BLINK | 961 | 60.05 | 58.60 (−1.45) | 97.50% |
| RealWorldQA | 589 | 73.36 | 70.59 (−2.77) | 96.26% |
| CharXiv | 532 | 79.45 | 80.70 (+1.25) | 96.80% |
| InfographicVQA | 244 | 97.81 | 99.45 (+1.64) | 98.77% |
| Mind2Web | 973 | 84.10 | 83.14 (−0.96) | 96.61% |
| Winoground | 800 | 85.75 | 84.75 (−1.00) | 98.50% |
| KIE (CORD+FUNSD) | 2,465 | 92.65 | 92.65 (+0.00) | 99.55% |
| Moderation (Hateful Memes) | 1,213 | 45.42 | 44.11 (−1.32) | 96.21% |
| R-Bench-M | 665 | 33.22 | 32.86 (−0.36) | 85.41% |
| MMMU-Pro vision | 1,730 | 45.84 | 45.64 (−0.20) | 86.76% |

</details>

All 12,210 rows of the kit's public vision suite (11 benchmarks), one image request per row, run with the official kit ([apolinario/decision-index](https://github.com/apolinario/decision-index) `f8552a1`) through `d3q/` and scored by it. d3 (BF16) answered the same rows the same way on the same machine and scores 74.15, in line with the official vision board's 74.1. Agreement compares the top answer of every question with that BF16 run.

### Videos: Perception Test

| | d3 (BF16) | d3-W4A16-GPTQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: |
| All 19,140 questions (validation) ↑ | 77.73 | **76.94 (−0.79)** | 95.13% |

<details>
<summary>By area (accuracy, %)</summary>

| Area | Questions | d3 (BF16) | d3-W4A16-GPTQ | Top-1 agreement with d3 |
| --- | ---: | ---: | ---: | ---: |
| Abstraction | 5,607 | 71.55 | 71.23 (−0.32) | 93.78% |
| Memory | 746 | 80.56 | 80.97 (+0.40) | 95.71% |
| Physics | 6,938 | 73.19 | 71.63 (−1.56) | 94.05% |
| Semantics | 5,849 | 88.66 | 88.19 (−0.48) | 97.62% |

</details>

Every multiple-choice question of Perception Test validation (19,140 questions over 5,260 videos, three options each, chance 33.3): one request per video with all its questions and the state "A video.", videos read with d3's defaults, through `d3q/` on one RTX PRO 6000. d3 (BF16) answered the same requests the same way on the same machine and scores 77.73; d3's card reports 77.4 from its internal evaluation, whose prompt may differ.

<sub>Record: [decision3-quantized.md](https://github.com/vllm-project/semantic-router/blob/main/src/model-runtime/docs/records/decision3-quantized.md) in #5066. Quantized with llm-compressor 0.14.0 and compressed-tensors 0.19.0 (torch 2.11.0+cu128, transformers 5.17.0) on one GeForce RTX 5090, calibrating the text model layer by layer with the full-attention layers under the noncausal key mask of `d3_runtime.PromptEncoder`, as at inference. The calibration prompts are text only and none of their states appears in the Decision Index public suite. `QUANT_INFO.json` records the recipe, versions and calibration data; `MODEL_MANIFEST.json` is d3's manifest with the hashes, sizes and model identity of this package's own files, written by `write_manifest` of [bench/d3-quant-eval/awq.py](https://github.com/subin9/semantic-router/blob/7908956ae1e1a673dd19fd7a305d2118b8a5228c/bench/d3-quant-eval/awq.py). `d3q_engine.py` is the Decision Index engine for the kit (`--engine d3q_engine:D3QEngine --option model=<this folder>`).</sub>

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
