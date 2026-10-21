# W4b remote Python code audit

## Verdict

**No suspicious hidden network/exfiltration, shell execution, arbitrary user-state evaluation, or unrelated persistent file modification found in the pinned repository code.** This does not mean the repository contains no network/write functions: documented Hub downloads, URL media fetching, video tempfile decoding, optional serving, and GPU JIT caches exist. The approved local PIL/no-video/local-directory inference route bypasses those optional paths. Audit completed before any remote code/model execution by this auditor.

The 8 Python files (4,396 lines total) are byte-identical across nano/mini/flash at their pinned revisions. Hashes are retained per repository in `audit-code-sha256.json`. Reviewed imports/top-level statements, model loading, image/video loading, dynamically imported local modules, inference/readout, fast-path guards, and CLI/server entry points; all weight data is safetensors. This is a repository-specific static review, not an audit of installed PyTorch/Transformers dependencies.

## Relevant behavior and exact locations

Locations below refer to [`d3-nano` revision462efc366229ea268cf4eed3738b3fc4415e4817](https://huggingface.co/vllm-sr/d3-nano/tree/462efc366229ea268cf4eed3738b3fc4415e4817); identical source applies to mini/flash.

| File:lines | Behavior | Reachability in this evaluation |
|---|---|---|
| modeling_d3.py:88–106 | `hf_hub_download` checks decision config for remote repo names | Local model directory returns at lines89–91; predownloaded local path avoids Hub access |
| d3_runtime.py:848–858 | `snapshot_download` for remote model ID | Existing local dir returns at853–854 |
| d3_runtime.py:436–446,475–477 | `urllib.request.urlopen` fetches explicitly supplied HTTP image URL | Pass only already-opened PIL objects;465–466 returns RGB conversion before URL branch |
| d3_runtime.py:614–698,745–786 | Optional video decoding; NamedTemporaryFile write637–639 then unlink in finally | `videos=None`; not reached |
| d3_runtime.py:815–845 | `importlib.spec_from_file_location` + exec_module for package's own `d3_fast.py` | Verified same-directory code, not state text or downloaded unknown source |
| d3_fast.py:74–95 | Same-directory dynamic import of `d3_kernels.py` | Only ROCm eligible fast path; not MPS/CPU |
| d3_fast.py:28–45,513–518 | Fast path requires ROCm GPU | Explicit MPS/CPU returns without Triton execution |
| d3_kernels.py:24–33 | NumPy/PyTorch/Triton imports and JIT decorators | GPU-kernel module only; optional JIT disk cache is expected GPU inference behavior |
| d3_server.py:349–392 | Explicit local HTTP server bind/serve if main/serve invoked | Never import/invoke server in evaluation; no server starts on normal model import |
| d3_engine.py:30–34; d3_server.py:42–43 | sys.path insertion; optional Triton cache env default | CLI/engine not used by AutoModel; no unrelated writes |
| modeling_d3.py:293–302 | save_pretrained/push_to_hub refuse with NotImplementedError | No publishing path |
| d3_runtime.py:1205–1213 | Reject optional GPU-only FLA kernels on CPU | CPU environment must omit these optional packages |

Python/HuggingFace may write normal bytecode/module caches on import; use `PYTHONDONTWRITEBYTECODE=1` and put HF_HOME/HF_MODULES_CACHE inside W4b if output isolation is required. Hub offline flags plus local_files_only should be set for execution. Local PIL inputs and no videos are a caller-side invariant, not a modification to model code. `AutoProcessor.from_pretrained(str(root))` and backbone/tokenizer loads use the local root.

## Runtime details that affect valid measurement

- `modeling_d3.py:149–172` fixes BF16 backbone/FP32 readout and SDPA. Float16/float32 overrides are explicitly rejected; casting for convenience would depart from official numerics.
- `d3_runtime.py:1199–1203`: default is CUDA if present else CPU; **MPS must be explicitly selected** (`device="mps"`). No CUDA-only assertion exists on the plain path; actual MPS operator support still requires a dev probe.
- `d3_runtime.py:2113–2115`: built-in synchronize only handles CUDA. Surround MPS timings with `torch.mps.synchronize()`; otherwise asynchronous timing undercounts cost.
- `d3_runtime.py:2051–2069`: no text generation, typed questions go prepare→run→respond. `state` is formatted as data; it is never Python eval/exec.
- `d3_format.py:25–27,123–146`: fixed system prompt and exact model input template. Use `system_one` rather than reconstructing logits/prompts independently.
- `d3_format.py:173–187`: noul probability is true option share; choice mapping exposes each option probability. `d3_runtime.product_answer` adds an entropy-based confidence, not the selected option probability; see the explicit pinned-code/documentation discrepancy below.

Recommendation: safe to proceed with pinned localdir/PIL/no-video inference, no runtime source patching, no optional URL inputs, offline Hub flags, and explicit measured MPS device or documented CPU fallback. No model inference or weight downloads were performed by this research task.

## Pinned-code / documentation discrepancy: `confidence`

Confirmed directly in all three byte-identical pinned runtimes: **`confidence` is not the chosen option probability**. [`d3_runtime.py:316–322`](https://huggingface.co/vllm-sr/d3-nano/blob/462efc366229ea268cf4eed3738b3fc4415e4817/d3_runtime.py#L316) defines it as `1 - ShannonEntropy(p)/log(number_of_options)`, clipped to [0,1]; [`product_answer`, lines341–343](https://huggingface.co/vllm-sr/d3-nano/blob/462efc366229ea268cf4eed3738b3fc4415e4817/d3_runtime.py#L341) adds that quantity for choice answers. Score answers also use it at335.

The [official recipe](https://recipes.vllm.ai/vllm-sr/d3-nano) describes confidence as the chosen-option probability. That description conflicts with the pinned reference implementation. For example, the symmetric binary distribution [0.5,0.5] has a maximum option probability0.5 but reference confidence0. This is a documentation/runtime mismatch, not a reason to replace the official forward path.

The evaluation must use **`answer["probabilities"]["faithful"]` for Q1 and `answer["noul"]` for Q2**, never the top-level choice confidence. Consequently this mismatch does not affect the registered scoring rule when those explicit fields are used. No runtime source was modified.
