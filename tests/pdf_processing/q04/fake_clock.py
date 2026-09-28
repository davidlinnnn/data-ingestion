"""Shared deterministic wall and monotonic clock for local admission tests."""


class FakeClock:
    def __init__(self):
        self.wall = 1_000.0
        self.monotonic_value = 0.0

    def time(self):
        return self.wall

    def monotonic(self):
        return self.monotonic_value

    def sleep(self, seconds):
        self.wall += seconds
        self.monotonic_value += seconds
