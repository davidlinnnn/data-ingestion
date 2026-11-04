"""DEV fake of the Document Summary's model (#155): answers each step from its own request, so
the whole pipeline runs in process. Its map sentences are word runs of the section's text, its
judge supports what judge(sentence) says, its repair returns rewrite(sentence), and its reduce
turns the first statements into the overview, each citing its own statement."""

import json
import re
from collections.abc import Callable
from typing import Any

from kp_processing.ports.inference import Completion, FakeInference, completion
from kp_processing.stages import (
    ChunkInput,
    EnrichInput,
    OutcomeRef,
    OverviewInput,
    Ports,
    Runtime,
    summary,
)

WORDS_PER_SENTENCE = 12


def step(request: dict[str, Any]) -> str:
    return request["response_format"]["json_schema"]["name"]


def prompt(request: dict[str, Any]) -> str:
    return request["messages"][0]["content"]


def section_texts(text: str) -> dict[str, str]:
    return dict(re.findall(r'<section id="(S\d+)" heading="[^"]*">\n(.*?)\n</section>', text, re.S))


def targets(text: str) -> dict[str, int]:
    return {k: int(n) for k, n in re.findall(r"^- (S\d+): (\d+) sentence\(s\)$", text, re.M)}


def sentences(text: str) -> list[str]:
    """The sentences a verify request judges, or the one a repair request rewrites."""
    found = re.findall(r'<sentence n="\d+">(.*?)</sentence>', text, re.S)
    return found or re.findall(r"<sentence>(.*?)</sentence>", text, re.S)


def statements(text: str) -> list[str]:
    return re.findall(r"^\[\d+\] \(.*?\) (.*)$", text, re.M)


def map_sentences(text: str, count: int) -> list[str]:
    words = text.split()
    runs = [words[i : i + WORDS_PER_SENTENCE] for i in range(0, len(words), WORDS_PER_SENTENCE)]
    return [" ".join(run) for run in runs[:count]]


def answer(
    request: dict[str, Any],
    judge: Callable[[str], bool] = lambda sentence: True,
    rewrite: Callable[[str], str] = lambda sentence: sentence,
) -> dict[str, Any]:
    text = prompt(request)
    match step(request):
        case "map":
            texts = section_texts(text)
            return {"sections": [{"id": k, "sentences": map_sentences(texts[k], n)}
                                 for k, n in targets(text).items()]}  # fmt: skip
        case "verify":
            return {"verdicts": [{"n": n, "supported": judge(s), "reason": f"judged {n}"}
                                 for n, s in enumerate(sentences(text), 1)]}  # fmt: skip
        case "repair":
            (sentence,) = sentences(text)
            return {"quotes": [], "sentence": rewrite(sentence)}
        case "reduce":
            (target,) = re.findall(r"in at most (\d+) sentences", text)
            chosen = statements(text)[: int(target)]
            return {"sentences": [{"text": s, "sources": [n]} for n, s in enumerate(chosen, 1)]}
    raise ValueError(f"unknown step {step(request)}")


def fake_llm(
    judge: Callable[[str], bool] = lambda sentence: True,
    rewrite: Callable[[str], str] = lambda sentence: sentence,
) -> FakeInference:
    return FakeInference(lambda request: reply(answer(request, judge, rewrite)))


def reply(body: dict[str, Any]) -> Completion:
    return completion(json.dumps(body))


async def summarize_all(
    ports: Ports, runtime: Runtime, input: EnrichInput, complete: bool = True
) -> list[OutcomeRef]:
    """The summary Activities in workflow order, without Temporal: sections, every chunk, then
    the overview with the whole default budget."""
    plan = await summary.run_sections(input, ports, runtime)
    if plan.outcome is not None:
        return [plan.outcome]
    for index in range(plan.chunks if complete else 0):
        await summary.run_chunk(ChunkInput(input, plan, index), ports, runtime)
    budget = runtime.profile.runtime["summary_budget_s"]
    overview = OverviewInput(input, plan, complete, budget)
    return [await summary.run_overview(overview, ports, runtime)]
