"""Existing immutable S3 publication protocol, extracted without semantic changes.

Callers own bucket/prefix configuration and retention. T03 hardens this protocol.
"""
import hashlib
import json
import uuid
import time
import threading


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Store:
    def __init__(self, client, bucket, prefix):
        self.client, self.bucket = client, bucket
        self.prefix = prefix.rstrip('/') + '/'
        self.lock = threading.Lock()
        self.io = {'get_bytes': 0, 'put_bytes': 0, 'get_seconds': 0.0, 'put_seconds': 0.0}

    def get(self, key):
        try:
            start = time.perf_counter()
            data = self.client.get_object(Bucket=self.bucket, Key=key)['Body'].read()
            with self.lock:
                self.io['get_bytes'] += len(data)
                self.io['get_seconds'] += time.perf_counter() - start
            return data
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('NoSuchKey', '404'):
                return None
            raise  # Authorization/network failures are not cache misses.

    def put_once(self, key, data):
        try:
            start = time.perf_counter()
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, IfNoneMatch='*')
            with self.lock:
                self.io['put_bytes'] += len(data)
                self.io['put_seconds'] += time.perf_counter() - start
            return True
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('PreconditionFailed', '412'):
                return False
            raise  # 409 and ambiguous acknowledgements retry the entire operation.

    def registry_key(self, operation):
        return self.prefix + 'registered/' + digest(operation.encode()) + '.json'

    def resolve(self, operation):
        raw = self.get(self.registry_key(operation))
        if raw is None:
            return None
        manifest = json.loads(raw)
        assert manifest['operation'] == operation
        for item in manifest['files']:
            assert item['key'].startswith(self.prefix + 'attempts/')
            data = self.get(item['key'])
            assert data is not None and digest(data) == item['sha256']
            assert len(data) == item['bytes']
        return manifest

    def publish(self, operation, files, after_upload=None, after_register=None):
        """Caller must validate domain/group coverage before passing completed files.

        operation must encode source/method/code/kind/input identities, never attempt
        numbers or fault flags. files maps relative artifact names to bytes. Deliberate
        readback measures integrity AND transfer overhead in this prototype.
        """
        existing = self.resolve(operation)
        if existing is not None:
            return existing
        assert files
        attempt = self.prefix + 'attempts/' + str(uuid.uuid4()) + '/'
        entries = []
        for name, data in sorted(files.items()):
            assert name and not name.startswith('/') and '..' not in name.split('/')
            key = attempt + name
            assert self.put_once(key, data)
            assert self.get(key) == data
            entries.append({'name': name, 'key': key, 'sha256': digest(data), 'bytes': len(data)})
            if after_upload:
                after_upload(key)
        manifest = {'version': 1, 'operation': operation, 'files': entries}
        self.put_once(self.registry_key(operation), json.dumps(manifest, sort_keys=True).encode())
        if after_register:
            after_register()
        # Concurrent loser returns the accepted winner, not its own staging output.
        return self.resolve(operation)
