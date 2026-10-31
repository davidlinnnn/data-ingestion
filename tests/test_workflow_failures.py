from temporalio.exceptions import ActivityError

from kp_processing.workflow import _failure_details


def test_unclassified_activity_failure_keeps_retryable_details():
    error = ActivityError(
        "Activity failed",
        scheduled_event_id=1,
        started_event_id=2,
        identity="worker",
        activity_type="parse_group",
        activity_id="3",
        retry_state=None,
    )
    error.__cause__ = RuntimeError("bug")

    assert _failure_details(error) == {
        "cause": "platform",
        "category": "platform",
        "reason": "PLATFORM_ERROR",
        "message": "bug",
        "retryable": True,
        "metadata": {"activity": "parse_group"},
    }
