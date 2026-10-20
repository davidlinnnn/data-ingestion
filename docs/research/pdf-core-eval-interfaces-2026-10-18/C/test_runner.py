"""Injected HTTP controls only; real source gate remains blocked and no credentials read."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx
import runner as r


class RunnerControls(unittest.TestCase):
    def setUp(self):
        self.manifest = r.p.read(r.HERE / "requests.json")
        self.snapshots = {str(path):r.p.sha(path) for path in [r.HERE/"requests.json",r.HERE/"producer.py",
            *r.HERE.glob("bundles/*/document.md")]}

    def tearDown(self):
        self.assertEqual({name:r.p.sha(name) for name in self.snapshots},self.snapshots)

    def run_injected(self, alter=None, change=None, raw=None):
        manifest = deepcopy(self.manifest); manifest["jobs"] = manifest["jobs"][:2]
        manifest["calls_candidate"] = 2
        manifest["input_tokens_reserve_total"] = sum(j["input_tokens_reserve"] for j in manifest["jobs"])
        manifest["completion_tokens_cap_total"] = sum(j["output_tokens_cap"] for j in manifest["jobs"])
        if change: change(manifest)
        calls = []
        def handler(request):
            job = manifest["jobs"][len(calls)]; calls.append(job["job_id"])
            payload = {"image_kind":"control","description":"schema control only","visible_text":[],
                "components":[],"relations":[],"ordered_steps":[],"uncertainties":[]}
            if job["task"] == "chart_assessment": payload={"chart_type":"not_chart","unit":None,"data":[],"uncertainties":[]}
            response = {"id":"mock-id","model":job["body_without_image"]["model"],"system_fingerprint":"mock-fingerprint",
                "usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2},
                "choices":[{"finish_reason":"stop","message":{"content":json.dumps(payload)}}]}
            if alter: alter(response,job)
            return httpx.Response(200,content=raw if raw is not None else json.dumps(response).encode())
        temp = tempfile.TemporaryDirectory(prefix="C-runner-"); self.addCleanup(temp.cleanup)
        directory = Path(temp.name)/"run"
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = r.execute(manifest,client,"TEST_ONLY_NO_NETWORK",directory)
        return result,calls,directory,manifest

    def test_current_gate_refuses_before_credential_client_or_run_creation(self):
        original=r.os.environ.get
        def guard(name,*args):
            if name=="OPENAI_API_KEY": raise AssertionError("credential read")
            return original(name,*args)
        with patch.object(sys,"argv",["runner","--live"]), patch.object(r.os.environ,"get",side_effect=guard), \
             patch.object(r.httpx,"Client",side_effect=AssertionError("network client opened")):
            with self.assertRaisesRegex(r.Stop,"source_coverage_blocked"): r.main()

    def test_independent_contract_gate_and_frozen_dry_run(self):
        original=r.p.read
        def reader(path):
            if Path(path).name=="source-coverage.json": return {"full_C_coverage_gate":"pass"}
            return original(path)
        with patch.object(r.p,"read",side_effect=reader):
            with self.assertRaisesRegex(r.Stop,"source_contracts_not_ready"): r.source_gate(self.manifest)
        self.assertEqual(len(r.verify(self.manifest)["jobs"]),58)

    def test_valid_receipts_have_trusted_key_provider_and_immutable_source(self):
        result,calls,directory,manifest=self.run_injected()
        self.assertEqual(len(calls),2); self.assertIsNone(result["stopped"])
        for job in manifest["jobs"]:
            receipt=r.p.read(directory/"receipts"/job["binding"]["image_key"]/(job["task"]+".json"))
            self.assertEqual(receipt["input"],job["binding"])
            self.assertEqual(receipt["request_sha256"],job["request_sha256"])
            self.assertEqual(receipt["provider_id"],"mock-id")
            self.assertFalse(receipt["semantic_acceptance"])
            raw=r.loads((directory/job["job_id"]/"response.raw").read_bytes())
            self.assertEqual(raw["system_fingerprint"],"mock-fingerprint")

    def test_refusal_finish_truncation_and_invalid_payload_are_rejected(self):
        for kind in ("refusal","length","invalid","wrong_model"):
            def alter(response,job):
                if kind=="refusal": response["choices"][0]["message"]["refusal"]="mock refusal"
                elif kind=="length": response["choices"][0]["finish_reason"]="length"
                elif kind=="wrong_model": response["model"]="foreign"
                else: response["choices"][0]["message"]["content"]="{}"
            result,calls,directory,_=self.run_injected(alter)
            self.assertEqual(len(calls),2)
            self.assertTrue(all(record["status"]=="rejected" for record in result["records"]))
            self.assertFalse((directory/"receipts").exists())

    def test_truncated_oversize_invalid_encoding_json_and_missing_usage_stop(self):
        for raw in (b"{",b"\xff",b"[]",b'{"choices":[]}',b'{"usage":{},"usage":{}}'):
            result,calls,directory,_=self.run_injected(raw=raw)
            self.assertEqual(len(calls),1); self.assertIsNotNone(result["stopped"])
            self.assertTrue((directory/calls[0]/"response.raw").exists())
        result,calls,directory,_=self.run_injected(change=lambda m:[j.update(transport_bytes_max=10) for j in m["jobs"]])
        self.assertEqual(len(calls),1); self.assertEqual(result["stopped"],"transport_bytes_exceeded")
        self.assertLessEqual((directory/calls[0]/"response.raw").stat().st_size,10)

    def test_actual_overrun_reserve_content_limit_and_total_guard(self):
        def overrun(response,job): response["usage"]={"prompt_tokens":job["input_tokens_reserve"]+1,"completion_tokens":1,"total_tokens":job["input_tokens_reserve"]+2}
        result,calls,_,_=self.run_injected(overrun)
        self.assertEqual(len(calls),1); self.assertEqual(result["stopped"],"actual_usage_overrun")
        result,calls,_,_=self.run_injected(change=lambda m:m.update(input_tokens_reserve_total=0))
        self.assertFalse(calls); self.assertEqual(result["stopped"],"pre_request_budget")
        result,calls,_,_=self.run_injected(change=lambda m:[j.update(content_bytes_max=1) for j in m["jobs"]])
        self.assertEqual(len(calls),2); self.assertTrue(all(v["status"]=="rejected" for v in result["records"]))
        result,calls,_,_=self.run_injected(change=lambda m:m.update(remote_live_seconds_cap=0))
        self.assertFalse(calls); self.assertEqual(result["stopped"],"time_or_memory_guard")

    def test_stale_crop_request_and_template_prevent_send(self):
        for change in (lambda m:m["jobs"][0]["binding"].update(crop_sha256="stale"),
                       lambda m:m["jobs"][0].update(request_sha256="stale"),
                       lambda m:m["jobs"][0]["body_without_image"].update(model="foreign")):
            result,calls,_,_=self.run_injected(change=change)
            self.assertFalse(calls); self.assertIsNotNone(result["stopped"])
        with patch.object(r.p,"materialize",return_value=b"x"*(8*2**20+1)):
            result,calls,_,_=self.run_injected()
            self.assertFalse(calls); self.assertEqual(result["stopped"],"stale_request_or_crop")
        result,calls,_,_=self.run_injected(change=lambda m:m.update(completion_tokens_cap_total=0))
        self.assertFalse(calls); self.assertEqual(result["stopped"],"pre_request_budget")
        result,calls,_,_=self.run_injected(change=lambda m:m.update(rss_max_bytes=0))
        self.assertFalse(calls); self.assertEqual(result["stopped"],"time_or_memory_guard")

    def test_actual_wall_timeout_and_http_timeout_stop_later_jobs(self):
        def wait(response,job): time.sleep(.35)
        result,calls,_,_=self.run_injected(wait,lambda m:[j.update(max_seconds=.001) for j in m["jobs"]])
        self.assertEqual(len(calls),1); self.assertEqual(result["stopped"],"transport_or_timeout_usage_unknown")

    def test_malformed_choice_and_credential_echo_cannot_be_accepted_or_persisted(self):
        for choice in (None,1):
            result,calls,_,_=self.run_injected(lambda response,job:response.update(choices=[choice]))
            self.assertEqual(len(calls),1); self.assertEqual(result["stopped"],"invalid_choice_envelope")
        def echo(response,job):
            value=json.loads(response["choices"][0]["message"]["content"])
            value["echo"]="TEST_ONLY_NO_NETWORK"
            response["choices"][0]["message"]["content"]=json.dumps(value)
            response["id"]="TEST_ONLY_NO_NETWORK"
        result,calls,directory,_=self.run_injected(echo)
        self.assertEqual(len(calls),2)
        for path in directory.rglob("*"):
            if path.is_file(): self.assertNotIn(b"TEST_ONLY_NO_NETWORK",path.read_bytes())
        def timeout(response,job): raise httpx.ReadTimeout("mock timeout")
        result,calls,_,_=self.run_injected(timeout)
        self.assertEqual(len(calls),1); self.assertEqual(result["stopped"],"transport_or_timeout_usage_unknown")


if __name__=="__main__": unittest.main()
