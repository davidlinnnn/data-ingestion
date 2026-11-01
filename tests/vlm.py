"""Stand-in VLM answers for tests: a valid answer for each method's schema."""

import json
from typing import Any

from kp_processing.ports.inference import Completion, FakeInference, completion

CANNED = {
    "picture-interpretation": {
        "caption": "A block diagram of an encoder and a decoder.",
        "description": "Four boxes: Encoder, Attention x4, Decoder 512 and the loss 0.031.",
        "figure_type": "diagram",
        "chart_values": [],
    },
    "formula": {"latex": "L = 2x + 3y - 7 = 0"},
    "code": {"code": "x = 1"},
}


def schema_name(request: dict[str, Any]) -> str:
    return request["response_format"]["json_schema"]["name"]


def images(request: dict[str, Any]) -> list[str]:
    """The data URLs of every image in the request's messages, in order."""
    return [
        part["image_url"]["url"]
        for message in request["messages"]
        if isinstance(message["content"], list)
        for part in message["content"]
        if part["type"] == "image_url"
    ]


def canned(request: dict[str, Any]) -> Completion:
    return completion(json.dumps(CANNED[schema_name(request)]))


def canned_vlm() -> FakeInference:
    return FakeInference(canned)
