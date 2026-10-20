# W4b pinned official candidate verification

2026-10-20; research-only retrieval, no model execution or weight downloads by this auditor. Metadata plus every repository Python file are retained under `official/`; precise weight LFS SHA-256 values are in `official/candidate-lock.json`.

| Repository | Exact revision | BF16 parameter count | Safetensors bytes | License |
|---|---|---:|---:|---|
| [vllm-sr/d3-nano](https://huggingface.co/vllm-sr/d3-nano/tree/462efc366229ea268cf4eed3738b3fc4415e4817) | `462efc366229ea268cf4eed3738b3fc4415e4817` | 2,213,241,664 | 4,428,644,200 | Apache-2.0 |
| [vllm-sr/d3-mini](https://huggingface.co/vllm-sr/d3-mini/tree/bd0090dd758d32ba59ef5c749910a8e87fc4391f) | `bd0090dd758d32ba59ef5c749910a8e87fc4391f` | 4,539,265,536 | 9,081,227,360 | Apache-2.0 |
| [vllm-sr/d3-flash](https://huggingface.co/vllm-sr/d3-flash/tree/13dc1cc8ef23caefa765907e1d764751e5629f7d) | `13dc1cc8ef23caefa765907e1d764751e5629f7d` | 8,392,695,024 | 16,789,656,976 | Apache-2.0 |

All three are multimodal Qwen3.5-based checkpoints. Nano's published text/vision indices are 38.9/54.7; mini's are 52.6/63.2; flash has 8.39B parameters, not 9B exact (9B is its product size name). These are general published benchmarks, not document-enrichment gate qualification. [Nano card](https://huggingface.co/vllm-sr/d3-nano), [mini card](https://huggingface.co/vllm-sr/d3-mini), [flash card](https://huggingface.co/vllm-sr/d3-flash).

The model-card reference runtime uses Transformers **5.17.0**, `AutoModel.from_pretrained(..., trust_remote_code=True)` followed by `system_one(state=..., questions=..., images=[...])`. Choice criteria are a key/description mapping; noul returns the yes probability. Image input accepts local paths/PIL/base64/URLs. The exact processor ceiling is **1,638,400 pixels**, with a 65,536-pixel minimum and 32×32 patch accounting. User-facing 1.6 MP is rounded; preprocessing can conservatively cap at 1,600,000 pixels and record the scale. [Pinned runtime](https://huggingface.co/vllm-sr/d3-nano/blob/462efc366229ea268cf4eed3738b3fc4415e4817/d3_runtime.py).

The [official recipe](https://recipes.vllm.ai/vllm-sr/d3-nano) confirms `/v1/systemone`, vLLM main support from 2026-10-14 via PR61565 plus nano loading fix PR61778, with nightly CUDA/ROCm setup. This server route is **not** used on this Mac. The local reference runtime accepts explicit MPS, but the card gives no tested Apple/MPS compatibility guarantee: a local dev probe must establish it. CPU is supported without optional GPU-only FLA/causal-conv1d kernels.

Memory and download decisions: nano+mini weight bytes total **13,509,871,560**. All three total **30,299,528,536**, already exceeding a literal 30,000,000,000-byte cap before configs/tokenizers. Therefore flash must not be downloaded after both smaller candidates under the stated decimal cap; freeing cached files does not undo transferred bytes. Additional shared tokenizer files still count.

Official GPU reference: nano warm single-image p50/p90 **90.2/90.7ms**, mini **112/113ms**, flash **166/167ms**, on AMD Instinct MI325X, 1.6MP, one question, sequential reference AutoModel. Inverse p50 gives only rough sequential capacity **11.1/8.9/6.0 judgments/s** excluding other pipeline work. Nano reference peak is 9.1GiB; flash 23.8GiB. These are published benchmark settings, **not** measurements on the company GPU or a guarantee for longer candidate text. Nano's published 318 requests/s is **batched text**, not image throughput. Eight-question image throughput numbers cannot be relabeled single-question image throughput. [Nano benchmark details](https://huggingface.co/vllm-sr/d3-nano#serving-performance), [mini](https://huggingface.co/vllm-sr/d3-mini#serving-performance), [flash](https://huggingface.co/vllm-sr/d3-flash#serving-performance).

Pinned-code caveat: the recipe's statement that `confidence` equals the selected-option probability is false for the audited reference revision. [`d3_runtime.py:316–322,341–343`](https://huggingface.co/vllm-sr/d3-nano/blob/462efc366229ea268cf4eed3738b3fc4415e4817/d3_runtime.py#L316) computes one minus normalized Shannon entropy. This evaluation uses explicit `probabilities["faithful"]` / `noul`, not confidence; detailed mismatch evidence is in `remote-code-audit.md`.

## Complete-family metadata verification (no weight downloads)

The official HF org listing and pinned cards confirm the remaining named repositories and Apache-2.0 license declarations. Exact metadata/cards are saved in `official/`; this section does **not** qualify their remote code for execution.

| Repository | Exact parameter count | Pinned revision |
|---|---:|---|
| [vllm-sr/d3](https://huggingface.co/vllm-sr/d3/tree/cf15549a78fc52598ddd1951f321c58372bbd64f) | 26085330160 | `cf15549a78fc52598ddd1951f321c58372bbd64f` |
| [vllm-sr/d3-turbo](https://huggingface.co/vllm-sr/d3-turbo/tree/17a01e225d5e37d649b95f329512c7805bf32ed0) | 26085330160 | `17a01e225d5e37d649b95f329512c7805bf32ed0` |
| [vllm-sr/d3-lite](https://huggingface.co/vllm-sr/d3-lite/tree/03560c26f5199c3c04129a2ccb38960c913635e0) | 852985920 | `03560c26f5199c3c04129a2ccb38960c913635e0` |
| [vllm-sr/d3-edge](https://huggingface.co/vllm-sr/d3-edge/tree/c454ee39b862248d70abd7f84195d2f54ffe6d43) | 594321600 | `c454ee39b862248d70abd7f84195d2f54ffe6d43` |
| [vllm-sr/d3-FP8](https://huggingface.co/vllm-sr/d3-FP8/tree/8acfecc803504cf201b77c483d1734b409a6a710) | 26085330160 | `8acfecc803504cf201b77c483d1734b409a6a710` |
| [vllm-sr/d3-W4A16-GPTQ](https://huggingface.co/vllm-sr/d3-W4A16-GPTQ/tree/45bd22cdaccf12943ab9a5ca452748ef37012675) | 26085330160 | `45bd22cdaccf12943ab9a5ca452748ef37012675` |
| [vllm-sr/d3-W4A16-AWQ](https://huggingface.co/vllm-sr/d3-W4A16-AWQ/tree/43885ebf0f9cb1e82eacdd38fefe09e09f970988) | 26085330160 | `43885ebf0f9cb1e82eacdd38fefe09e09f970988` |

The d3 and d3-turbo product names use the **27B size class**, while their exact BF16 parameter metadata gives **26,085,330,160**, rounded26.09B. Lite is **852,985,920** (0.85B) and edge **594,321,600** (0.59B), each with a card-declared0.10B vision encoder. FP8, W4A16-GPTQ and W4A16-AWQ are real official d3 repositories, not assumed third-party variants; none were downloaded or executed.

A further source discrepancy must be retained: d3's current pinned card explicitly declares **Qwen/Qwen3.8-27B** as its base (frontmatter line4 and license paragraph), while its config `model_type` remains `qwen3_5`. Therefore the statement “every family member's base is Qwen3.5” is too strong. Nano/mini/flash cards identify Qwen3.5-2B/4B/9B; lite/edge identify Qwen3.5-0.8B. Turbo config is qwen3_5, but its card does not specify an exact base-model ID, so do not invent one. None of these discrepancies affect the selected nano/mini run identity.

Turbo also has a different runtime contract (shared state readout, box/track types and optionallong_context), so the smaller models' audited identical-code claim must not be extended to turbo. Nano/mini **official board** text/vision values are confirmed directly against their pinned cards: **38.9/54.7** and **52.6/63.2**, respectively. Turbo's70.2/72.9 are described as the authors' estimates rather than official-board entries, so are not equivalent evidence.
