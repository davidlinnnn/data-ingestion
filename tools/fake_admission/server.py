"""Stand-in for the admission status-report receiver (#97 not built yet), for runs outside
the Codex sandbox. Kept in the repo as a reference for #97. The HTTP wrapping is the
provisional one HttpStatusReporter sends:

    POST /v1/requests/{request_id}/status-reports   store a report
    GET  /v1/requests/{request_id}/status-reports   every stored report, in arrival order

Per (request_id, attempt_id) a report's seq must exceed the last stored one (gaps are
fine). A repeat of the last report is accepted again; anything else out of order gets
409 with the current position {"attempt_id", "seq"}. Ordering across attempts is not
modelled: run IDs are not orderable, and the rule is an open question for #97.

    python -m tools.fake_admission.server [--port 8081] [--log reports.jsonl]
"""

import argparse
import json
import re
import threading
from dataclasses import fields
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from kp_processing.ports.status_reporter import StatusReport

FIELDS = {field.name for field in fields(StatusReport)}
PATH = re.compile(r"^/v1/requests/([^/]+)/status-reports$")


class Receiver:
    def __init__(self, log_path: str | None = None) -> None:
        self.reports: dict[str, list[dict[str, Any]]] = {}
        self.last: dict[tuple[str, str], dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.log_path = log_path

    def accept(self, request_id: str, report: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if set(report) != FIELDS or report["request_id"] != request_id:
            return 400, {"error": "report fields or request_id do not match"}
        key = (request_id, report["attempt_id"])
        with self.lock:
            last = self.last.get(key)
            if last == report:
                return 200, {"duplicate": True}
            if last and report["seq"] <= last["seq"]:
                return 409, {"attempt_id": report["attempt_id"], "seq": last["seq"]}
            self.last[key] = report
            self.reports.setdefault(request_id, []).append(report)
            if self.log_path:
                with open(self.log_path, "a") as f:
                    f.write(json.dumps(report) + "\n")
        return 202, {}


def make_server(port: int = 0, log_path: str | None = None) -> ThreadingHTTPServer:
    """A server bound to 127.0.0.1 (port 0 picks a free one); `.receiver` holds the state."""
    receiver = Receiver(log_path)

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status: int, body: Any) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:
            m = PATH.match(self.path)
            if not m:
                return self.reply(404, {"error": "not found"})
            try:
                report = json.loads(self.rfile.read(int(self.headers["Content-Length"] or 0)))
            except (ValueError, TypeError):
                return self.reply(400, {"error": "body is not JSON"})
            if not isinstance(report, dict):
                return self.reply(400, {"error": "body is not a JSON object"})
            self.reply(*receiver.accept(m.group(1), report))

        def do_GET(self) -> None:
            m = PATH.match(self.path)
            if not m:
                return self.reply(404, {"error": "not found"})
            with receiver.lock:
                self.reply(200, list(receiver.reports.get(m.group(1), [])))

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.receiver = receiver  # type: ignore[attr-defined]
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stand-in admission status-report receiver")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--log", help="append every stored report to this JSONL file")
    args = parser.parse_args()
    server = make_server(args.port, args.log)
    print(f"fake_admission listening on http://127.0.0.1:{server.server_address[1]}")
    server.serve_forever()
