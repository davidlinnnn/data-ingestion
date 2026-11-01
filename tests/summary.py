"""DEV mock of the summary API (#134): fake sentences built from the request's own sections,
one with evidence and one without, so that both of the package's support paths run. The
Seam B stand-in serves the same answer over HTTP."""

from typing import Any

from kp_processing.ports.inference import Completion, FakeInference

MODEL = "summary-mock"


def answer(request: dict[str, Any]) -> dict[str, Any]:
    """{"model": MODEL, "sentences": [...]} for a provisional-contract request: for the first
    section with text, a sentence made of that text's first 12 words with evidence
    [{"section_id"}] of that section; for the next section with text, if any, the same kind of
    sentence without "evidence". Both sentences are supported, the second by overlap."""
    raise NotImplementedError


def completion(body: dict[str, Any]) -> Completion:
    """The Completion SummaryApi returns for a 2xx response body: content the compact JSON,
    model body["model"], usage {}, body the same bytes."""
    raise NotImplementedError


def mock_summary() -> FakeInference:
    return FakeInference(lambda request: completion(answer(request)))
