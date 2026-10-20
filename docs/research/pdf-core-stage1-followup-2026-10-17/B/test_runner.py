"""Mock HTTP controls; public cached baselines, no source answers or real requests."""
from copy import deepcopy
import json
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
import runner as r

RESOURCE_GUARD = r.resource_guard


def mock_payload(key):
    return dict(targets=[dict(target_key=key, caption="", conditions=[], diagnostics=[],
        panels=[dict(panel_label="", title="MOCK", data=dict(grid=[["Method", "Score"], ["MOCK", "001.20"]],
            spans=[], roles=[dict(row=0, col=0, kind="column"), dict(row=0, col=1, kind="column")], row_groups=[]))])])


class RunnerControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pdf-b-runner-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "run"
        original = json.loads((r.OLD / "next-stage-jobs.json").read_text())
        jobs = deepcopy(original["jobs"])
        for job in jobs:
            job.update(input_token_reservation=1000, completion_cap=r.COMPLETION_CAP,
                http_body_sha256="MOCK_REQUEST", body_without_image=dict(messages=[dict(content=[
                    dict(type="text", text="MOCK"), dict(type="image_url", image_url=dict(url="MOCK"))])]))
        self.reg = dict(jobs=jobs, pages=original["pages"], calls_max=6, total_input_budget=6000,
            total_completion_budget=6*r.COMPLETION_CAP, transport_bytes=r.TRANSPORT_LIMIT, content_bytes=r.CONTENT_LIMIT)
        self.calls = 0
        self.guard = patch.object(r, "resource_guard")
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def execute(self, change=lambda index, response: response):
        def handle(request):
            index = self.calls
            self.calls += 1
            job = self.reg["jobs"][index]
            response = dict(model=r.MODEL, usage=dict(prompt_tokens=100, completion_tokens=100),
                choices=[dict(finish_reason="stop", message=dict(content=json.dumps(mock_payload(job["target_key"]))))])
            response = change(index, response)
            if isinstance(response, Exception):
                raise response
            if isinstance(response, httpx.Response):
                return response
            return httpx.Response(200, json=response)
        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            return r.execute(self.reg, client, "MOCK_CREDENTIAL", self.directory)

    def test_all_six_atomic_mapping_and_replay_rejected(self):
        result = self.execute()
        self.assertEqual(self.calls, 6)
        self.assertIsNone(result["stopped"])
        pages = json.loads((self.directory / "page-assembly.json").read_text())
        self.assertEqual(len(pages), 4)
        self.assertTrue(all(p["status"].startswith("mapped and reloaded") for p in pages))
        self.assertTrue(all(p["mapping_seconds"] >= 0 and p["serialize_reload_save_seconds"] >= 0 for p in pages))
        self.assertTrue(all(p["http_response_seconds"] <= p["seconds"] for p in result["records"]))
        with self.assertRaises(FileExistsError):
            self.execute()
        self.assertEqual(self.calls, 6)

    def test_input_pre_request_budget(self):
        self.reg["total_input_budget"] = 999
        result = self.execute()
        self.assertEqual(self.calls, 0)
        self.assertEqual(result["stopped"], "pre_request_budget_stop")

    def test_reservation_boundary_and_completion_budget(self):
        ledger = dict(calls=0, input=5000, completion=0)
        r.reserve(self.reg, ledger, self.reg["jobs"][0])
        ledger["input"] += 1
        with self.assertRaises(r.BudgetStop):
            r.reserve(self.reg, ledger, self.reg["jobs"][0])
        ledger.update(input=0, completion=self.reg["total_completion_budget"])
        with self.assertRaises(r.BudgetStop):
            r.reserve(self.reg, ledger, self.reg["jobs"][0])

    def test_actual_input_overrun_stops_after_one(self):
        def overrun(i, value):
            value["usage"]["prompt_tokens"] = 1001
            return value
        result = self.execute(overrun)
        self.assertEqual((self.calls, result["stopped"]), (1, "actual_usage_overrun"))
        self.assertEqual(result["ledger"]["input"], 1001)

    def test_actual_completion_overrun_stops_after_one(self):
        def overrun(i, value):
            value["usage"]["completion_tokens"] = r.COMPLETION_CAP + 1
            return value
        self.assertEqual(self.execute(overrun)["stopped"], "actual_usage_overrun")
        self.assertEqual(self.calls, 1)

    def test_missing_usage_stops_after_one(self):
        def missing(i, value):
            value.pop("usage")
            return value
        self.assertEqual(self.execute(missing)["stopped"], "usage_unavailable_or_invalid")
        self.assertEqual(self.calls, 1)

    def test_invalid_usage_type(self):
        for usage in (None, {}, dict(prompt_tokens=True, completion_tokens=1),
                      dict(prompt_tokens=-1, completion_tokens=1)):
            with self.assertRaises(r.BudgetStop):
                r.charge(self.reg, dict(input=0, completion=0), self.reg["jobs"][0], usage)

    def test_invalid_usage_remains_unknown_in_saved_execution(self):
        def invalid(i, value):
            value["usage"]["prompt_tokens"] = True
            return value
        self.assertEqual(self.execute(invalid)["stopped"], "usage_unavailable_or_invalid")
        self.assertTrue(json.loads((self.directory / "execution.json").read_text())["unknown_usage"])

    def test_invalid_choice_stops_with_known_usage(self):
        def invalid(i, value):
            value["choices"][0]["message"] = None
            return value
        result = self.execute(invalid)
        self.assertEqual((self.calls, result["stopped"]), (1, "invalid_provider_choice_envelope"))
        self.assertEqual(result["ledger"]["input"], 100)
        self.assertFalse(json.loads((self.directory / "execution.json").read_text())["unknown_usage"])

    def test_invalid_encoding_stops_before_next_request(self):
        result = self.execute(lambda i, value: httpx.Response(200, content=b"\xff"))
        self.assertEqual((self.calls, result["stopped"]), (1, "invalid_provider_encoding_usage_unknown"))

    def test_failed_target_rejects_whole_page_but_continues_fixed_jobs(self):
        def failed(i, value):
            if i == 1:
                value["choices"][0]["message"]["content"] = '{"targets":[]}'
            return value
        result = self.execute(failed)
        self.assertEqual(self.calls, 6)
        self.assertIsNone(result["stopped"])
        pages = {p["name"]: p for p in json.loads((self.directory / "page-assembly.json").read_text())}
        self.assertTrue(pages["skillopt-p8"]["status"].startswith("unaccepted"))
        self.assertFalse((self.directory / "skillopt-p8" / "document.json").exists())
        self.assertTrue(pages["wikiskill-p13"]["status"].startswith("mapped"))

    def test_truncated_completion_continues_and_counts(self):
        def truncated(i, value):
            value["choices"][0]["finish_reason"] = "length"
            return value
        result = self.execute(truncated)
        self.assertEqual(self.calls, 6)
        self.assertTrue(all(p["result"] == "target_rejected" for p in result["records"]))
        self.assertEqual(result["ledger"]["completion"], 600)

    def test_transport_limit_stops_after_one(self):
        self.reg["transport_bytes"] = 32
        self.assertEqual(self.execute()["stopped"], "transport_bytes_exceeded")
        self.assertEqual(self.calls, 1)
        self.assertTrue((self.directory / self.reg["jobs"][0]["name"] / "response.partial.txt").exists())

    def test_timeout_stops_after_one(self):
        self.assertEqual(self.execute(lambda i, response: httpx.ReadTimeout("mock"))["stopped"],
                         "transport_or_timeout_usage_unknown")
        self.assertEqual(self.calls, 1)

    def test_partial_transport_response_survives_timeout(self):
        class Partial(httpx.SyncByteStream):
            def __iter__(self):
                yield b'{"partial":'
                raise httpx.ReadTimeout("mock partial")
        self.assertEqual(self.execute(lambda i, value: httpx.Response(200, stream=Partial()))["stopped"],
                         "transport_or_timeout_usage_unknown")
        prefix = self.directory / self.reg["jobs"][0]["name"] / "response.partial.txt"
        self.assertEqual(prefix.read_bytes(), b'{"partial":')

    def test_watchdog_covers_assembly_and_stops_cleanly(self):
        def stopped_assembly(*args):
            self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0], 0)
            raise r.BudgetStop("mock_resource_stop_during_assembly")
        with patch.object(r, "assemble", side_effect=stopped_assembly):
            result = self.execute()
        self.assertEqual(result["stopped"], "mock_resource_stop_during_assembly")
        self.assertEqual(self.calls, 6)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
        self.assertTrue(all(p["status"].startswith("unaccepted") for p in
            json.loads((self.directory / "page-assembly.json").read_text())))

    def test_watchdog_remains_active_during_http_wait(self):
        def resource_stop(i, response):
            with patch.object(r, "resource_guard", side_effect=r.BudgetStop("mock_http_resource_stop")):
                signal.raise_signal(signal.SIGALRM)
            return response
        self.assertEqual(self.execute(resource_stop)["stopped"], "mock_http_resource_stop")
        self.assertEqual(self.calls, 1)

    def test_request_deadline_signal_is_classified_as_timeout(self):
        def deadline(i, response):
            signal.raise_signal(signal.SIGALRM)
            return response
        with patch.object(r, "REQUEST_SECONDS", 0):
            result = self.execute(deadline)
        self.assertEqual((self.calls, result["stopped"]), (1, "transport_or_timeout_usage_unknown"))

    def test_resource_guard_counts_child_rss(self):
        child = SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=5*2**30))
        parent = SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=8*2**30), children=lambda recursive: [child])
        with patch.object(r.psutil, "Process", return_value=parent), patch.object(r.psutil, "virtual_memory",
            return_value=SimpleNamespace(available=20*2**30)):
            with self.assertRaises(r.BudgetStop):
                RESOURCE_GUARD(r.time.monotonic())

    def test_http_failure_stops_after_one(self):
        self.assertEqual(self.execute(lambda i, response: httpx.Response(429, json={}))["stopped"],
                         "http_error_usage_unknown")
        self.assertEqual(self.calls, 1)

    def test_credential_unavailable_does_not_mark_attempt(self):
        with httpx.Client(transport=httpx.MockTransport(lambda request: self.fail("must not send"))) as client:
            with self.assertRaises(ValueError):
                r.execute(self.reg, client, "", self.directory)
        self.assertFalse(self.directory.exists())

    def test_finite_preflight(self):
        self.assertTrue(r.preflight()["source_independent"])


if __name__ == "__main__":
    unittest.main()
