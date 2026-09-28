"""Require successful measured SDK calls to have all server-side attempts.

Failed calls with unknown partial transfers remain incomplete. This does not
measure packets lost before reaching MinIO or transport framing overhead.
"""
from collections import defaultdict


def reconcile_ledgers(paths, server, bucket):
    from storage_ledger import reconcile as reconcile_ledger
    ledgers = [reconcile_ledger(path) for path in paths]
    report = reconcile([event for ledger in ledgers for event in ledger['events']],
                       server, bucket)
    for path, ledger in zip(paths, ledgers):
        if not ledger['complete']:
            report['errors'].append(f'{path}: incomplete storage ledger')
    report['complete'] = report['complete'] and not report['errors']
    return report


def reconcile(client, server, bucket):
    observers = {row['call_id'] for row in client if row['role'] == 'observer'}
    groups = defaultdict(list)
    for row in server:
        if row.get('call_id'):
            groups[row['call_id']].append(row)
    seen, errors = set(), []
    expected_methods = {'get_object': 'GET', 'put_object': 'PUT'}
    calls = [row for row in client if row['role'] == 'workload'
             and row['operation'] in expected_methods]
    for call in calls:
        call_id = call['call_id']
        if call_id in seen:
            errors.append('duplicate client call')
        seen.add(call_id)
        rows = groups[call_id]
        retries = call['sdk_retries']
        if type(retries) is not int or retries < 0 or len(rows) != retries + 1:
            errors.append(f'{call_id}: attempt coverage missing')
        if call['outcome'] not in ('call_succeeded', 'read_complete'):
            errors.append(f'{call_id}: client transfer incomplete')
        if any(row['method'] != expected_methods[call['operation']] or
               row['path'] != '/'+bucket+'/'+call['key'] for row in rows):
            errors.append(f'{call_id}: request identity mismatch')
        successful = [row for row in rows if 200 <= row['status'] < 300]
        if not successful:
            errors.append(f'{call_id}: server success missing')
        if call['operation'] == 'get_object' and successful and not any(
                row['server_tx_bytes'] == call['delivered_bytes'] for row in successful):
            errors.append(f'{call_id}: GET byte count mismatch')
    if observers & seen:
        errors.append('call identity shared by workload and observer')
    if set(groups) - seen - observers:
        errors.append('unmatched tagged server calls')
    return {'complete': bool(calls) and not errors, 'client_calls': len(calls),
            'server_attempts': sum(len(groups[key]) for key in seen),
            'server_rx_bytes': sum(row['server_rx_bytes'] for key in seen for row in groups[key]),
            'server_tx_bytes': sum(row['server_tx_bytes'] for key in seen for row in groups[key]),
            'excluded_untagged_calls': sum(not row.get('call_id') for row in server),
            'excluded_observer_calls': sum(row.get('call_id') in observers for row in server),
            'errors': errors, 'layer': 'server HTTP counters; not total wire traffic'}


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', action='append', required=True, type=Path)
    parser.add_argument('--server', required=True, type=Path,
                        help='sanitized MinIO accounting JSONL')
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.server.read_text().splitlines()]
    report = reconcile_ledgers(args.ledger, rows, args.bucket)
    with args.out.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    raise SystemExit(0 if report['complete'] else 1)
