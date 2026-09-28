"""Keep only scoped server HTTP accounting; discard headers and bodies."""
from urllib.parse import urlsplit
import json


def collect(stream, output, bucket, prefix):
    """Stream sanitized records; reject malformed/error output, never retain raw data."""
    count = 0
    for line in stream:
        event = json.loads(line)
        if not isinstance(event, dict) or event.get('status') == 'error':
            raise ValueError('invalid or failed native trace')
        if 'request' not in event:
            raise ValueError('unexpected native trace record')
        row = accounting(event, bucket, prefix)
        if row is not None:
            output.write(json.dumps(row) + '\n')
            output.flush()
            count += 1
    if not count:
        raise ValueError('no scoped native trace records')
    return count


def accounting(row, bucket, prefix):
    path = urlsplit(row['request']['path']).path
    target = '/' + bucket + '/' + prefix.strip('/') + '/'
    if not path.startswith(target):
        return None
    stats = row['callStats']
    headers = row['request'].get('headers', {})
    call_id = next((value for key, value in headers.items()
                    if key.lower() == 'x-t09b-call-id'), None)
    if isinstance(call_id, list):
        call_id = call_id[0] if len(call_id) == 1 else None
    if call_id is not None and (not isinstance(call_id, str) or len(call_id) != 32
                                or any(c not in '0123456789abcdef' for c in call_id)):
        raise ValueError('invalid trace correlation')
    for name in ('rx', 'tx', 'duration'):
        if type(stats.get(name)) is not int or stats[name] < 0:
            raise ValueError('missing or invalid server HTTP accounting')
    return {'time': row['time'], 'path': path, 'call_id': call_id,
            'method': row['request']['method'],
            'status': row['response']['statusCode'],
            'server_rx_bytes': stats['rx'], 'server_tx_bytes': stats['tx'],
            'server_duration_raw': stats['duration'],
            'layer': 'MinIO HTTP callStats; not payload-only or packet bytes'}


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    with args.out.open('x') as output:
        collect(sys.stdin, output, args.bucket, args.prefix)
