"""#159: the 46 t4-accuracy display formulas as inputs for CodeFormulaV2 and the judges.

    env AWS_ACCESS_KEY_ID=kpdev AWS_SECRET_ACCESS_KEY=kpdev-secret \
        .venv/bin/python docs/research/codeformula-vs-vlm-2026-11-07/prepare.py OUT

Reads the formula targets of docs/validation/80/t4-accuracy/targets.json and their inputs from the
S3 stand-in (the t4-seam-b runs). OUT is the research folder outside git:

  inputs/<sha256>.png   the crop formula@1 sends the VLM (methods.formula._crop)
  sources/<sha256>.pdf  the source PDF
  items.json            per formula: label, paper, page, bbox, crop and source hashes, and the
                        native text formula@1 compares (third-party text, so outside git)

inputs.json next to this script is the same list without the native text.
"""

import asyncio
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
T4 = REPO / "docs/validation/80/t4-accuracy"
sys.path[:0] = [str(REPO / "src"), str(REPO / "docs/validation/80/t4-seam-b")]


def load_t4():
    spec = importlib.util.spec_from_file_location("t4acc", T4 / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def main(out: Path) -> int:
    from kp_processing.methods.formula import _crop, _native_text

    t4 = load_t4()
    targets = [t for t in json.loads((T4 / "targets.json").read_text()) if t["kind"] == "formula"]
    for folder in ("inputs", "sources"):
        (out / folder).mkdir(parents=True, exist_ok=True)
    items = []
    for t in targets:
        store = (await t4.document(t["paper"]))[0]
        inputs = [await store.get(s["ref"]) for s in t["item"]["input_refs"]]
        assert [sha(i) for i in inputs] == [s["sha256"] for s in t["item"]["input_refs"]]
        crop = _crop(t["item"], inputs)
        (out / "inputs" / f"{sha(crop)}.png").write_bytes(crop)
        (out / "sources" / f"{sha(inputs[1])}.pdf").write_bytes(inputs[1])
        items.append({"label": t["label"], "paper": t["paper"], "page": t["item"]["page"],
                      "bbox": t["item"]["bbox"], "crop_sha256": sha(crop),
                      "page_image_sha256": sha(inputs[0]), "source_sha256": sha(inputs[1]),
                      "native_text": _native_text(t["item"], inputs[1])})  # fmt: skip
    assert len({i["label"] for i in items}) == len(items) == 46
    (out / "items.json").write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n")
    public = [{k: v for k, v in i.items() if k != "native_text"} for i in items]
    (HERE / "inputs.json").write_text(json.dumps(public, indent=1) + "\n")
    print(len(items), "formulas,", len({i["source_sha256"] for i in items}), "papers")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]))))
