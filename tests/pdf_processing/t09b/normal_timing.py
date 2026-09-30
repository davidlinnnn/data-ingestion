"""Summarize successful normal-path Temporal timings, including required OCR."""
import base64
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path


def seconds(event):
    return datetime.fromisoformat(event['eventTime'].replace('Z', '+00:00')).timestamp()


def summarize(path):
    events = json.loads(path.read_text())['events']
    if events[-1]['eventType'] != 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED':
        raise ValueError('completed normal-path history required')
    scheduled, started, stages, attempts = {}, {}, defaultdict(list), []
    for event in events:
        attrs = event.get('activityTaskScheduledEventAttributes')
        if attrs:
            payload = json.loads(base64.b64decode(attrs['input']['payloads'][0]['data']))
            stage = payload.get('operation', {}).get('kind', payload['stage'])
            scheduled[str(event['eventId'])] = (stage, seconds(event))
        attrs = event.get('activityTaskStartedEventAttributes')
        if attrs:
            key = str(attrs['scheduledEventId'])
            if key in started or attrs.get('attempt', 1) != 1:
                raise ValueError('normal-path summary does not accept retries')
            started[key] = seconds(event)
        if any(key in event for key in ('activityTaskFailedEventAttributes',
                                       'activityTaskTimedOutEventAttributes')):
            raise ValueError('normal-path summary does not accept failed attempts')
        attrs = event.get('activityTaskCompletedEventAttributes')
        if attrs:
            key = str(attrs['scheduledEventId'])
            stage, admitted = scheduled[key]
            row = {'stage': stage, 'scheduled_event_id': key,
                   'queue_seconds': started[key] - admitted,
                   'activity_seconds': seconds(event) - started[key]}
            if min(row['queue_seconds'], row['activity_seconds']) < 0:
                raise ValueError('nonmonotonic activity history')
            stages[stage].append(row)
            attempts.append(row)
    if len(attempts) != len(scheduled):
        raise ValueError('incomplete activity history')
    return {'history': str(path),
            'workflow_seconds': seconds(events[-1]) - seconds(events[0]),
            'stages': {stage: {'activities': len(rows),
                              'queue_seconds_sum': sum(r['queue_seconds'] for r in rows),
                              'activity_seconds_sum': sum(r['activity_seconds'] for r in rows)}
                       for stage, rows in sorted(stages.items())},
            'attempts': attempts,
            'scope': 'Temporal wall times; activity times include storage/publication; sums are not workflow wall time'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    rows = [summarize(path) for path in sorted(args.state.glob('warm-*/history.json'))]
    if len(rows) != 5:
        parser.error('five mixed-sequence histories required')
    args.out.write_text(json.dumps(rows, indent=2) + '\n')
