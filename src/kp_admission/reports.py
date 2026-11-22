"""Status report intake (#97, admission spec §7.3): canonical processing's reports of the current
attempt, the run the dispatcher started, move its request to processing and end it."""

import logging
from dataclasses import dataclass
from typing import Any, Literal

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, BaseModel, Field, StrictInt, model_validator

from kp_admission.requests import Candidate, lock_document, record_outcome

log = logging.getLogger(__name__)

Result = Literal[
    "recorded", "repeated", "out_of_order", "not_current", "no_attempt", "not_found", "bad_stage"
]


class Pipeline(BaseModel, frozen=True, extra="forbid"):
    """A reporter's registration (admission spec §7.3): its pipeline ID, the track its failures
    show under (`canonical`, or a projection with #252), its ordered stages, and the deadlines
    past which a pending or running attempt is progress_stalled."""

    pipeline_id: str = Field(min_length=1)
    track: str = Field(min_length=1)
    stages: list[str] = Field(min_length=1)
    start_deadline_s: int = Field(gt=0)  # from dispatch to the first report
    update_interval_s: int = Field(gt=0)  # from one report to the next


class Progress(BaseModel, extra="forbid"):
    done: StrictInt
    total: StrictInt
    unit: str


class ErrorBlock(BaseModel, extra="forbid"):
    """AIP-193-style (admission design record, Error block); admission reads only
    metadata.cause, which decides between rejected and failed."""

    domain: str
    reason: str
    message: str
    retryable: bool
    metadata: dict[str, str] = {}
    support_ref: str | None = None
    occurred_at: str | None = None


class Report(BaseModel, extra="forbid"):
    """The twelve fields of #129, every one present; progress, manifest_ref and error may be
    null, and error is present exactly when the state is failed. The candidate (#251) may be
    left out."""

    request_id: str
    attempt_id: str = Field(min_length=1)
    seq: StrictInt = Field(ge=1)
    stages_version: str
    stage: str
    state: Literal["pending", "running", "succeeded", "failed"]
    progress: Progress | None
    message: str
    method_version: str
    manifest_ref: str | None
    observed_at: AwareDatetime
    error: ErrorBlock | None
    # Optional, so a worker that predates it (#81) is still taken; read on the last success only.
    candidate: Candidate | None = None

    @model_validator(mode="after")
    def _error_on_failure(self) -> "Report":
        if (self.state == "failed") != (self.error is not None):
            raise ValueError("error is required when state is failed, and only then")
        return self


class Position(BaseModel):
    """The current attempt of a request and the seq of its last report taken (0 before any)."""

    attempt_id: str
    seq: int


@dataclass(frozen=True)
class Taken:
    result: Result
    position: Position | None = None  # on a refusal


_REQUEST = """
SELECT attempt_id, last_report FROM request WHERE request_id = %s AND kind = 'process' FOR UPDATE
"""

# A report while the request has not ended moves it to processing; one after keeps the outcome.
_RECORD = """
UPDATE request SET last_report = %s, reported_at = now(), updated_at = now(),
                   state = CASE WHEN state = 'queued' THEN 'processing' ELSE state END
WHERE request_id = %s
"""


async def take(conn: AsyncConnection, pipeline: Pipeline, report: Report) -> Taken:
    """Takes the report of a process request, in one transaction. Only the current attempt's
    reports count, each with a seq above the last one taken (gaps are fine): the first moves the
    request to processing, and a failure, or success at the last registered stage with its
    candidate, ends it as requests.record_outcome does. A repeat of the last report is `repeated`
    and changes nothing; any other report in the wrong place is `out_of_order`, or `not_current`
    from another attempt, with the current position. `no_attempt` while the dispatcher has not
    recorded the attempt: the sender retries. `bad_stage` for a stage the pipeline did not
    register."""
    if report.stage not in pipeline.stages:
        return _logged(pipeline, report, Taken("bad_stage"))
    ends = report.state == "failed" or (
        report.state == "succeeded" and report.stage == pipeline.stages[-1]
    )
    async with conn.transaction():
        if ends:
            await lock_document(conn, report.request_id)
        row = await (await conn.execute(_REQUEST, (report.request_id,))).fetchone()
        if row is None:
            return _logged(pipeline, report, Taken("not_found"))
        attempt_id, last = row
        if attempt_id is None:
            return _logged(pipeline, report, Taken("no_attempt"))
        position = Position(attempt_id=attempt_id, seq=last["seq"] if last else 0)
        body = report.model_dump(mode="json")
        if report.attempt_id != attempt_id:
            return _logged(pipeline, report, Taken("not_current", position))
        if last == body:
            return _logged(pipeline, report, Taken("repeated"))
        if last and report.seq <= last["seq"]:
            return _logged(pipeline, report, Taken("out_of_order", position))
        await conn.execute(_RECORD, (Jsonb(body), report.request_id))
        if ends:
            await record_outcome(
                conn,
                report.request_id,
                "failed" if report.state == "failed" else "succeeded",
                body["error"],
                report.observed_at,
                report.candidate,
            )
    return _logged(pipeline, report, Taken("recorded"))


def _logged(pipeline: Pipeline, report: Report, taken: Taken) -> Taken:
    fields = {
        "pipeline": pipeline.pipeline_id,
        "request_id": report.request_id,
        "attempt_id": report.attempt_id,
        "seq": report.seq,
        "stage": report.stage,
        "state": report.state,
        "result": taken.result,
    }
    if report.error:
        fields["reason"] = report.error.reason  # never the message: it can be exception text
    if taken.position:
        fields["current_attempt_id"] = taken.position.attempt_id
        fields["current_seq"] = taken.position.seq
    level = logging.INFO if taken.result in ("recorded", "repeated") else logging.WARNING
    log.log(level, "status report %s", taken.result, extra={"correlation": fields})
    return taken


def details(last_report: dict[str, Any] | None) -> dict[str, Any] | None:
    """The request's internal details (§5.5): where its current attempt last reported."""
    if last_report is None:
        return None
    return {k: last_report[k] for k in ("attempt_id", "seq", "stage", "progress")}
