from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
import api


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.budget=dict(calls_max=8,input_reservation_per_job=10000,
            aggregate_input_reservation=80000,max_completion_tokens=8192,total_completion_tokens=65536,
            total_seconds=1800,per_request_seconds=180)
        self.ledger=dict(calls=0,input=0,completion=0)

    def test_call_input_and_completion_stop_before_request(self):
        for change in (dict(calls=8),dict(input=70001),dict(completion=57345)):
            with self.subTest(change=change),self.assertRaises(api.BudgetStop):
                api.reserve(self.budget,{**self.ledger,**change})

    def test_reasoning_is_not_counted_twice(self):
        api.charge(self.budget,self.ledger,dict(prompt_tokens=100,completion_tokens=200,
            completion_tokens_details=dict(reasoning_tokens=150)))
        self.assertEqual(self.ledger,dict(calls=0,input=100,completion=200))

    def test_unknown_negative_or_boolean_usage_stops(self):
        for usage in (None,{},dict(prompt_tokens=-1,completion_tokens=1),dict(prompt_tokens=True,completion_tokens=1)):
            with self.subTest(usage=usage),self.assertRaises(api.BudgetStop):
                api.charge(self.budget,self.ledger,usage)

    def test_actual_usage_overrun_is_charged_then_stops(self):
        with self.assertRaises(api.BudgetStop):
            api.charge(self.budget,self.ledger,dict(prompt_tokens=10001,completion_tokens=20))
        self.assertEqual(self.ledger['input'],10001)

    def test_truncation_refusal_and_duplicate_json_are_not_repaired(self):
        for choice in (dict(finish_reason="length",message=dict(content='{}')),
                       dict(finish_reason="stop",message=dict(content='{}',refusal='no')),
                       dict(finish_reason="stop",message=dict(content='{"x":1,"x":2}'))):
            with self.subTest(choice=choice),self.assertRaises(ValueError):
                api.parse_content(dict(choices=[choice]))

    def test_valid_content_is_not_transformed(self):
        value=dict(complete=True,issues=[],regions=[])
        self.assertEqual(api.parse_content(dict(choices=[dict(finish_reason='stop',
            message=dict(content=json.dumps(value)))])),value)

    def test_changed_freeze_refuses_without_resealing(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'input';path.write_text('original')
            hashes=dict(input=api.d.file_hash(path))
            path.write_text('changed')
            with self.assertRaises(ValueError):api.seal_check(hashes,Path(td))
            self.assertNotEqual(hashes['input'],api.d.file_hash(path))

    def test_http_error_consumes_one_attempt_and_stops_without_retry(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(401,json=dict(error='not recorded'))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'live-registration.json').write_text('{}')
            job=dict(id='synthetic')
            request=b'{}'
            live=dict(endpoint='https://example.invalid',requests=dict(synthetic=api.d.sha256(request).hexdigest()))
            reg=dict(budgets=self.budget,jobs=[job,job])
            with patch.object(api,'HERE',root),patch.object(api,'body',return_value=request), \
                    httpx.Client(transport=httpx.MockTransport(handler)) as client:
                out=api.execute(reg,live,'synthetic-memory-only',client,root/'run')
            self.assertEqual(len(calls),1)
            self.assertEqual(out['ledger']['calls'],1)
            self.assertEqual(out['stopped'],'http_error_usage_unknown')
            self.assertFalse((root/'run/synthetic/response.json').exists())
            self.assertNotIn('synthetic-memory-only',''.join(p.read_text() for p in (root/'run').rglob('*.json')))
            with self.assertRaises(FileExistsError):
                with patch.object(api,'HERE',root), httpx.Client(transport=httpx.MockTransport(handler)) as client:
                    api.execute(reg,live,'synthetic-memory-only',client,root/'run')


if __name__ == '__main__': unittest.main()
