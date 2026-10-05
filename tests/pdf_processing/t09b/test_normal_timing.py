import base64
import json
from pathlib import Path
import tempfile
import unittest

from normal_timing import summarize


class NormalTimingTest(unittest.TestCase):
    def test_ocr_queue_execution_and_retry_rejection(self):
        payload = base64.b64encode(json.dumps({'stage': 'component_ocr'}).encode()).decode()
        events = [
            {'eventId': '1', 'eventTime': '2026-09-30T00:00:00Z'},
            {'eventId': '2', 'eventTime': '2026-09-30T00:00:01Z',
             'activityTaskScheduledEventAttributes': {'input': {'payloads': [{'data': payload}]}}},
            {'eventId': '3', 'eventTime': '2026-09-30T00:00:03Z',
             'activityTaskStartedEventAttributes': {'scheduledEventId': '2', 'attempt': 1}},
            {'eventId': '4', 'eventTime': '2026-09-30T00:00:07Z',
             'activityTaskCompletedEventAttributes': {'scheduledEventId': '2'}},
            {'eventId': '5', 'eventTime': '2026-09-30T00:00:08Z',
             'eventType': 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED'},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.json'
            path.write_text(json.dumps({'events': events}))
            report = summarize(path)
            self.assertEqual(report['workflow_seconds'], 8)
            self.assertEqual(report['stages']['component_ocr'], {
                'activities': 1, 'queue_seconds_sum': 2, 'activity_seconds_sum': 4})
            events[2]['activityTaskStartedEventAttributes']['attempt'] = 2
            path.write_text(json.dumps({'events': events}))
            with self.assertRaisesRegex(ValueError, 'retries'):
                summarize(path)
