"""The paper-pdf workflow: the stage graph of #129 as code (#131), with local enrichment (#132)
and VLM enrichment (#133).

prepare -> parse group x N (in order) -> assemble -> inventory -> {local, VLM} enrichment ->
finalize,
reporting the four admission stages. Activities are addressed by name so that this module,
which the workflow sandbox re-imports, stays free of docling.
"""

import asyncio
import math
from datetime import timedelta
from typing import Any, Literal, TypeVar

from temporalio import workflow
from temporalio.common import Priority, RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from kp_processing.ports.status_reporter import Progress, Stage, State, StatusReport
    from kp_processing.stages import (
        AssembleInput,
        EnrichInput,
        FailureInput,
        FinalizeInput,
        GroupInput,
        GroupRef,
        InventoryInput,
        InventoryRef,
        OutcomeRef,
        Plan,
        PrepareInput,
        ProcessingFailure,
        Registered,
        error_block,
    )

T = TypeVar("T")
WORKFLOW = "paper-pdf"
STAGES_VERSION = "1"
FAILURE_TYPE = "ProcessingFailure"  # ApplicationError type carrying ProcessingFailure.details()


# Task queues are named after what their workers can run and are shared by every pipeline:
# the workflow and light Activities on orchestration, docling on inference (one call per
# worker), the external enrichment services on vlm and summary.
ORCHESTRATION_QUEUE = "orchestration"
INFERENCE_QUEUE = "inference"
VLM_QUEUE = "vlm"
Queue = Literal["orchestration", "inference", "vlm"]


def priority(admission_priority: Any) -> Priority:
    """Admission priority low waits behind normal on the shared queues. Temporal priority keys
    run 1 (first) to 5; Activities inherit the workflow's."""
    return Priority(priority_key=4 if admission_priority == "low" else 2)


# prepare runs before the plan exists, and register_failure may too: they take these options.
_BOOTSTRAP = {
    "task_queue": ORCHESTRATION_QUEUE,
    "start_to_close_timeout": timedelta(minutes=2),
    "retry_policy": RetryPolicy(
        initial_interval=timedelta(seconds=2),
        maximum_interval=timedelta(seconds=30),
        maximum_attempts=5,
        non_retryable_error_types=[FAILURE_TYPE],
    ),
}


def activity_options(runtime: dict[str, Any], items: int = 0) -> dict[Queue, dict[str, Any]]:
    """execute_activity options per task queue from the profile's runtime section:
    activity_retry.<queue> ({initial_s, multiplier, cap_s, max_attempts}; ProcessingFailure
    never retried); start_to_close_s.<queue>, except vlm's backstop for a document of `items`
    inventory items (#93 §3.2): ceil(items / vlm_concurrency_per_document) x
    vlm_request_deadline_s.total x retry.max_attempts + external_start_to_close_slack_s; and
    heartbeat_timeout_s.<queue> for inference and vlm."""
    vlm_s = (
        math.ceil(items / runtime["vlm_concurrency_per_document"])
        * runtime["vlm_request_deadline_s"]["total"]
        * runtime["retry"]["max_attempts"]
        + runtime["external_start_to_close_slack_s"]
    )
    options: dict[Queue, dict[str, Any]] = {}
    for queue in ("orchestration", "inference", "vlm"):
        retry = runtime["activity_retry"][queue]
        seconds = vlm_s if queue == "vlm" else runtime["start_to_close_s"][queue]
        options[queue] = {
            "task_queue": queue,
            "start_to_close_timeout": timedelta(seconds=seconds),
            "retry_policy": RetryPolicy(
                initial_interval=timedelta(seconds=retry["initial_s"]),
                backoff_coefficient=retry["multiplier"],
                maximum_interval=timedelta(seconds=retry["cap_s"]),
                maximum_attempts=retry["max_attempts"],
                non_retryable_error_types=[FAILURE_TYPE],
            ),
        }
        if queue != "orchestration":
            options[queue]["heartbeat_timeout"] = timedelta(
                seconds=runtime["heartbeat_timeout_s"][queue]
            )
    return options


@workflow.defn(name=WORKFLOW)
class PaperPdfWorkflow:
    def __init__(self) -> None:
        self._seq = 0
        self._sending: asyncio.Future[None] | None = None
        self._delivered = True  # whether the last report sent reached the receiver

    @workflow.run
    async def run(self, start: Any) -> dict[str, Any]:
        """Returns {"outcome": "complete" | "failed", "manifest_ref": result or failure key}."""
        info = workflow.info()
        self._start = start
        stage: Stage = "prepare"
        inventory: InventoryRef | None = None
        orchestration = _BOOTSTRAP
        try:
            self._report("prepare", "running")
            plan = await self._call(
                "prepare", PrepareInput(start, info.run_id), Plan, orchestration
            )
            self._report("prepare", "succeeded")
            options = activity_options(plan.runtime)
            orchestration, inference = options["orchestration"], options["inference"]

            stage = "parse"
            uid = start["document_uid"]
            pages = Progress(0, plan.page_count, "pages")
            self._report("parse", "running", pages)
            groups: list[GroupRef] = []
            for group_pages in plan.groups:
                group_input = GroupInput(uid, plan.source_key, plan.source_sha256, group_pages)
                groups.append(await self._call("parse_group", group_input, GroupRef, inference))
                pages = Progress(group_pages[1], plan.page_count, "pages")
                self._report("parse", "running", pages)
            assemble_input = AssembleInput(uid, plan.source_key, plan.source_sha256, groups)
            assembly = await self._call("assemble", assemble_input, Registered, inference)
            self._report("parse", "succeeded", pages)

            stage = "enrich"
            inventory_input = InventoryInput(
                uid, plan.source_key, plan.source_sha256, groups, assembly
            )
            inventory = await self._call("inventory", inventory_input, InventoryRef, orchestration)
            self._report("enrich", "running", Progress(0, inventory.items, "items"))
            # #108 screening goes here, before any enrichment; the summary Activity (#134)
            # joins the two below.
            enrich_input = EnrichInput(uid, inventory, info.workflow_id, info.run_id)
            vlm = activity_options(plan.runtime, inventory.items)["vlm"]
            local, external = await asyncio.gather(
                self._call("enrich_local", enrich_input, list[OutcomeRef], inference),
                self._call("enrich_vlm", enrich_input, list[OutcomeRef], vlm),
            )
            outcomes = local + external
            self._report("enrich", "succeeded", Progress(len(outcomes), inventory.items, "items"))

            stage = "finalize"
            self._report("finalize", "running")
            finalize_input = FinalizeInput(start, plan, groups, assembly, inventory, outcomes)
            ref = await self._call("finalize", finalize_input, str, orchestration)
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
            ref = await self._call("register_failure", failure, str, orchestration)
            self._report(stage, "failed", manifest_ref=ref, error=error)
            outcome = {"outcome": "failed", "manifest_ref": ref}
        if self._sending:
            await self._sending
        return outcome

    async def _call(self, name: str, arg: Any, result_type: type[T], options: dict[str, Any]) -> T:
        return await workflow.execute_activity(name, arg, result_type=result_type, **options)

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
        version = self._start.get("adopted_version") if isinstance(self._start, dict) else None
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
                task_queue=ORCHESTRATION_QUEUE,
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
    return ProcessingFailure(
        "platform",
        "platform",
        "PLATFORM_ERROR",
        str(cause or err),
        retryable=True,
        metadata={"activity": err.activity_type or ""},
    ).details()


def _rfc3339(moment: Any) -> str:
    return moment.isoformat().replace("+00:00", "Z")
