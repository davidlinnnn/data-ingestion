import shutil
from pathlib import Path

import pytest
from temporalio.testing import WorkflowEnvironment

from kp_processing.ports.clock import FakeClock
from kp_processing.ports.object_store import DictObjectStore
from kp_processing.ports.status_reporter import RecordingStatusReporter
from kp_processing.profile import load_profile
from kp_processing.stages import Ports, Runtime
from kp_processing.workflow import SEARCH_ATTRIBUTES
from tests.d3 import fake_d3
from tests.summary import fake_llm
from tests.vlm import canned_vlm

DEV_PROFILE = Path(__file__).parent / "profiles" / "paper-pdf-dev.yaml"


@pytest.fixture
def ports() -> Ports:
    return Ports(
        store=DictObjectStore(),
        reporter=RecordingStatusReporter(),
        clock=FakeClock(),
        vlm=canned_vlm(),
        summary=fake_llm(),
        d3=fake_d3(),
    )


@pytest.fixture
async def client():
    """A Temporal dev server; tests using it are marked network."""
    async with await WorkflowEnvironment.start_local(
        dev_server_existing_path=shutil.which("temporal"),
        search_attributes=list(SEARCH_ATTRIBUTES.values()),
    ) as env:
        yield env.client


@pytest.fixture
def runtime() -> Runtime:
    return Runtime(profile=load_profile(DEV_PROFILE), build_id="test-r1", custody_bucket="kp-dev")
