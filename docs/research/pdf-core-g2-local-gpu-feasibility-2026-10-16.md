# G2 本機 Apple GPU／vLLM 可行性補充

日期：2026-10-16（Asia/Taipei）。使用者無法立即把專案移到公司，詢問目前硬體是否能做 GPU 與 vLLM 測試。本補充修正上一輪「下一步必須取得公司 dots endpoint」的安排；前次 CPU timeout、parser 缺口與原始 manifest 保留不改。

**可以在這台 Mac 繼續 GPU 可行性與有界模型驗證。** 硬體具備 Apple GPU，當前阻礙主要是各引擎／模型的支援組合，不能由 CPU timeout 推論必須換電腦。原生 MLX 模型推論、vLLM-Metal serving、公司 CUDA／vLLM 效能資格需要分別記錄。

第一手來源、checkpoint來源身分與引擎核對另見[研究明細](pdf-core-g2-local-gpu-feasibility-2026-10-16-sources.md)。

## 本機實測

| 項目 | 已觀察資料 |
|---|---|
| 硬體 | Apple M5 Pro，18 CPU cores、20 GPU cores、48 GiB unified memory |
| 環境 | macOS 26.4 arm64、Python 3.12、PyTorch 2.14.0 |
| GPU 可用性 | 主機權限下 `torch.backends.mps.is_available()` 為 true；CUDA false |
| 小算子 | MPS FP32／FP16／BF16 的128×128矩陣乘法均實際執行、同步並核對結果通過 |
| 記憶體 | 最後一次讀取 available 約15.50 GiB；Metal recommended max 約37.44 GiB，兩者都不是額外獨立VRAM。其他應用與CPU/GPU共用48 GiB |
| 尚未執行 | 本輪沒有模型GPU推論、MLX安裝或vLLM server執行；小算子通過不能代證整個模型所有算子相容 |

最初沙箱程序回報MPS不可用；主機權限下的小算子測試已排除「硬體無GPU或PyTorch根本不支援MPS」的推論。實測JSON (`pdf-core-g2-local-gpu-feasibility-2026-10-16/host-probe.json`)未保存設備序號或UUID。

dots完整BF16權重約6.08GB，因此以48 GiB總容量判斷，**有合理條件開始單模型、單頁、低併發的GPU探測**；這是依權重規模與主機容量的可行性判斷，不是峰值memory或latency保證。當下僅約15.5 GiB可用，長頁、KV cache與其他應用仍可能造成壓力；不自行關閉使用者應用，也不為fit RAM而默默量化或縮小輸入。

## 引擎與模型支援

1. **Docling／MLX：適合接續dots模型品質調查。** 已安裝Docling2.132的`MlxVlmEngine`提供MLX-VLM路徑；同版Transformers VLM engine的supported devices只有CPU、CUDA、XPU，不能把`device=mps`當成既有Transformers候選的可用開關。dots preset沒有明列MLX repo override，必須先做實際載入與官方parser接點smoke，不能稱為preset開箱即用已驗證。[固定Docling engine source](https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/docling/models/inference_engines/vlm/mlx_engine.py)
2. **MLX-VLM已具備dots_ocr實作。** 另有`mlx-community/dots.ocr-bf16`，模型卡指明由原dots.ocr轉換；其卡片沒有固定上游revision，不能直接視為前次`c0111ce...`的相同權重。優先評估既有固定checkpoint的上游MLX載入／格式轉換，核對tensor映射與processor/template；若只能使用社群轉換版，明記為另一個checkpoint候選。先維持BF16，量化不是預設捷徑。[MLX-VLM DOTS實作](https://github.com/Blaizzy/mlx-vlm/tree/main/mlx_vlm/models/dots_ocr)／[BF16模型卡](https://huggingface.co/mlx-community/dots.ocr-bf16)
3. **vLLM-Metal：可在Apple GPU做本機serving測試，但模型支援另查。** 官方vLLM文件指向這個以MLX／Metal執行的硬體plugin；本機macOS與arm64 Python符合安裝條件。官方多模態表明列Qwen3-VL、PaddleOCR-VL為experimental，未列dots.ocr，不能從MLX-VLM支援dots推導vLLM-Metal也已支援。若要測vLLM的OpenAI-compatible API、佇列與有限併發，使用其已列支援的明確checkpoint，結果與dots的模型評分分開。[vLLM GPU安裝](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)／[Metal安裝](https://docs.vllm.ai/projects/vllm-metal/en/stable/installation/)／[Metal支援模型](https://docs.vllm.ai/projects/vllm-metal/en/latest/supported_models/)

## 接續順序

- 先在隔離環境固定MLX／MLX-VLM版本與模型身分，使用上輪相同曝光頁、官方prompt和BF16做一次有界GPU探測；保留實際image size、stop reason、raw輸出、時間與memory。原生MLX與Transformers輸出不預設bit-identical。
- GPU正常完成後，沿用既有回歸與新validation核對內容和原生交付；不追加逐案prompt／字串修補，不因更快便通過F13/F14，不開holdout。
- vLLM-Metal另以其支援模型做本機API接點／有限併發；不為dots手寫新vLLM架構adapter。若必須原版dots＋公司相同CUDA kernel，才需要遠端GPU服務；專案本身可以仍放本機，由本機呼叫API。

此時不需搬移整個專案，也不需先購買GPU。Apple GPU品質觀察不能代證公司CUDA runtime輸出完全一致，Mac latency／吞吐不能外推公司GPU或高頻ingest SLO。已知行內HTML code parser損失仍在，G2與正式profile狀態不變。
