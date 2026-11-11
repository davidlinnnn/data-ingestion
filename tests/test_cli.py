import json
import logging
import re
import sys

from kp_canonicalization.cli import JsonFormatter, main
from kp_canonicalization.profile import latest_profile


def test_profile_prints_every_method_identity(capsys):
    assert main(["profile"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 8
    assert re.fullmatch(
        r"docling-parse@1  module_digest=[0-9a-f]{64}  components="
        r"docling-slim@2\.132\.0,layout-heron@8f39ad3c,tableformer-accurate@v1,rapidocr-ppocrv6-small",
        lines[0],
    )
    assert re.fullmatch(r"table-status@1  module_digest=[0-9a-f]{64}  components=", lines[5])


def test_profile_takes_a_path(capsys):
    assert main(["profile", str(latest_profile())]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 8


def test_a_bad_profile_exits_1_with_the_reason_on_stderr(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text(latest_profile().read_text().replace("code@1:", "code@9:"))

    assert main(["profile", str(bad)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "code" in captured.err


def test_the_summary_worker_needs_the_summary_url(monkeypatch, capsys):
    monkeypatch.delenv("KP_SUMMARY_BASE_URL", raising=False)

    assert main(["worker", "--queue", "summary"]) == 2
    assert "KP_SUMMARY_BASE_URL" in capsys.readouterr().err


def test_the_d3_worker_needs_the_d3_url(monkeypatch, capsys):
    monkeypatch.delenv("KP_D3_BASE_URL", raising=False)

    assert main(["worker", "--queue", "d3"]) == 2
    assert "KP_D3_BASE_URL is required for the d3 worker" in capsys.readouterr().err


def test_the_orchestration_worker_needs_the_admission_url(monkeypatch, capsys):
    monkeypatch.delenv("KP_ADMISSION_URL", raising=False)

    assert main(["worker", "--queue", "orchestration"]) == 2
    assert "KP_ADMISSION_URL" in capsys.readouterr().err


def test_a_worker_listed_under_another_profile_versions_deployment_refuses_to_start(
    monkeypatch, capsys
):
    monkeypatch.setenv("KP_ADMISSION_URL", "http://admission.invalid")
    monkeypatch.setenv("TEMPORAL_DEPLOYMENT_NAME", "paper-pdf-2")

    assert main(["worker", "--queue", "orchestration"]) == 2
    assert "paper-pdf-2, but this worker loads paper-pdf@1" in capsys.readouterr().err


def test_a_start_input_without_an_adopted_version_exits_2(tmp_path, capsys):
    start = tmp_path / "start.json"
    start.write_text(json.dumps({"request_id": "req_1", "priority": "normal"}))

    assert main(["start-request", str(start)]) == 2
    assert "adopted_version" in capsys.readouterr().err


def test_the_promoter_refuses_deployment_values_without_a_profile(tmp_path, capsys, root_logging):
    values = tmp_path / "values.yaml"
    values.write_text("profiles: {}\n")

    assert main(["promote", str(values)]) == 2
    line = json.loads(capsys.readouterr().err)
    assert (line["level"], line["message"]) == ("ERROR", "no profiles in the deployment values")


def test_a_logged_exception_keeps_its_types_and_frames_and_drops_every_message():
    cell, answer = "Q3 revenue 4.2M", "the patient is ..."

    def parse():
        raise ValueError(f"cell text: {cell}")

    try:
        try:
            parse()
        except ValueError as cause:
            raise RuntimeError(f"model answered: {answer}") from cause
    except RuntimeError:
        record = logging.LogRecord(
            "temporalio.activity", logging.WARNING, __file__, 1, "Completing activity as failed",
            None, sys.exc_info(),
        )  # fmt: skip

    line = json.loads(JsonFormatter().format(record))

    assert re.fullmatch(
        r'RuntimeError\n  File ".*test_cli.py", line \d+, in test_a_logged_.*\n.*\n'
        r'caused by ValueError\n  File ".*test_cli.py", line \d+, in test_a_logged_.*\n.*\n'
        r'  File ".*test_cli.py", line \d+, in parse\n.*\n',
        line["exception"],
    )
    assert "revenue" not in json.dumps(line) and "patient" not in json.dumps(line)


def test_worker_logs_are_json_lines_that_carry_the_request_id():
    record = logging.LogRecord(
        "temporalio.activity", logging.WARNING, __file__, 1, "%s: refused", ("PASSWORD_REQUIRED",),
        None,
    )  # fmt: skip
    record.created = 1793620800.25  # 2026-11-02T12:00:00.250Z
    record.temporal_activity = {
        "workflow_id": "req_1", "workflow_run_id": "run_1", "activity_type": "prepare",
    }  # fmt: skip

    assert json.loads(JsonFormatter().format(record)) == {
        "time": "2026-11-02T12:00:00.250Z",
        "level": "WARNING",
        "logger": "temporalio.activity",
        "message": "PASSWORD_REQUIRED: refused",
        "request_id": "req_1",
        "attempt_id": "run_1",
        "activity": "prepare",
    }


def test_a_log_line_outside_an_activity_has_no_correlation_fields():
    record = logging.LogRecord(
        "kp_canonicalization", logging.INFO, __file__, 1, "worker up", None, None
    )

    assert set(json.loads(JsonFormatter().format(record))) == {"time", "level", "logger", "message"}


def test_workflow_logs_carry_the_request_id_and_extra_correlation_ids():
    record = logging.LogRecord("temporalio.workflow", logging.INFO, __file__, 1, "x", None, None)
    record.temporal_workflow = {"workflow_id": "req_1", "run_id": "run_1"}
    record.correlation = {"document_uid": "doc_1", "trace_id": "4bf92f3577b34da6"}

    line = json.loads(JsonFormatter().format(record))

    assert {k: line[k] for k in ("request_id", "attempt_id", "document_uid", "trace_id")} == {
        "request_id": "req_1", "attempt_id": "run_1",
        "document_uid": "doc_1", "trace_id": "4bf92f3577b34da6",
    }  # fmt: skip
