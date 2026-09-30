"""Derive comparable checkpoint and payload costs from a complete worker ledger."""
from collections import defaultdict

from storage_ledger import reconcile


def summarize(path):
    return summarize_ledgers([path])


def summarize_ledgers(paths):
    ledgers = [reconcile(path) for path in paths]
    if not ledgers or any(not ledger['complete'] for ledger in ledgers):
        raise ValueError('complete storage ledger required')
    requests = defaultdict(list)
    for ledger in ledgers:
        for row in ledger['events']:
            if row['role'] == 'workload':
                requests[row['request_id']].append(row)
    result = []
    for request_id, rows in sorted(requests.items()):
        gets = [row for row in rows if row['operation'] == 'get_object'
                and row['outcome'] == 'read_complete']
        puts = [row for row in rows if row['operation'] == 'put_object']
        unique_reads = {row['key']: max(
            item['delivered_bytes'] for item in gets if item['key'] == row['key'])
            for row in gets}
        successful_puts = [row for row in puts if row['outcome'] == 'call_succeeded']
        unique_puts = {row['key']: max(
            item.get('submitted_bytes') or 0 for item in successful_puts
            if item['key'] == row['key']) for row in successful_puts}
        read_bytes = sum(row['delivered_bytes'] for row in gets)
        read_denominator = sum(unique_reads.values())
        unknown_put_sizes = sum(row.get('submitted_bytes') is None for row in puts)
        submitted_put_bytes = sum(row.get('submitted_bytes') or 0 for row in puts)
        successful_upload_bytes = sum(unique_puts.values())
        buffers = [row for row in rows if row['operation'] == 'publication_buffers']
        expected_missing = [row for row in rows if row['operation'] == 'get_object'
                            and row['outcome'] == 'call_failed'
                            and row.get('error_type') == 'NoSuchKey'
                            and row.get('sdk_retries') == 0]
        result.append({
            'request_id': request_id,
            'read_payload_bytes': read_bytes,
            'unique_read_payload_bytes': read_denominator,
            'read_amplification': read_bytes / read_denominator if read_denominator else None,
            'submitted_put_payload_bytes': submitted_put_bytes,
            'unique_successful_upload_bytes': successful_upload_bytes,
            'application_submission_ratio': (
                submitted_put_bytes / successful_upload_bytes
                if successful_upload_bytes and not unknown_put_sizes else None),
            'unique_attempt_upload_bytes': sum(
                size for key, size in unique_puts.items() if '/attempts/' in key),
            'registration_bytes': sum(
                size for key, size in unique_puts.items() if '/registered/' in key),
            'peak_publication_payload_bytes': max(
                (row['concurrent_publication_payload_bytes'] for row in buffers), default=0),
            'peak_read_chunk_bytes': max(
                (row['peak_read_chunk_bytes'] for row in gets), default=0)
                if all('peak_read_chunk_bytes' in row for row in gets) else None,
            'expected_missing_lookups': len(expected_missing),
            'unknown_put_sizes': unknown_put_sizes,
            'sdk_retries': sum(row.get('sdk_retries') or 0 for row in puts),
            'transmitted_put_payload_bytes': None,
            'committed_payload_bytes': None,
            'incomplete_calls': sum(row['outcome'] == 'read_incomplete' or (
                row['outcome'] == 'call_failed' and row not in expected_missing) for row in rows),
        })
    return {'complete': True, 'requests': result}


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(json.dumps(summarize(args.ledger), indent=2) + '\n')
