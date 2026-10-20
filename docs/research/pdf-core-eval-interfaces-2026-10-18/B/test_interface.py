"""Actual new schema/parser/Core bridge and injected-transport controls; no network."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import httpx
from docling_core.types.doc import DoclingDocument, RefItem
import protocol as p
import runner as r

spec = importlib.util.spec_from_file_location("B_semantic_control_fixture",
    r.RESEARCH / "pdf-core-bc-closure-2026-10-17/B/test_method.py")
fixtures = importlib.util.module_from_spec(spec)
# The earlier test module imports its local method; isolate that import name.
import sys
previous = sys.modules.get("method"); sys.modules["method"] = p.method
try: spec.loader.exec_module(fixtures)
finally:
    if previous is None: sys.modules.pop("method", None)
    else: sys.modules["method"] = previous


def payload(key):
    return {"targets": [{"target_key": key, "caption": "", "conditions": [],
        "diagnostics": [], "panels": [fixtures.fixture()]}]}


class InterfaceControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = r.plan()

    def test_seven_sources_requests_schema_and_no_source_answers(self):
        self.assertEqual(len(self.plan["jobs"]), 7)
        self.assertEqual(len(self.plan["pages"]), 5)
        self.assertEqual(self.plan["calls_max"], 7)
        self.assertEqual(self.plan["retries"], 0)
        self.assertFalse(self.plan["semantic_acceptance"])
        for job in self.plan["jobs"]:
            self.assertEqual(r.sha(job["image"]), job["image_sha256"])
            body = p.loads(r.body(job))
            self.assertEqual(body["model"], self.plan["model"])
            text = body["messages"][0]["content"][0]["text"]
            self.assertIn("untrusted source data", text)
            self.assertNotIn("E017", text)
            self.assertNotIn("expected_rows", text)
            self.assertIn(job["target_key"], text)

    def test_actual_schema_parser_method_core_markdown_reload_and_captions(self):
        baseline, keys, _, _ = fixtures.gate.fixture()
        before = baseline.model_dump_json()
        value = {"targets": [payload(key)["targets"][0] for key in keys]}
        parsed = p.parse(p.loads(json.dumps(value)), keys)
        self.assertEqual(parsed.model_dump(mode="json"), value)
        out, bindings = p.map_response(baseline, value, 1, keys)
        markdown = p.adapter.export_markdown(out, bindings)
        rendered, _ = fixtures.gate.rendered_tables(markdown)
        self.assertEqual(rendered[0][1][-2:], ["001.20 / 0", ""])
        self.assertEqual(rendered[0][2][-1], r"\frac{a+b}{c} | <s> & x_y")
        self.assertEqual(baseline.model_dump_json(), before)
        self.assertEqual(markdown.count("Synthetic source caption 1"), 1)
        for binding in bindings:
            self.assertTrue(binding["caption_ownership"]["native_link_preserved"])
            self.assertFalse(binding["caption_ownership"]["source_completeness_verified"])
            self.assertEqual(binding["semantic_panels"][0]["cell_identities"][0]["text"], "001.20 / 0")
        loaded = DoclingDocument.model_validate_json(out.model_dump_json())
        self.assertEqual(p.adapter.export_markdown(loaded, json.loads(json.dumps(bindings))), markdown)

    def test_strict_nested_unknown_missing_duplicate_and_foreign_targets(self):
        key = "p1:#/tables/0"
        changes = [lambda v: v.update(extra=True), lambda v: v["targets"][0].pop("conditions"),
            lambda v: v["targets"].append(deepcopy(v["targets"][0])),
            lambda v: v["targets"][0].update(target_key="foreign"),
            lambda v: v["targets"][0]["panels"][0]["rows"][0]["cells"][0].update(text=1.2),
            lambda v: v["targets"][0]["panels"][0]["rows"][0]["cells"][0].update(text={"unknown": True}),
            lambda v: v["targets"][0]["panels"][0]["columns"][0]["path"][0].update(extra="x"),
            lambda v: v["targets"][0]["panels"][0]["rows"][0]["cells"].pop()]
        for change in changes:
            value = payload(key); change(value); before = deepcopy(value)
            with self.assertRaises(ValueError): p.parse(value, [key])
            self.assertEqual(value, before)
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            p.loads('{"targets":[],"targets":[]}')

    def test_missing_collateral_cannot_map_even_with_matching_parse_keys(self):
        baseline, keys, _, _ = fixtures.gate.fixture()
        p.parse(payload(keys[0]), keys[:1])
        with self.assertRaisesRegex(ValueError, "complete page"):
            p.map_response(baseline, payload(keys[0]), 1, keys[:1])

    def test_finite_source_independent_output_stress(self):
        panel = {"panel_label": "", "title": "", "dimension_names": ["F", "V", "M"],
            "columns": [{"key": f"c{c}", "path": [{"id": f"h{c}", "text": f"Metric {c}"}]} for c in range(10)],
            "rows": [{"key": f"r{i}", "dimensions": {"F": "Family", "V": "Variant", "M": "Method"},
                "group": None, "cells": [{"id": f"r{i}c{c}", "column": f"c{c}", "text": "001.20"} for c in range(10)]}
                for i in range(40)], "groups": []}
        value = payload("synthetic"); value["targets"][0]["panels"] = [panel]
        p.parse(value, ["synthetic"])
        compact = len(r.encoded(value))
        self.assertLessEqual(compact + 8192, 32768)
        self.assertLessEqual(len(json.dumps(value, indent=2).encode()), self.plan["content_bytes"])

    def execute(self, change=None, plan_change=None, transport_change=None):
        plan = deepcopy(self.plan)
        if plan_change: plan_change(plan)
        counter = []; transport = r.legacy(plan)
        if transport_change: transport_change(transport)
        snapshots = {j["baseline"]: r.sha(j["baseline"]) for j in plan["jobs"]}
        def reply(request):
            job = plan["jobs"][len(counter)]; counter.append(job["name"])
            content = json.dumps(payload(job["target_key"]))
            envelope = {"id": "mock-response", "system_fingerprint": "mock-fingerprint", "model": "mock-only",
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                "choices": [{"finish_reason": "stop", "message": {"content": content}}]}
            if change: change(envelope, len(counter)-1)
            return httpx.Response(200, json=envelope)
        directory = Path(tempfile.mkdtemp(prefix="B-interface-", dir=HERE))
        destination = directory / "run"
        try:
            with httpx.Client(transport=httpx.MockTransport(reply)) as client:
                result = transport.execute(plan, client, "TEST_ONLY_NO_NETWORK", destination)
            pages = p.loads((destination / "page-assembly.json").read_text())
            execution = p.loads((destination / "execution.json").read_text())
            self.assertEqual({name: r.sha(name) for name in snapshots}, snapshots)
            return result, counter, pages, execution, destination
        finally:
            self.addCleanup(__import__("shutil").rmtree, directory)

    def test_injected_seven_job_execution_maps_all_actual_source_pages(self):
        result, calls, pages, execution, destination = self.execute()
        self.assertEqual(len(calls), 7)
        self.assertIsNone(result["stopped"])
        self.assertTrue(all(page["status"].startswith("mapped and reloaded") for page in pages))
        self.assertTrue(execution["all_registered_jobs_attempted"])
        self.assertEqual(p.loads((destination / "attempt.json").read_text())["calls_max"], 7)
        raw = p.loads((destination / calls[0] / "response.json").read_text())
        self.assertEqual(raw["id"], "mock-response")
        self.assertEqual(raw["system_fingerprint"], "mock-fingerprint")
        page = next(v for v in self.plan["pages"] if v["name"] == "skillopt-p8")
        baseline = DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
        out = DoclingDocument.model_validate_json((destination / "skillopt-p8/document.json").read_text())
        bindings = p.loads((destination / "skillopt-p8/bindings.json").read_text())
        self.assertEqual(len(bindings), 2)
        native = p.adapter.inventory(baseline, 8)
        for binding in bindings:
            original = native[binding["target_key"]]
            self.assertEqual([RefItem(cref=ref).resolve(out).text for ref in binding["captions"]],
                [ref.resolve(baseline).text for ref in original.captions])
            self.assertEqual(binding["caption_ownership"]["native_link_preserved"], bool(original.captions))
            table = RefItem(cref=binding["panels"][0]["table_ref"]).resolve(out)
            self.assertEqual(table.prov, original.prov)
            self.assertTrue(all(cell.bbox is None for cell in table.data.table_cells))

    def test_refusal_truncation_malformed_duplicate_and_unknown_block_whole_page(self):
        for kind in ("refusal", "truncation", "malformed", "duplicate", "unknown"):
            def change(response, index):
                if index != 1: return
                choice = response["choices"][0]
                if kind == "refusal": choice["message"]["refusal"] = "mock refusal"
                if kind == "truncation": choice["finish_reason"] = "length"
                if kind == "malformed": choice["message"]["content"] = "{"
                if kind == "duplicate": choice["message"]["content"] = '{"targets":[],"targets":[]}'
                if kind == "unknown":
                    value = p.loads(choice["message"]["content"])
                    value["targets"][0]["panels"][0]["rows"][0]["cells"][0]["text"] = {"unknown": True}
                    choice["message"]["content"] = json.dumps(value)
            result, calls, pages, _, destination = self.execute(change)
            self.assertEqual(len(calls), 7)
            self.assertEqual(result["records"][1]["result"], "target_rejected")
            page = next(page for page in pages if page["name"] == "skillopt-p8")
            self.assertTrue(page["status"].startswith("unaccepted"))
            self.assertFalse((destination / "skillopt-p8").exists())

    def test_actual_overbudget_stops_and_input_reserve_prevents_call(self):
        result, calls, _, _, _ = self.execute(lambda v, i: v["usage"].update(completion_tokens=32769))
        self.assertEqual(len(calls), 1); self.assertEqual(result["stopped"], "actual_usage_overrun")
        result, calls, _, _, _ = self.execute(plan_change=lambda v: v.update(total_input_budget=0))
        self.assertFalse(calls); self.assertEqual(result["stopped"], "pre_request_budget_stop")

    def test_transport_and_content_caps_and_memory_guard(self):
        result, calls, _, _, _ = self.execute(plan_change=lambda v: v.update(transport_bytes=10))
        self.assertEqual(len(calls), 1); self.assertEqual(result["stopped"], "transport_bytes_exceeded")
        result, calls, _, _, _ = self.execute(plan_change=lambda v: v.update(content_bytes=1))
        self.assertEqual(len(calls), 7)
        self.assertTrue(all(v["result"] == "target_rejected" for v in result["records"]))
        def no_memory(transport):
            def guard(started): raise transport.BudgetStop("time_or_memory_guard")
            transport.resource_guard = guard
        result, calls, _, _, _ = self.execute(transport_change=no_memory)
        self.assertFalse(calls); self.assertEqual(result["stopped"], "time_or_memory_guard")

    def test_transport_constants_cannot_drift(self):
        value = deepcopy(self.plan); value["request_seconds"] += 1
        with self.assertRaisesRegex(AssertionError, "constants"):
            r.legacy(value)

    def test_request_hash_change_and_timeout_stop_before_further_calls(self):
        job = deepcopy(self.plan["jobs"][0]); job["body_without_image"]["model"] = "changed"
        with self.assertRaisesRegex(ValueError, "hash"):
            r.body(job)
        def timeout(response, index): raise httpx.ReadTimeout("mock timeout")
        result, calls, _, _, _ = self.execute(timeout)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["stopped"], "transport_or_timeout_usage_unknown")

    def test_own_process_guard_is_real_and_wall_timer_remains_active(self):
        import time
        transport = r.legacy(self.plan)
        sample = transport.resource_guard(time.monotonic())
        self.assertGreater(sample["rss"], 0)
        self.assertIn("current process", sample["scope"])
        def short_deadline(module): module.REQUEST_SECONDS = .001
        result, calls, _, _, _ = self.execute(lambda response, index: time.sleep(.35), transport_change=short_deadline)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["stopped"], "transport_or_timeout_usage_unknown")

    def test_baseline_mutated_after_requests_is_refused_before_any_page_mapping(self):
        import shutil
        with tempfile.TemporaryDirectory(prefix="B-stale-", dir=HERE) as temp:
            path = Path(temp) / "baseline.json"
            shutil.copyfile(self.plan["pages"][0]["baseline"], path)
            def setup(plan): plan["pages"][0]["baseline"] = str(path)
            def mutate(response, index):
                if index == 6:
                    value = p.loads(path.read_text()); value["name"] = "changed after request"
                    path.write_text(json.dumps(value))
            result, calls, pages, _, _ = self.execute(mutate, setup)
            self.assertEqual(len(calls), 7)
            self.assertEqual(result["stopped"], "baseline_changed_before_assembly")
            self.assertTrue(all(page["status"].startswith("unaccepted") for page in pages))


HERE = r.HERE
if __name__ == "__main__": unittest.main()
