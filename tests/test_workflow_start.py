"""The workers' side of the start contract with admission (#207): their constants, the start of
`kp-canonicalization start-request` and prepare's reading of the input all match
workflow_start.json, admission's start as admission spec §10 defines it."""

import json
from importlib.resources import files

import pytest

from kp_canonicalization.cli import start_request
from kp_canonicalization.stages import PrepareInput, ProcessingFailure, prepare
from kp_canonicalization.workflow import (
    QUEUES,
    SEARCH_ATTRIBUTES,
    WORKFLOW,
    deployment_name,
    priority,
    task_queue,
)

EXAMPLE = json.loads((files("kp_canonicalization") / "workflow_start.json").read_text())


def test_the_constants_match_the_contract_example():
    version = EXAMPLE["input"]["adopted_version"]
    assert WORKFLOW == EXAMPLE["workflow"]
    assert deployment_name(version) == EXAMPLE["deployment"]
    assert task_queue(version) == EXAMPLE["task_queue"]
    assert list(QUEUES) == EXAMPLE["queues"]
    assert {p: priority(p).priority_key for p in EXAMPLE["priority_keys"]} == EXAMPLE[
        "priority_keys"
    ]
    assert {key.name: EXAMPLE["input"][field] for field, key in SEARCH_ATTRIBUTES.items()} == (
        EXAMPLE["search_attributes"]
    )


# An input admission added a field to still reaches an older build of the workers.
@pytest.mark.parametrize("extra", [{}, {"added_later": "x"}])
async def test_prepare_takes_the_example_and_goes_on_to_read_its_source(ports, runtime, extra):
    start = {**EXAMPLE["input"], **extra}

    with pytest.raises(ProcessingFailure) as caught:
        await prepare.run(PrepareInput(start=start, run_id="run_1"), ports, runtime)

    assert caught.value.reason == "SOURCE_NOT_FOUND"  # past validation; the stand-in has no file


@pytest.mark.network
async def test_start_request_starts_what_the_contract_example_describes(client, monkeypatch):
    async def connect(**_):
        return client

    monkeypatch.setattr("kp_canonicalization.cli.connect", connect)

    assert await start_request(EXAMPLE["input"], wait=False) == 0

    handle = client.get_workflow_handle(EXAMPLE["input"]["request_id"])
    described = await handle.describe()
    assert (described.workflow_type, described.task_queue) == (
        EXAMPLE["workflow"], EXAMPLE["task_queue"],
    )  # fmt: skip
    priority_key = EXAMPLE["priority_keys"][EXAMPLE["input"]["priority"]]
    assert described.raw_info.priority.priority_key == priority_key
    assert {pair.key.name: pair.value for pair in described.typed_search_attributes} == (
        EXAMPLE["search_attributes"]
    )
    started = (await handle.fetch_history()).events[0].workflow_execution_started_event_attributes
    assert json.loads(started.input.payloads[0].data) == EXAMPLE["input"]
