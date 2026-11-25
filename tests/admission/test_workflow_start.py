"""Admission's side of the start contract with the workers (#207); the start itself is checked on
Temporal in test_dispatcher.py."""

import json
from importlib.resources import files

from kp_admission.dispatcher import QUEUES, WORKFLOW, deployment_name, priority, task_queue

EXAMPLE = json.loads((files("kp_admission") / "workflow_start.json").read_text())


def test_the_constants_match_the_contract_example():
    version = EXAMPLE["input"]["adopted_version"]
    assert WORKFLOW == EXAMPLE["workflow"]
    assert deployment_name(version) == EXAMPLE["deployment"]
    assert task_queue(version) == EXAMPLE["task_queue"]
    assert list(QUEUES) == EXAMPLE["queues"]
    assert {p: priority(p).priority_key for p in EXAMPLE["priority_keys"]} == EXAMPLE[
        "priority_keys"
    ]
