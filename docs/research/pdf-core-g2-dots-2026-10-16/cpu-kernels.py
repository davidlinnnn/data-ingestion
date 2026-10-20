"""Small BF16 CPU kernel check, without model weights or quality claims."""
import json
import time
from pathlib import Path
import torch

torch.set_num_threads(4)
torch.set_num_interop_threads(1)
torch.manual_seed(0)
start = time.monotonic()
with torch.inference_mode():
    patch = torch.nn.Conv2d(3, 24, kernel_size=14, stride=14).to(dtype=torch.bfloat16)
    pixels = torch.zeros((1, 3, 56, 56), dtype=torch.bfloat16)
    embedded = patch(pixels)
    q = torch.ones((1, 2, 16, 12), dtype=torch.bfloat16)
    scores = (q @ q.transpose(-2, -1)) / 12**0.5
    eager = torch.softmax(scores.float(), dim=-1).to(torch.bfloat16) @ q
    sdpa = torch.nn.functional.scaled_dot_product_attention(q, q, q)
    assert embedded.shape == (1, 24, 4, 4)
    assert torch.isfinite(embedded).all() and torch.isfinite(eager).all()
    assert torch.allclose(eager, sdpa, atol=0.02, rtol=0.02)
    assert all(t.device.type == "cpu" for t in (embedded, eager, sdpa))
result = {"torch": torch.__version__, "device": "cpu", "dtype": "bfloat16",
          "threads": 4, "seconds": time.monotonic()-start, "passed": True,
          "kernels": ["Conv2d patch embedding", "eager attention", "language SDPA"],
          "model_weights_loaded": False, "model_inference_calls": 0,
          "limit": "Tiny tensor kernel support only; not full vision stack, memory capacity or page latency."}
Path(__file__).with_name("cpu-kernels.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result))
