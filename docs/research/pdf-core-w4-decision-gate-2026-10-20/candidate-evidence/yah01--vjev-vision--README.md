---
base_model: Qwen/Qwen3.5-4B
license: apache-2.0
library_name: transformers
pipeline_tag: image-text-to-text
tags:
- qwen3.5
- classification
- calibration
- vision
- jev
---

# vjev-vision

A **listwise decision model** with vision: give it a state (text, images, or both) and typed
questions — `noul` (is this statement true?), `choice` (pick one), `score` (an ordered scale) —
and it returns calibrated probabilities for every option, in a single forward pass, with no
text generation. It re-creates the Jev API's shape on an open base (Qwen3.5-4B), with images added.

This is the released checkpoint of the full vision run (step 600 of 1,200; chosen over the final
step for its yes/no behaviour, see below). The earlier 300-step pilot stays at
[yah01/vjev-vision-pilot](https://huggingface.co/yah01/vjev-vision-pilot).

## Use it

The web console and the HTTP API live in [BubbleCal/vjev-serve](https://github.com/BubbleCal/vjev-serve):

```bash
pip install git+https://github.com/BubbleCal/vjev-serve
vjev-serve --model yah01/vjev-vision        # then open http://localhost:8800
```

Or, with nothing but transformers, the single file in this repo:

```python
from huggingface_hub import hf_hub_download
import importlib.util
spec = importlib.util.spec_from_file_location("vjev_infer", hf_hub_download("yah01/vjev-vision", "vjev_infer.py"))
vjev_infer = importlib.util.module_from_spec(spec); spec.loader.exec_module(vjev_infer)

m = vjev_infer.Vjev("yah01/vjev-vision")          # cuda / mps / cpu
m.ask(state=["photo.jpg", "Frame from the warehouse camera, 12:40."],
      questions={"person": {"type": "noul",   "instructions": "There is a person in this image."},
                 "where":  {"type": "choice", "instructions": "Where is the forklift?",
                            "criteria": {"left": "left half", "right": "right half", "none": "no forklift"}},
                 "busy":   {"type": "score",  "instructions": "How cluttered is the scene?",
                            "criteria": ["empty", "sparse", "busy", "crowded"]}})
```

Options inside one question compete (one softmax); questions never see each other. To rate
several independent things, ask one `noul` per thing (vjev-serve's `multilabel` type does this).
About 9 GB of memory in bf16/fp16.

## What is in this repo

| file | what |
|---|---|
| `model-*.safetensors`, `config.json`, tokenizer and processor files | the full model, bf16: Qwen3.5-4B with the checkpoint's LoRA merged in |
| `head.pt` | the listwise scoring head: one shared linear layer read at each option's slot |
| `vjev.json` | how inputs are rendered (`readout: trailing`, `pause: 0`, length budgets) |
| `vjev_infer.py` | stand-alone inference |
| `adapter/` | the same weights as a LoRA adapter (PEFT, r=32, α=64) over `Qwen/Qwen3.5-4B`, fitted on the nf4-quantized base |

The merged weights are the nf4-dequantized base the adapter was trained against, plus the
adapter, in bf16 — no bitsandbytes needed. Against the adapter on its nf4 base (CUDA, 118
questions over 10 images): max |Δp| 0.0097, mean 0.0036, no answer changed.

## How it was trained

1. **Text** (3,868 steps): QLoRA on ~145k typed questions with soft labels from the Jev API plus
   human-labelled corpora; KL to the teacher distribution for choice/score, soft BCE for noul.
   All options of a question share one sequence and are read at a trailing `Answer: (A) (B) …`
   slot, so options can see each other.
2. **Vision** (this checkpoint, step 600 of a 1,200-step run warm-started from the text stage):
   a second LoRA on the vision tower (0.1× the text learning rate), on ~84k geometry questions
   from COCO-2017 annotations (which object is highest / smallest / left of…, counts, presence
   with adversarial absent objects; soft labels by Monte-Carlo perturbation of the boxes) and
   ~15k VQAv2 questions with their 10-annotator answer distributions, mixed with 25% text.

## Results (held out: images and texts never seen in training)

| | text stage (zero-shot) | pilot, 300 steps | **this, step 600** | final step 1200 |
|---|---:|---:|---:|---:|
| COCO geometry, choice accuracy | 0.506 | 0.665 | **0.735** | 0.703 |
| COCO geometry, choice ECE ↓ | 0.171 | 0.094 | 0.183 | 0.148 |
| VQAv2, choice accuracy | 0.579 | 0.654 | 0.706 | 0.721 |
| VQAv2, choice ECE ↓ | 0.126 | 0.033 | 0.052 | 0.070 |
| POPE adversarial, absent objects called present ↓ | 5.5% | 13.8% | **6.1%** | 12.9% |
| POPE, AUC | 0.977 | 0.969 | 0.966 | 0.962 |
| text, 20k held-out rows: accuracy vs human labels | 0.796 | — | 0.799 | 0.797 |
| text, 20k held-out rows: ECE ↓ | 0.068 | — | 0.063 | 0.065 |

Step 600 was picked over the final step: the final step called absent objects present twice
as often, for a small VQA gain. On text the vision stage cost nothing; the teacher itself scores
0.797 accuracy and 0.102 ECE on the same rows.

Options interact as in the teacher: adding a competing option protects the leader and takes
its mass from the runners-up (a paired effect of +0.0066 over the order-permutation noise
floor, CI excluding 0) — something a one-option-per-pass scorer cannot do.

## Limits

- Spatial answers are over-confident (ECE 0.18 on COCO geometry): the ranking is better than
  the probabilities.
- Trained on single images; several images in one request (`Picture 1:`, `Picture 2:`) rely on
  the base model's ability.
- Options are read in the order given; reordering them moves probabilities by a TVD of ~0.037
  on average.
- Images are resized to a 512 px longer side, the training resolution.

## License

Apache-2.0. The base model, Qwen3.5-4B, is Apache-2.0.
