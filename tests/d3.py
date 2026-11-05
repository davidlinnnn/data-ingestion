"""Stand-in d3 answers for tests: System One replies with one noul score per question."""

import json
from collections.abc import Callable
from typing import Any

from kp_processing.ports.inference import Completion, FakeInference

Score = float | Exception


def system_one(request: dict[str, Any], noul: float) -> Completion:
    """The reply vLLM Semantic Router and d3_server.py give: {"model", "answers", "usage"}."""
    usage = {"input_tokens": 591, "output_tokens": 0}
    answers = {question: {"type": "noul", "noul": noul} for question in request["questions"]}
    body = json.dumps({"model": "d3-mini", "answers": answers, "usage": usage})
    return Completion(body, None, "d3-mini", None, usage, body.encode())


def fake_d3(score: Score | Callable[[dict[str, Any]], Score] = 0.99) -> FakeInference:
    """Every question gets the score: a number, an exception to raise, or score(request)."""

    def answer(request: dict[str, Any]) -> Completion | Exception:
        value = score(request) if callable(score) else score
        return value if isinstance(value, Exception) else system_one(request, value)

    return FakeInference(answer)


def category(request: dict[str, Any]) -> str:
    return request["state"]["category"]
