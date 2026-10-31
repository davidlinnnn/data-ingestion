"""Seam A: status report delivery never fails processing (#131)."""

import dataclasses

from kp_processing.ports.status_reporter import Position, ReportOutcome
from kp_processing.stages import Ports, report
from tests.ports.test_status_reporter import report as a_report
from tests.stages.conftest import with_runtime


class Scripted:
    def __init__(self, *outcomes: ReportOutcome) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    async def report(self, report):
        self.calls += 1
        return self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]


def ports_with(ports, reporter) -> Ports:
    return dataclasses.replace(ports, reporter=reporter)


async def test_a_delivered_report_is_sent_once(ports, runtime):
    reporter = Scripted(ReportOutcome(delivered=True))

    assert await report.run(a_report(seq=1), ports_with(ports, reporter), runtime) is True
    assert reporter.calls == 1


async def test_an_undelivered_report_is_retried_until_delivered(ports, runtime):
    down = ReportOutcome(delivered=False, error="HTTP 503")
    reporter = Scripted(down, ReportOutcome(delivered=True))

    assert await report.run(a_report(seq=1), ports_with(ports, reporter), runtime) is True
    assert reporter.calls == 2


async def test_a_receiver_that_stays_down_costs_at_most_the_budget(ports, runtime):
    reporter = Scripted(ReportOutcome(delivered=False, error="ConnectError"))

    no_budget = with_runtime(runtime, status_report_budget_s=0)

    delivered = await report.run(a_report(seq=1), ports_with(ports, reporter), no_budget)

    assert delivered is False
    assert reporter.calls == 1


async def test_an_out_of_order_answer_is_final(ports, runtime):
    reporter = Scripted(ReportOutcome(delivered=False, position=Position("run_1", 7)))

    assert await report.run(a_report(seq=3), ports_with(ports, reporter), runtime) is False
    assert reporter.calls == 1


async def test_retries_back_off_doubling_up_to_10_s_within_the_budget(ports, runtime):
    reporter = Scripted(ReportOutcome(delivered=False, error="ConnectError"))
    budget = with_runtime(runtime, status_report_budget_s=20)

    delivered = await report.run(a_report(seq=1), ports_with(ports, reporter), budget)

    assert delivered is False
    assert ports.clock.sleeps == [1, 2, 4, 8, 5]  # the last one ends at the budget
    assert reporter.calls == 6
