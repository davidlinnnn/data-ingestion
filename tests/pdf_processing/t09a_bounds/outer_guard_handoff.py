"""Choose whether the outer guard must signal a running acceptance runner."""

import json
import signal


def handoff_on_guard(process, stop_record, runner_started_at):
    try:
        record = json.loads(stop_record.read_text())
    except (OSError, ValueError):
        record = {}
    if (type(record.get("time")) in (int, float)
            and record["time"] >= runner_started_at
            and isinstance(record.get("reason"), str) and record["reason"]
            and record.get("automatic_retry") is False):
        return "runner_cleanup"
    process.send_signal(signal.SIGINT)
    return "outer_signalled"
