"""The paper-pdf workflow: the stage graph of #129 as code, without enrichment yet (#131).

prepare -> parse group x N (in order) -> assemble -> inventory -> finalize, reporting the four
admission stages. Activities are addressed by name so that this module, which the workflow
sandbox re-imports, stays free of docling.
"""

import asyncio
from datetime import timedelta
from typing import Any, TypeVar

from temporalio import workflow
from temporalio.common import Priority, RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from kp_processing.ports.status_reporter import Progress, Stage, State, StatusReport
    from kp_processing.stages import (
        AssembleInput,
        FailureInput,
        FinalizeInput,
        GroupInput,
        GroupRef,
        InventoryInput,
        Plan,
        PrepareInput,
        Registered,
        error_block,
    )

T = TypeVar("T")
WORKFLOW = "paper-pdf"
STAGES_VERSION = "1"
FAILURE_TYPE = "ProcessingFailure"  # ApplicationError type carrying ProcessingFailure.details()


# The task queues are named after the worker pool that serves them (cpu, vlm, summary) and
# are shared by every pipeline; this workflow and its Activities run on the CPU queue.
CPU_QUEUE = "cpu"


def priority(admission_priority: Any) -> Priority:
    """Admission priority low waits behind normal on the shared queues. Temporal priority keys
    run 1 (first) to 5; Activities inherit the workflow's."""
    return Priority(priority_key=4 if admission_priority == "low" else 2)


_STORAGE_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
    non_retryable_error_types=[FAILURE_TYPE],
)
_SHORT = {"start_to_close_timeout": timedelta(minutes=2), "retry_policy": _STORAGE_RETRY}
# Heartbeats every runtime heartbeat_interval_s (15 s); a killed worker is noticed after 60 s.
_INFERENCE = {
    "start_to_close_timeout": timedelta(minutes=15),
    "heartbeat_timeout": timedelta(seconds=60),
    "retry_policy": RetryPolicy(maximum_attempts=3, non_retryable_error_types=[FAILURE_TYPE]),
}


@workflow.defn(name=WORKFLOW)
class PaperPdfWorkflow:
    def __init__(self) -> None:
        self._seq = 0
        self._sending: asyncio.Future[None] | None = None
        self._delivered = True  # whether the last report sent reached the receiver

    @workflow.run
    async def run(self, start: dict[str, Any]) -> dict[str, Any]:
        """Returns {"outcome": "complete" | "failed", "manifest_ref": result or failure key}."""
        info = workflow.info()
        self._start = start
        stage: Stage = "prepare"
        inventory: Registered | None = None
        try:
            self._report("prepare", "running")
            plan = await self._call("prepare", PrepareInput(start, info.run_id), Plan, _SHORT)
            self._report("prepare", "succeeded")

            stage = "parse"
            uid = start["document_uid"]
            pages = Progress(0, plan.page_count, "pages")
            self._report("parse", "running", pages)
            groups: list[GroupRef] = []
            for group_pages in plan.groups:
                group_input = GroupInput(uid, plan.source_key, plan.source_sha256, group_pages)
                groups.append(await self._call("parse_group", group_input, GroupRef, _INFERENCE))
                pages = Progress(group_pages[1], plan.page_count, "pages")
                self._report("parse", "running", pages)
            assemble_input = AssembleInput(uid, plan.source_key, plan.source_sha256, groups)
            assembly = await self._call("assemble", assemble_input, Registered, _INFERENCE)
            self._report("parse", "succeeded", pages)

            stage = "enrich"
            items = Progress(0, 0, "items")
            self._report("enrich", "running", items)
            inventory = await self._call(
                "inventory", InventoryInput(uid, assembly), Registered, _SHORT
            )
            # #108 screening and the enrichment Activities (#132-#134) go here.
            self._report("enrich", "succeeded", items)

            stage = "finalize"
            self._report("finalize", "running")
            finalize_input = FinalizeInput(start, plan, groups, assembly, inventory)
            ref = await self._call("finalize", finalize_input, str, _SHORT)
            self._report("finalize", "succeeded", manifest_ref=ref)
            outcome = {"outcome": "complete", "manifest_ref": ref}
        except ActivityError as err:
            details = _failure_details(err)
            error = error_block(
                details,
                occurred_at=_rfc3339(workflow.now()),
                support_ref=f"temporal:{info.workflow_id}/{info.run_id}",
            )
            failure = FailureInput(
                info.workflow_id, start, stage, details["cause"], error,
                inventory.ref if inventory else None,
            )  # fmt: skip
            ref = await self._call("register_failure", failure, str, _SHORT)
            self._report(stage, "failed", manifest_ref=ref, error=error)
            outcome = {"outcome": "failed", "manifest_ref": ref}
        if self._sending:
            await self._sending
        return outcome

    async def _call(self, name: str, arg: Any, result_type: type[T], options: dict[str, Any]) -> T:
        return await workflow.execute_activity(
            name, arg, result_type=result_type, task_queue=CPU_QUEUE, **options
        )

    def _report(
        self,
        stage: Stage,
        state: State,
        progress: Progress | None = None,
        manifest_ref: str | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        """Build the report here (seq, workflow time) so that every resend is identical, and
        queue it behind the previous one so that reports leave in seq order."""
        info = workflow.info()
        self._seq += 1
        version = self._start.get("adopted_version")
        report = StatusReport(
            request_id=info.workflow_id,
            attempt_id=info.run_id,
            seq=self._seq,
            stages_version=STAGES_VERSION,
            stage=stage,
            state=state,
            progress=progress,
            message=error["message"] if error else "",
            method_version=version if isinstance(version, str) else "",
            manifest_ref=manifest_ref,
            observed_at=_rfc3339(workflow.now()),
            error=error,
        )
        self._sending = asyncio.ensure_future(self._send(self._sending, report))

    async def _send(self, previous: asyncio.Future[None] | None, report: StatusReport) -> None:
        if previous:
            await previous
        if not self._delivered and report.seq < self._seq:
            return  # receiver unreachable: skip to the newest report instead of a budget each
        try:
            # The Activity spends the report budget itself; Temporal retries only lost workers.
            self._delivered = await workflow.execute_activity(
                "report",
                report,
                task_queue=CPU_QUEUE,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=3),
                result_type=bool,
            )
        except ActivityError:
            self._delivered = False
            workflow.logger.warning("status report seq %s abandoned", report.seq)


def _failure_details(err: ActivityError) -> dict[str, Any]:
    cause = err.cause
    if isinstance(cause, ApplicationError) and cause.type == FAILURE_TYPE and cause.details:
        return cause.details[0]
    # Retries exhausted, timeouts and bugs: a platform failure that a redispatch may cure.
    return {
        "cause": "platform",
        "category": "platform",
        "reason": "PLATFORM_ERROR",
        "message": str(cause or err),
        "retryable": True,
        "metadata": {"activity": err.activity_type or ""},
    }


def _rfc3339(moment: Any) -> str:
    return moment.isoformat().replace("+00:00", "Z")
