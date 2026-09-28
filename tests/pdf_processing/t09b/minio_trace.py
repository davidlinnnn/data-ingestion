"""Keep only scoped server HTTP accounting; discard headers and bodies."""
from urllib.parse import urlsplit


def accounting(row, bucket, prefix):
    path = urlsplit(row['request']['path']).path
    target = '/' + bucket + '/' + prefix.strip('/') + '/'
    if not path.startswith(target):
        return None
    stats = row['callStats']
    for name in ('rx', 'tx', 'duration'):
        if type(stats.get(name)) is not int or stats[name] < 0:
            raise ValueError('missing or invalid server HTTP accounting')
    return {'time': row['time'], 'path': path,
            'method': row['request']['method'],
            'status': row['response']['statusCode'],
            'server_rx_bytes': stats['rx'], 'server_tx_bytes': stats['tx'],
            'server_duration_raw': stats['duration'],
            'layer': 'MinIO HTTP callStats; not payload-only or packet bytes'}
