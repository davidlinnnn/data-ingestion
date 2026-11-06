"""The d3-check package (#161, ADR-0011): the System One request it builds and the judgement it
reads from the reply. The questions and constants are #153's (tag research/153-d3-quality-check:
questions.json, selection/d3-mini.json); the expected values here were computed from those files."""

import base64
import hashlib
import io
import json

import pytest
from PIL import Image

from kp_processing.identity import canonical_json
from kp_processing.methods import InvalidOutput, InventoryItem, d3_check

ITEM: InventoryItem = {
    "item_id": "d3-check:formula:#/texts/7",
    "method": "d3-check",
    "target_ref": "#/texts/7",
    "page": 1,
    "bbox": {"l": 1.0, "t": 2.0, "r": 3.0, "b": 4.0, "coord_origin": "BOTTOMLEFT"},
    "input_refs": [],
}
# sha256 of the compact sorted-key JSON of each Q2 question in #153's questions.json.
QUESTIONS = {
    "formula@1": "c902f57ad88e2f8fd3ce6c43a9ddc588b4ca9d6f9e584d7374965c0d550aec24",
    "table-status@1": "2c105ef66ebed645fcc920d874dc5128e1ec5c06adf0a8a31bfc55233b47f487",
    "picture-ocr@1": "5aab3056f671f00c3040b2e86e43878b56337232c3ac1d857ddc487b48c2423e",
}


def png(width: int = 40, height: int = 10) -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (width, height), 200).save(buffer, format="PNG")
    return buffer.getvalue()


def record(method: str, content: str = "x = 1") -> bytes:
    method_id, version = method.split("@")
    return canonical_json(
        {
            "method_ref": {"id": method_id, "version": int(version), "digest": "0" * 64},
            "outcome": "success",
            "content": content,
        }
    )


def reply(noul: float) -> str:
    return json.dumps(
        {
            "model": "d3-mini",
            "answers": {"Q2": {"type": "noul", "noul": noul}},
            "usage": {"input_tokens": 591, "output_tokens": 0},
        }
    )


def judged(method: str, noul: float):
    return d3_check.parse(ITEM, [png(), record(method)], reply(noul))


def test_the_checks_cover_formula_table_and_picture_ocr_with_153s_questions():
    assert {
        ref: hashlib.sha256(
            canonical_json({"type": "noul", "instructions": check.instructions})
        ).hexdigest()
        for ref, check in d3_check.CHECKS.items()
    } == QUESTIONS
    assert {ref: (c.category, c.reason) for ref, c in d3_check.CHECKS.items()} == {
        "formula@1": ("formula LaTeX", "FORMULA_D3_UNFAITHFUL"),
        "table-status@1": ("table grid (Markdown)", "TABLE_D3_UNFAITHFUL"),
        "picture-ocr@1": ("recognised text", None),
    }


def test_a_request_asks_the_one_question_about_the_judged_content_and_its_image():
    image = png()

    request = d3_check.request(ITEM, [image, record("formula@1", r"\mathcal{L} = 2x")])

    assert request == {
        "model": "vllm-sr/d3-mini",
        "state": {"category": "formula LaTeX", "reconstruction": r"\mathcal{L} = 2x"},
        "images": ["data:image/png;base64," + base64.b64encode(image).decode()],
        "questions": {
            "Q2": {"type": "noul", "instructions": d3_check.CHECKS["formula@1"].instructions}
        },
    }


def test_an_image_over_1_6_megapixels_is_sent_downsized_and_a_smaller_one_as_it_is():
    large = png(2000, 1000)

    (url,) = d3_check.request(ITEM, [large, record("picture-ocr@1", "Encoder")])["images"]

    with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as sent:
        # scale = sqrt(1.6 MP / 2 MP); each side is truncated, as #153's prepare_inputs.py did
        assert (sent.size, sent.mode, sent.format) == ((1788, 894), "RGB", "PNG")


@pytest.mark.parametrize(
    ("method", "noul", "p", "contradictions"),
    [
        # p = sigmoid(a * logit(clip(noul, 1e-6, 1 - 1e-6)) + b); t_d 0.4452 and 0.3064
        ("formula@1", 0.99, 0.990810337956909, []),
        ("formula@1", 0.9, 0.696530180734985, []),
        ("formula@1", 0.5, 0.06317271386388043, ["FORMULA_D3_UNFAITHFUL"]),
        ("formula@1", 0.0, 1.571758363064166e-11, ["FORMULA_D3_UNFAITHFUL"]),
        ("table-status@1", 0.9, 0.9418515487613651, []),
        ("table-status@1", 0.5, 0.23948964408905538, ["TABLE_D3_UNFAITHFUL"]),
        ("table-status@1", 1.0, 0.9999999999448055, []),
        ("picture-ocr@1", 0.0, 0.0024236212131999247, []),  # a weak signal never contradicts
        ("picture-ocr@1", 0.9, 0.762782341888497, []),
    ],
)
def test_a_calibrated_score_at_or_below_the_threshold_contradicts_a_strong_category(
    method, noul, p, contradictions
):
    output = judged(method, noul)

    assert (output.outcome, output.contradictions) == ("success", contradictions)
    signal = output.signals["d3"]
    assert signal["p"] == pytest.approx(p, rel=1e-12)
    assert {k: signal[k] for k in ("model", "revision", "question", "score")} == {
        "model": "vllm-sr/d3-mini",
        "revision": "bd0090dd758d32ba59ef5c749910a8e87fc4391f",
        "question": "Q2",
        "score": noul,
    }
    assert signal["t_d"] == d3_check.CHECKS[method].t_d
    assert set(signal) == {"model", "revision", "question", "score", "p", "t_d"}


def test_the_raw_scores_on_either_side_of_the_formula_threshold_differ_in_status():
    # p == t_d at a raw score of 0.82385...
    assert judged("formula@1", 0.8238).contradictions == ["FORMULA_D3_UNFAITHFUL"]
    assert judged("formula@1", 0.8239).contradictions == []
    assert judged("table-status@1", 0.5470).contradictions == ["TABLE_D3_UNFAITHFUL"]
    assert judged("table-status@1", 0.5471).contradictions == []


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"answers": {}}),
        json.dumps({"answers": {"Q2": {"type": "noul", "error": "invalid_model_output"}}}),
        json.dumps({"answers": {"Q2": {"type": "noul", "noul": 1.5}}}),
        json.dumps({"answers": {"Q2": {"type": "noul", "noul": "0.9", "confidence": 0.9}}}),
    ],
)
def test_a_reply_without_a_noul_probability_is_an_invalid_output(content):
    with pytest.raises(InvalidOutput) as caught:
        d3_check.parse(ITEM, [png(), record("formula@1")], content)

    assert caught.value.reason == "SCHEMA_INVALID"
