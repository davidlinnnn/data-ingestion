from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import protocol as p
import runner

JOBS = p.read(p.R1 / "planning/jobs.json")["jobs"]


class Controls(unittest.TestCase):
    def run_control(self, transport, jobs=None, **kwargs):
        with tempfile.TemporaryDirectory(dir=p.HERE) as directory:
            path = Path(directory)/"run"
            with patch.object(runner, "deliver"):
                result = runner.run(jobs or JOBS[:2], path, transport, mock_only=True, **kwargs)
            receipts = p.read(path/"final-ledger.json")
            return result, receipts

    def faulty(self, mutate):
        def transport(job, body, timeout):
            value = runner.mock_transport(job, body, timeout)
            mutate(value)
            return value
        result, receipts = self.run_control(transport)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["not_run"], 1)
        self.assertEqual([r["attempts"] for r in receipts], [1, 0])
        return result

    def test_materialization_binds_all_43_and_has_json_instruction(self):
        for job in JOBS:
            body = p.materialize(job)
            self.assertEqual(body["model"], p.MODEL)
            self.assertEqual(body["reasoning_effort"], "low")
            self.assertEqual(body["max_completion_tokens"], job["per_job_completion_cap_proposal"])
            self.assertIn("JSON", body["messages"][0]["content"])
            self.assertNotIn("temperature", body)
            self.assertEqual(sum(c["type"] == "image_url" for c in body["messages"][1]["content"]),len(job["image_assets"]))

    def test_all_43_schemas_without_transport(self):
        for job in JOBS:
            p.validate_payload(job, p.mock_payload(job))

    def test_foreign_job_group_and_context_reject(self):
        for key in ("job_id", "group_sha256", "context_key"):
            value = p.mock_payload(JOBS[0]); value[key] = "foreign"
            with self.assertRaises(ValueError):
                p.validate_payload(JOBS[0], value)

    def test_missing_image_and_wrong_lane_reject(self):
        job = JOBS[15]; value = p.mock_payload(job)
        value["payload"]["images"].pop(next(iter(value["payload"]["images"])))
        with self.assertRaises(ValueError): p.validate_payload(job, value)
        value = p.mock_payload(job)
        first = next(iter(value["payload"]["images"].values()))
        first["context_ocr"]["scope"] = "crop"
        with self.assertRaises(ValueError): p.validate_payload(job, value)

    def test_incomplete_is_not_a_success(self):
        value = p.mock_payload(JOBS[0]); value.update(status="incomplete",incomplete_reason="unreadable",payload=None)
        with self.assertRaises(ValueError): p.validate_payload(JOBS[0],value)

    def test_source_boolean_page_and_nonstring_segment_reject(self):
        for pages, text in (([True],"literal"),([1],42)):
            payload={"group_sha256":"x","keep":[],"actions":[{"id":"a","consume":[],
                "evidence_refs":["@page/1"],"source_pages":pages,
                "placement":{"reference":"#/body","side":"after"},
                "blocks":[{"kind":"code","segments":[{"kind":"code","text":text}]}]}]}
            with self.assertRaises(ValueError): p.validate_source_types(payload)

    def test_blank_description_reject(self):
        value=p.mock_payload(JOBS[15])
        next(iter(value["payload"]["images"].values()))["description"]["description"]=" "
        with self.assertRaises(ValueError): p.validate_payload(JOBS[15],value)

    def test_delivery_failure_is_recorded(self):
        with tempfile.TemporaryDirectory(dir=p.HERE) as directory:
            with patch.object(runner,"deliver",side_effect=ValueError("MOCK assembly failure")):
                result=runner.run(JOBS[:1],Path(directory)/"run",runner.mock_transport,mock_only=True)
        self.assertIn("DELIVERY_FAILED",result["stop"])

    def test_partial_delivery_is_not_published(self):
        with tempfile.TemporaryDirectory(dir=p.HERE) as directory:
            destination=Path(directory)/"run"
            with patch.object(p.m,"supplement",side_effect=ValueError("MOCK C assembly failure")):
                result=runner.run([JOBS[3],JOBS[15],JOBS[16]],destination,runner.mock_transport,mock_only=True)
            self.assertIn("DELIVERY_FAILED",result["stop"])
            self.assertFalse((destination/"delivery").exists())
            self.assertEqual(len(list((destination/"delivery-pending").glob("*.source.json"))),1)

    def test_wrong_provider_model_stops(self):
        self.faulty(lambda r:r.update(model="other"))

    def test_truncation_stops(self):
        self.faulty(lambda r:r["choices"][0].update(finish_reason="length"))

    def test_refusal_stops(self):
        self.faulty(lambda r:r["choices"][0]["message"].update(refusal="refused"))

    def test_bad_json_stops(self):
        self.faulty(lambda r:r["choices"][0]["message"].update(content="{"))

    def test_completion_cap_stops(self):
        def mutate(r):
            r["usage"].update(completion_tokens=20000,total_tokens=20001)
        self.faulty(mutate)

    def test_input_reservation_stops(self):
        def transport(job,body,timeout):
            r=runner.mock_transport(job,body,timeout);r["usage"].update(prompt_tokens=3,total_tokens=4);return r
        result,_=self.run_control(transport,reservations={j["job_id"]:2 for j in JOBS[:2]})
        self.assertEqual(result["failed"],1)

    def test_response_size_stops(self):
        self.faulty(lambda r:r["choices"][0]["message"].update(content="x"*1048577))

    def test_transport_error_no_retry(self):
        def transport(*args): raise ConnectionError("MOCK network failure")
        result,receipts=self.run_control(transport)
        self.assertEqual(result["failed"],1)
        self.assertEqual(receipts[1]["attempts"],0)

    def test_hard_request_timeout(self):
        def transport(*args): time.sleep(.1)
        result,_=self.run_control(transport,request_seconds=.01)
        self.assertIn("TimeoutError",result["stop"])

    def test_batch_deadline_stops_before_second_request(self):
        def transport(job,body,timeout):
            time.sleep(.02);return runner.mock_transport(job,body,timeout)
        result,receipts=self.run_control(transport,batch_seconds=.01)
        self.assertIn("TimeoutError",result["stop"])
        self.assertEqual(receipts[1]["attempts"],0)

    def test_duplicate_excess_and_live_gate(self):
        for jobs in ([JOBS[0],JOBS[0]],JOBS+[JOBS[0]]):
            with self.assertRaises(ValueError): runner.run(jobs,p.HERE/"unused",runner.mock_transport,mock_only=True)
        with self.assertRaises(RuntimeError): runner.run(JOBS,p.HERE/"unused",runner.mock_transport,mock_only=False)

    def test_positive_receipts_and_no_parallel_dispatch(self):
        order=[]
        def transport(job,body,timeout):
            order.append(job["job_id"]);return runner.mock_transport(job,body,timeout)
        result,receipts=self.run_control(transport)
        self.assertEqual(result["validated"],2)
        self.assertEqual(order,[j["job_id"] for j in JOBS[:2]])
        self.assertTrue(all(r["attempts"]==1 for r in receipts))

    def test_HTTP_seam_exact_body_with_offline_httpx_transport(self):
        import httpx
        seen=[]
        def handler(request):
            seen.append(request)
            return httpx.Response(200,json=runner.mock_transport(JOBS[0],{},180))
        body=p.materialize(JOBS[0])
        with patch.dict(os.environ,{"OPENAI_API_KEY":"MOCK_TOKEN_NOT_REAL"}):
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                response=runner.http_transport(JOBS[0],body,180,client=client)
        self.assertEqual(len(seen),1)
        self.assertEqual(str(seen[0].url),p.ENDPOINT)
        self.assertEqual(seen[0].content,p.encoded(body))
        self.assertEqual(response["model"],p.MODEL)

    def test_HTTP_failure_does_not_follow_redirect_or_retry(self):
        import httpx
        for status in (302,429,500):
            seen=[]
            def handler(request):
                seen.append(request);return httpx.Response(status,headers={"Location":"https://example.invalid"})
            with patch.dict(os.environ,{"OPENAI_API_KEY":"MOCK_TOKEN_NOT_REAL"}):
                with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                    with self.assertRaises(RuntimeError): runner.http_transport(JOBS[0],{},180,client=client)
            self.assertEqual(len(seen),1)

    def test_HTTP_stream_response_ceiling(self):
        import httpx
        with patch.dict(os.environ,{"OPENAI_API_KEY":"MOCK_TOKEN_NOT_REAL"}):
            with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=b"x"*1048577))) as client:
                with self.assertRaises(ValueError): runner.http_transport(JOBS[0],{},180,client=client)


if __name__ == "__main__": unittest.main()
