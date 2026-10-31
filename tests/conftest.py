from pathlib import Path

import pytest

from kp_processing.ports.object_store import DictObjectStore
from kp_processing.ports.status_reporter import RecordingStatusReporter
from kp_processing.profile import load_profile
from kp_processing.stages import Ports, Runtime

DEV_PROFILE = Path(__file__).parent / "profiles" / "paper-pdf-dev.yaml"


@pytest.fixture
def ports() -> Ports:
    return Ports(store=DictObjectStore(), reporter=RecordingStatusReporter())


@pytest.fixture
def runtime() -> Runtime:
    return Runtime(profile=load_profile(DEV_PROFILE), build_id="test-r1")
