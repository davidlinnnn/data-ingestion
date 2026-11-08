"""summarize(): the Document Summary's orchestration in workflow code, for every format's
workflow (#155). It runs the summary Activities of kp_canonicalization.stages.summary under one
workflow timer of summary_budget_s; what the summary says is the method package's."""

import asyncio
from typing import Any

from temporalio import workflow
from temporalio.common import Priority
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from kp_canonicalization.stages import (
        FAILURE_TYPE,
        ChunkInput,
        EnrichInput,
        OutcomeRef,
        OverviewInput,
        SummaryPlan,
    )


async def summarize(
    input: EnrichInput, runtime: dict[str, Any], options: dict[str, Any]
) -> list[OutcomeRef]:
    """The Document Summary's OutcomeRef, from the Activities
    summary_sections, then summary_chunk per chunk (at most summary_concurrency_per_document at
    once, each with fairness key document_uid), then summary_overview, all with options.

    When summary_budget_s (runtime) runs out before every chunk returned, the rest are cancelled
    and summary_overview is told the chunks are incomplete; a chunk that failed for good after its
    retries counts as incomplete too. A chunk's ProcessingFailure (ApplicationError of
    FAILURE_TYPE) is raised, failing the document.
    """
    deadline = workflow.time() + runtime["summary_budget_s"]
    plan = await workflow.execute_activity(
        "summary_sections", input, result_type=SummaryPlan, **options
    )
    if plan.outcome is not None:
        return [plan.outcome]
    fair = {
        **options,
        "priority": Priority(
            priority_key=workflow.info().priority.priority_key,
            fairness_key=input.document_uid,
        ),
    }
    gate = asyncio.Semaphore(runtime["summary_concurrency_per_document"])

    async def chunk(index: int) -> None:
        async with gate:
            await workflow.execute_activity("summary_chunk", ChunkInput(input, plan, index), **fair)

    tasks = [asyncio.ensure_future(chunk(index)) for index in range(plan.chunks)]
    complete = True
    if tasks:
        done, pending = await asyncio.wait(tasks, timeout=max(0.0, deadline - workflow.time()))
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        complete = not pending
        for task in done:
            error = task.exception()
            if error is None:
                continue
            cause = error.cause if isinstance(error, ActivityError) else None
            if isinstance(cause, ApplicationError) and cause.type == FAILURE_TYPE:
                raise error
            complete = False
    budget = max(0.0, deadline - workflow.time())
    overview = OverviewInput(input, plan, complete, budget)
    outcome = await workflow.execute_activity(
        "summary_overview", overview, result_type=OutcomeRef, **options
    )
    return [outcome]
