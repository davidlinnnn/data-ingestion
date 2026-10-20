# W4: verified local decision-model candidates

Research date: 2026-10-20. Primary sources only; no weights downloaded or inference performed by this research task. Metadata and small source files are captured in `candidate-evidence/`. Hugging Face API metadata includes full revisions, individual LFS SHA-256 values and byte sizes. Those advertised hashes must still be checked against downloaded files before evaluation.

## Decision

Select **`yah01/vjev-vision`**, revision **`2fa8b58e40e5bc351a7d6dd39b953469a8f3ded2`**, with its published decision head and reference Transformers implementation on MPS. It is the only priority candidate whose first-party inference helper explicitly supports this Mac. The other priority model exists and has a suitable declared license, but its public loader rejects MPS and CPU. Do not download it or engineer a port during this bounded evaluation.

The advertised calibrated probabilities are a claim to evaluate, not evidence that a probability of 0.8 means 80% correctness on formulas or code. The VJev card itself reports spatial overconfidence and a training distribution dominated by COCO/VQAv2 rather than document transcription.

## Verification table

| Candidate | Exact repository revision | Parameters / released weights | Images / typed probabilities | License | Mac decision |
|---|---|---|---|---|---|
| VJev-Vision | `yah01/vjev-vision@2fa8b58e40e5bc351a7d6dd39b953469a8f3ded2` | 4,539,265,536 BF16 parameters; merged three-shard weights **9,078,619,904 bytes** plus 12,045-byte head | Reference `Vjev.ask` accepts images and noul/choice/score; shared linear scoring head, one forward pass | Apache-2.0 in first-party card; base Qwen3.5-4B independently declares Apache-2.0 | **Selected.** Reference helper explicitly chooses CUDA / MPS / CPU. Published approximately 9 GB weight memory leaves room for runtime and >=8 GB available-memory guard on 48 GB Mac; actual operation and peak memory still need measurement. |
| Jev-Omni | `akhilaaa3/Jev-Omni@fee89b076e2263bfa8bce8d34142caa4ca733a48` | 11,959,730,224 BF16 parameters; **23,919,549,408-byte** full multimodal checkpoint plus decision head | Image/audio/video inputs; one question per forward pass, classifier logits rather than generated confidence | Apache-2.0 in first-party card; `google/gemma-4-12B-it` metadata independently declares Apache-2.0 | **Not run locally.** Public `load_jev_omni` explicitly raises unless CUDA is available; `predict` hardcodes CUDA BF16 autocast. A custom MPS adaptation is engineering, not demonstrated official support. |
| CLEF | `Cloudflare/clef@a30162b99d68a481d8bd75d38df069a0cf83df40` | 27,356,728,560 BF16 parameters; backbone plus joint head **54,969,731,792 bytes** | Multimodal Qwen3.8-27B; joint schema head scores typed options | Apache-2.0, LICENSE present | Not selected. Released full weights exceed both 40 GB total download limit and Mac memory with required 8 GB headroom. Official tested setup is H200/CUDA. |
| JEV-27B-VL | `autotrust/JEV-27B-VL@9e53b8a809d2ab98e3e6a55b2b2dbf94b4c1e84a` | 27,781,427,952 BF16 parameters; full weights + adapter **56,014,508,552 bytes** | Multimodal typed System 1 decisions; source card provides vLLM serving instructions | Apache-2.0, LICENSE present | Not selected. Full release exceeds limits; card requests a GPU with >=80 GB. |
| pplx-decider-v1-27b | `perplexity-ai/pplx-decider-v1-27b@d8c3bd18e31dc1804433d38528b3e770019bf00c` | 26,085,330,160 BF16 parameters; weights + readout **52,173,413,928 bytes** | `Decider.predict(..., images=[...])`, typed choices and calibrated probabilities | Apache-2.0, LICENSE present | Not selected. Official instructions require CUDA and approximately49 GiB of weights plus working memory. Exceeds download budget and Mac memory guard. |

The two priority models' full weights together would be approximately33 GB, within the download limit, but that does not make the second model executable on MPS. No third-party quantization is silently substituted, because its head preservation and calibration would be a separate candidate.

## VJev pinned weight identities

| File | Bytes | Publisher's SHA-256 |
|---|---:|---|
| `model-00001-of-00003.safetensors` | 3,991,298,872 | `24ba02d1fb2ce94b82dbb5392bff0ad0a6da68af29de91b20069094523686daf` |
| `model-00002-of-00003.safetensors` | 3,979,833,152 | `d1a174029ad8264cbd2aa8cb701321cd432ddf020a2da910d526365c49b8f071` |
| `model-00003-of-00003.safetensors` | 1,107,487,880 | `611359f82c25f0c13abfdcf115812ca23ffd6765d7bbd330ff2d6631756b4f71` |
| `head.pt` | 12,045 | `f1c21ff4eee514b109ab6299c8c76e5e8cf7925ba14141fe18d3d930a92a2629` |

The optional adapter is **not needed** when using the merged release. Do not download the base model separately. The card states the merged backbone uses the dequantized training base plus its LoRA, so replacing it with pristine Qwen weights is not equivalent.

VJev's reference preprocessing resizes images to a 512-pixel longer side. This is part of the released model's operating point and may lose fine formula/code glyphs; record it in the evaluation, do not silently change it based on test errors. Multiple images are allowed but were not the training shape. The model card reports an option-order effect; keep one fixed option order across dev and test. No MLX decision-head implementation is established by these sources; use the supported Transformers/MPS path rather than a generative MLX conversion that drops the scoring head.

## Primary sources

- [Pinned VJev model card](https://huggingface.co/yah01/vjev-vision/blob/2fa8b58e40e5bc351a7d6dd39b953469a8f3ded2/README.md), [reference implementation](https://huggingface.co/yah01/vjev-vision/blob/2fa8b58e40e5bc351a7d6dd39b953469a8f3ded2/vjev_infer.py), [revision metadata including LFS hashes](https://huggingface.co/api/models/yah01/vjev-vision/revision/2fa8b58e40e5bc351a7d6dd39b953469a8f3ded2?blobs=true).
- [Qwen3.5-4B base metadata](https://huggingface.co/api/models/Qwen/Qwen3.5-4B/revision/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a?blobs=true).
- [Pinned Jev-Omni card](https://huggingface.co/akhilaaa3/Jev-Omni/blob/fee89b076e2263bfa8bce8d34142caa4ca733a48/README.md), [CUDA-only reference loader](https://huggingface.co/akhilaaa3/Jev-Omni/blob/fee89b076e2263bfa8bce8d34142caa4ca733a48/jev_omni.py), [dependencies](https://huggingface.co/akhilaaa3/Jev-Omni/blob/fee89b076e2263bfa8bce8d34142caa4ca733a48/requirements.txt).
- [Gemma4-12B-it base metadata](https://huggingface.co/api/models/google/gemma-4-12B-it/revision/707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7?blobs=true).
- [Pinned CLEF card](https://huggingface.co/Cloudflare/clef/blob/a30162b99d68a481d8bd75d38df069a0cf83df40/README.md).
- [Pinned JEV-27B-VL card](https://huggingface.co/autotrust/JEV-27B-VL/blob/9e53b8a809d2ab98e3e6a55b2b2dbf94b4c1e84a/README.md).
- [Pinned Perplexity Decider card](https://huggingface.co/perplexity-ai/pplx-decider-v1-27b/blob/d8c3bd18e31dc1804433d38528b3e770019bf00c/README.md).

License statements above reflect the named model publishers and independent base metadata. VJev and Jev-Omni express Apache-2.0 in their model cards but do not ship a standalone LICENSE file at these revisions; this is recorded rather than fabricating a file. No external benchmark score is substituted for W4's own held-out test result.
