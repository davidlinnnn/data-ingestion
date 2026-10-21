# Local Apple GPU / vLLM feasibility — primary-source check

Date: 2026-10-16. Scope: read-only documentation and source review; no installation, weight download, or model inference in this review. Existing frozen G2 evidence is unchanged.

## Conclusion

**The current Mac can support a meaningful local GPU experiment, but the best next dots.ocr route is MLX-VLM, not an assumed working dots.ocr deployment on vLLM-Metal.** The host inspection reported by the parent task is M5 Pro, 20 GPU cores, 18 CPU cores, 48 GiB unified memory, and macOS 26.4; host MPS matrix operations passed for FP32/FP16/BF16. That establishes available Apple GPU hardware and basic operations, not whole-model compatibility or latency.

The 3.04B dots.ocr BF16 weights are about 6.08 GB. With 48 GiB total memory, a bounded, one-page, concurrency-one experiment is reasonable. This is an engineering feasibility judgment, **not** a measured full-model memory requirement: image attention, KV cache, framework allocations, other applications, and current free memory matter. The parent reports around 15.3 GiB available now. The GPU shares system memory; 48 GiB must not be described as a dedicated 48 GiB NVIDIA card. [Published BF16 tensor inventory](https://huggingface.co/mlx-community/dots.ocr-bf16/blob/main/model.safetensors.index.json)

## What each runtime actually supports

| Route | Primary-source evidence | Consequence for this test |
|---|---|---|
| Regular vLLM with NVIDIA CUDA | The NVIDIA route requires Linux and a compatible NVIDIA GPU. Apple Silicon has a separately documented Metal plugin route. | This Mac cannot reproduce the company CUDA execution stack locally. |
| vLLM-Metal | The vLLM project describes an Apple Silicon hardware plugin using MLX, integrated with vLLM scheduling and the OpenAI-compatible API. The plugin's installation page requires macOS 15+, Apple Silicon, and Python 3.12. | The hardware/OS meets published prerequisites; installation and model serving still need actual verification. |
| dots.ocr on vLLM-Metal | The current multimodal support table lists experimental Qwen3-VL, Qwen3.5, PaddleOCR-VL, and Gemma 4; it does not list dots.ocr. | **Unverified**, not a supported route we can promise. Generic MLX-VLM support does not imply the plugin implements the corresponding multimodal runner. |
| dots.ocr on MLX-VLM | MLX-VLM has a dedicated `dots_ocr` configuration, language/vision implementation, processor, and model documentation; a BF16 MLX conversion of the original dots.ocr is published. | A concrete Apple GPU candidate exists. Test the actual model before claiming end-to-end support. |
| Docling MLX engine | Docling 2.132 has a native `MlxVlmEngine`, which calls `mlx_vlm.load`, `apply_chat_template`, and `stream_generate`. | There is an official integration seam; no custom OCR postprocessor is needed merely to try MLX. The exact dots wiring is still a smoke-test item. |

Sources: [vLLM GPU installation](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/), [vLLM-Metal architecture](https://docs.vllm.ai/projects/vllm-metal/en/latest/), [plugin installation](https://docs.vllm.ai/projects/vllm-metal/en/latest/installation/), [plugin model support table](https://github.com/vllm-project/vllm-metal/blob/main/docs/supported_models.md), [MLX-VLM dots model](https://github.com/Blaizzy/mlx-vlm/tree/main/mlx_vlm/models/dots_ocr), [Docling 2.132 MLX engine](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/inference_engines/vlm/mlx_engine.py).

## Checkpoint identity and official Docling path

The community BF16 conversion is `mlx-community/dots.ocr-bf16`, currently revision **`98b9cda3930eb69d2b887781685f3f393d6f141e`**. Its metadata reports **3,039,179,264 BF16 parameters**. Its card says it was converted from `rednote-hilab/dots.ocr` with MLX-VLM 0.3.12. The card/config/Hub metadata inspected do **not** specify the original upstream revision; therefore this conversion cannot automatically be equated with the earlier pinned `dots-studio/dots.ocr@c0111ce6bc07803dbc267932ffef0ae3a51dc951`. [Model card](https://huggingface.co/mlx-community/dots.ocr-bf16), [Hub metadata](https://huggingface.co/api/models/mlx-community/dots.ocr-bf16)

MLX-VLM's `dots_ocr.Model.sanitize` maps original Hugging Face parameter names into its language and vision modules. The common loader reads local safetensors, invokes model/vision sanitization, and supports BF16 conversion. This makes reuse or upstream conversion of the **already downloaded exact checkpoint** a reasonable first experiment. Source inspection alone does not prove that its processor, chat template, weight shapes, and output match; these must be checked before scoring. Prefer this identity-preserving attempt over downloading another unpinned conversion or introducing 4-bit quantization in the same comparison. [Dots weight mapping](https://github.com/Blaizzy/mlx-vlm/blob/main/mlx_vlm/models/dots_ocr/dots_ocr.py), [MLX-VLM loader](https://github.com/Blaizzy/mlx-vlm/blob/main/mlx_vlm/utils.py)

The pinned Docling 2.132 `dots_ocr` preset has Transformers and vLLM overrides plus API options, but **no explicit MLX override**. It retains the native layout prompt, DOTS_JSON response format, scale 2, and 24,000 output tokens. The general MLX engine exists and can load a specified repository/local artifact. Thus “Docling supports MLX” is true; “Docling's dots preset already certifies this exact MLX checkpoint” is not established. [Pinned preset](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/stage_model_specs.py#L1854), [pinned MLX implementation](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/inference_engines/vlm/mlx_engine.py)

The newer model catalog documents official MLX routes for Granite-Docling/SmolDocling and distinguishes engine compatibility by model. It also explicitly disables MPS for TableFormer due to performance concerns. Accordingly, enabling an Apple GPU does not move every StandardPdfPipeline component to GPU. [Docling model catalog](https://docling-project.github.io/docling/usage/model_catalog/)

## Recommended next experiment

1. In an isolated runtime, pin MLX/MLX-VLM and try the existing exact dots checkpoint through the upstream loader or converter, preserving BF16 and the frozen image/prompt. First check parameter coverage, processor dimensions, and actual GPU execution.
2. Run one bounded page at concurrency one. Measure completed output, wall time, peak unified-memory usage, and parser behavior; preserve the known inline-code parser defect separately from GPU performance.
3. Only if complete inference is feasible, run the frozen validation pages without per-case tuning. Report the runtime change explicitly; do not merge its latency with CUDA benchmarks.
4. If testing the vLLM serving interface itself is valuable, use a **documented vLLM-Metal multimodal family** such as Qwen3-VL in a separate experiment. Do not label this dots.ocr validation or company deployment validation.

An OpenAI-compatible endpoint lets Docling use a common request interface. It does not make MLX, vLLM-Metal, Linux/CUDA vLLM, or different checkpoints numerically/performance equivalent. Company GPU throughput, high-frequency admission, and production capacity remain separate measurements.

Not checked here: model loading/inference, vLLM-Metal installation, conversion tensor equality, or high-frequency latency. The recommendation is a feasible next bounded test, not a completed GPU validation or a claim that the known canonical parser gap is fixed.
