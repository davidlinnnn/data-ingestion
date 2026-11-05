import json
import logging
import re

from kp_processing.cli import JsonFormatter, main
from kp_processing.profile import PROFILES_DIR


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
    assert main(["profile", str(PROFILES_DIR / "paper-pdf@1.yaml")]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 8


def test_a_bad_profile_exits_1_with_the_reason_on_stderr(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text((PROFILES_DIR / "paper-pdf@1.yaml").read_text().replace("code@1:", "code@9:"))

    assert main(["profile", str(bad)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "code" in captured.err


def test_the_summary_worker_needs_the_summary_url(monkeypatch, capsys):
    monkeypatch.delenv("KP_SUMMARY_BASE_URL", raising=False)

    assert main(["worker", "--queue", "summary"]) == 2
    assert "KP_SUMMARY_BASE_URL" in capsys.readouterr().err


def test_the_orchestration_worker_needs_the_admission_url(monkeypatch, capsys):
    monkeypatch.delenv("KP_ADMISSION_URL", raising=False)

    assert main(["worker", "--queue", "orchestration"]) == 2
    assert "KP_ADMISSION_URL" in capsys.readouterr().err


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
    record = logging.LogRecord("kp_processing", logging.INFO, __file__, 1, "worker up", None, None)

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
