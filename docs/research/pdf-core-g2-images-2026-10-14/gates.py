"""Exercise installed description dispatch/error contracts with a fake engine, no inference."""
import json
from pathlib import Path

from PIL import Image
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import ItemAndImageEnrichmentElement
from docling.datamodel.pipeline_options import PictureDescriptionVlmEngineOptions
from docling.models.inference_engines.vlm import VlmEngineOutput
from docling.models.picture_description_base_model import PictureDescriptionBaseModel
from docling.models.stages.picture_description.picture_description_vlm_engine_model import PictureDescriptionVlmEngineModel
from docling_core.types.doc import DoclingDocument, PictureItem

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


class FakeEngine:
    def __init__(self, mode="normal"):
        self.mode, self.calls = mode, []

    def predict_batch(self, inputs):
        self.calls.append({"inputs": len(inputs), "max_new_tokens": [x.max_new_tokens for x in inputs]})
        if self.mode == "exception":
            raise RuntimeError("Injected model failure; no network or model is involved")
        if self.mode == "short":
            return []
        return [VlmEngineOutput(text="mock output; not semantic evidence") for _ in inputs]

    def cleanup(self):
        pass


def exercise(input_id, *, mode="normal", overrides=None, small=False):
    source = next(x for x in json.loads((HERE / "layout/native-inventory.json").read_text())["pictures"] if x["input_id"] == input_id)
    doc = DoclingDocument.load_from_json(REPO / source["provider_document"])
    picture = PictureItem.model_validate_json((HERE / "classifier/runs" / input_id / "picture-item.json").read_text())
    if small:
        # This is an explicit synthetic gate control, not a changed source oracle or real layout result.
        doc.pages[picture.prov[0].page_no].size.width *= 10
        doc.pages[picture.prov[0].page_no].size.height *= 10
    options = PictureDescriptionVlmEngineOptions.from_preset("smolvlm")
    for key, value in (overrides or {}).items():
        setattr(options, key, value)
    engine = FakeEngine(mode)
    stage = object.__new__(PictureDescriptionVlmEngineModel)
    PictureDescriptionBaseModel.__init__(stage, enabled=True, enable_remote_services=False,
        artifacts_path=None, options=options, accelerator_options=AcceleratorOptions(device="cpu"))
    stage.engine, stage.options = engine, options
    output = list(stage(doc, [ItemAndImageEnrichmentElement(item=picture, image=Image.open(REPO / source["path"]))]))
    descriptions = [p.meta.description.text for p in output if p.meta and p.meta.description]
    return {"input_id": input_id, "mode": mode, "explicit_synthetic_small_control": small,
            "options_overrides": overrides, "engine_calls": engine.calls, "yielded_items": len(output),
            "descriptions": descriptions, "required_nonempty_description_satisfied": len(descriptions) == 1 and bool(descriptions[0].strip())}


native = json.loads((HERE / "layout/native-inventory.json").read_text())["pictures"]
actual = [exercise(x["input_id"]) for x in native]
assert all(x["required_nonempty_description_satisfied"] for x in actual)
selected = native[0]["input_id"]
small = exercise(selected, small=True)
assert small["engine_calls"] == [] and small["yielded_items"] == 0
small_disabled = exercise(selected, small=True, overrides={"picture_area_threshold": 0})
assert small_disabled["required_nonempty_description_satisfied"]
denied = exercise(selected, overrides={"classification_deny": ["flow_chart"]})
assert denied["engine_calls"] == [] and denied["yielded_items"] == 0
failed = exercise(selected, mode="exception")
assert failed["yielded_items"] == 1 and failed["descriptions"] == [""]
assert not failed["required_nonempty_description_satisfied"]
short = exercise(selected, mode="short")
assert short["engine_calls"] and short["yielded_items"] == 0
assert not short["required_nonempty_description_satisfied"]
report = {"scope": "No model/API execution; fake engine isolates installed description size/filter/error/short-output behavior",
          "actual_native_metadata_default_dispatch": actual,
          "controls": [small, small_disabled, denied, failed, short],
          "interpretation": "Default dispatch retains these6current pictures; small/filter skips and empty/short/swallowed failures need explicit required-work outcomes. No full-pipeline document-deletion claim."}
(HERE / "description-gates.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"native_dispatch_cases": len(actual), "controls_passed": 5, "model_or_api_calls": 0}))
