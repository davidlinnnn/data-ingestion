"""Clock port: time for retry budgets and backoff, so tests run without waiting (#129)."""

import asyncio
import time
from typing import Protocol


class Clock(Protocol):
    def monotonic(self) -> float:
        """Seconds on a clock that never goes back."""
        ...

    async def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class FakeClock:
    """Time moves only when someone sleeps; every sleep is recorded."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
