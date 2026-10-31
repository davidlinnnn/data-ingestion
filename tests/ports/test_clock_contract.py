"""The fake and the system clock pass one contract."""

import pytest

from kp_processing.ports.clock import FakeClock, SystemClock


@pytest.fixture(params=[FakeClock, SystemClock])
def clock(request):
    return request.param()


async def test_sleeping_moves_the_clock_forward_by_at_least_the_sleep(clock):
    before = clock.monotonic()

    await clock.sleep(0.01)

    assert clock.monotonic() - before >= 0.01
