"""Immutable attempt artifacts, authoritative registrations and bounded inventory.

Callers own domain coverage checks, bucket/prefix configuration and retention.
"""
import hashlib
import json
import uuid
import time
import threading


def digest(data):
    return hashlib.sha256(data).hexdigest()


class StoreFailure(RuntimeError):
    """Sanitized failure categories shared by storage and processing callers."""
    def __init__(self, category, code):
        super().__init__(code)
        self.category, self.code = category, code


def storage_failure(error):
    code = getattr(error, 'response', {}).get('Error', {}).get('Code', '')
    if code in ('AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch', '403'):
        return StoreFailure('configuration', 'storage_access_denied')
    if code in ('NoSuchBucket', 'InvalidBucketName', 'AuthorizationHeaderMalformed',
                'PermanentRedirect', 'InvalidEndpoint', 'NotImplemented', '501'):
        return StoreFailure('configuration', 'storage_configuration')
    return StoreFailure('storage', 'storage_unavailable')


def valid_name(name):
    return (isinstance(name, str) and bool(name) and not name.startswith('/')
            and all(part not in ('', '.', '..') for part in name.split('/')))


class Store:
    def __init__(self, client, bucket, prefix):
        self.client, self.bucket = client, bucket
        self.prefix = prefix.rstrip('/') + '/'
        self.lock = threading.Lock()
        self.io = {'get_bytes': 0, 'put_bytes': 0, 'get_seconds': 0.0, 'put_seconds': 0.0}

    def get(self, key):
        try:
            start = time.perf_counter()
            body = self.client.get_object(Bucket=self.bucket, Key=key)['Body']
            try:
                data = body.read()
            finally:
                body.close()
            with self.lock:
                self.io['get_bytes'] += len(data)
                self.io['get_seconds'] += time.perf_counter() - start
            return data
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('NoSuchKey', '404'):
                return None
            raise storage_failure(error) from None

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
            raise storage_failure(error) from None

    def registry_key(self, operation):
        return self.prefix + 'registered/' + digest(operation.encode()) + '.json'

    def resolve(self, operation):
        raw = self.get(self.registry_key(operation))
        if raw is None:
            return None
        try:
            manifest = json.loads(raw)
            if manifest['version'] != 1 or manifest['operation'] != operation or not manifest['files']:
                raise ValueError()
            names, keys, attempts = set(), set(), set()
            for item in manifest['files']:
                name, key = item['name'], item['key']
                if (not valid_name(name) or name in names or key in keys
                        or not key.startswith(self.prefix+'attempts/')
                        or type(item['bytes']) is not int or item['bytes'] < 0
                        or len(item['sha256']) != 64
                        or any(c not in '0123456789abcdef' for c in item['sha256'])):
                    raise ValueError()
                suffix = key[len(self.prefix+'attempts/'):]
                attempt, separator, artifact = suffix.partition('/')
                if not attempt or not separator or artifact != name:
                    raise ValueError()
                names.add(name); keys.add(key); attempts.add(attempt)
            if len(attempts) != 1:
                raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError):
            raise StoreFailure('integrity', 'committed_manifest_invalid') from None
        for item in manifest['files']:
            self.read_artifact(item)
        return manifest

    def read_artifact(self, item):
        """Validate every read, including a second read after resolution."""
        data = self.get(item['key'])
        if data is None:
            raise StoreFailure('integrity', 'committed_payload_missing')
        if len(data) != item['bytes'] or digest(data) != item['sha256']:
            raise StoreFailure('integrity', 'committed_payload_corrupt')
        return data

    def publish(self, operation, files, after_upload=None, after_register=None):
        """Publish validated outputs; a concurrent loser returns the verified winner.

        Callers validate page coverage before publication. Hooks exist for the real
        fault harness, never become operation identity, and are not commit signals.
        Unknown write outcomes reconcile by authoritative read, not overwrite.
        """
        existing = self.resolve(operation)
        if existing is not None:
            return existing
        if not files or any(not valid_name(n) or not isinstance(d, bytes) for n,d in files.items()):
            raise ValueError('Invalid publication files')
        attempt = self.prefix + 'attempts/' + str(uuid.uuid4()) + '/'
        entries = []
        for name, data in sorted(files.items()):
            key = attempt + name
            try:
                self.put_once(key, data)
            except StoreFailure as error:
                if error.category != 'storage':
                    raise
                # May have succeeded remotely before the connection failed.
                if self.get(key) != data:
                    raise error
            if self.get(key) != data:
                raise StoreFailure('integrity', 'uploaded_payload_corrupt')
            entries.append({'name': name, 'key': key, 'sha256': digest(data), 'bytes': len(data)})
            if after_upload:
                after_upload(key)
        manifest = {'version': 1, 'operation': operation, 'files': entries}
        try:
            self.put_once(self.registry_key(operation), json.dumps(manifest, sort_keys=True).encode())
        except StoreFailure as error:
            if error.category != 'storage':
                raise
            accepted = self.resolve(operation)
            if accepted is None:
                raise error
        if after_register:
            after_register()
        accepted = self.resolve(operation)
        if accepted is None:
            raise StoreFailure('storage', 'registration_not_visible')
        def content(value):
            return sorted((i['name'], i['sha256'], i['bytes']) for i in value['files'])
        if content(accepted) != content(manifest):
            diagnostic = {'version': 1, 'operation': operation, 'winner': accepted,
                          'loser': manifest, 'observed_at_unix': time.time()}
            self.put_once(self.prefix+'diagnostics/'+uuid.uuid4().hex+'.json',
                          json.dumps(diagnostic, sort_keys=True).encode())
        return accepted

    def inventory(self, max_objects=10000, capacity_bytes=None):
        """Bounded observation, not a snapshot or retention/GC authorization.

        With a truncated listing no orphan classification is safe. A complete
        listing still requires quiescence before counts are compared exactly.
        Capacity is an operator supplied logical prefix budget, not disk capacity.
        """
        if type(max_objects) is not int or max_objects <= 0:
            raise ValueError('max_objects must be positive')
        if capacity_bytes is not None and (type(capacity_bytes) is not int or capacity_bytes <= 0):
            raise ValueError('capacity_bytes must be positive')
        objects, token, complete = [], None, False
        while len(objects) < max_objects:
            args = dict(Bucket=self.bucket, Prefix=self.prefix, MaxKeys=min(1000,max_objects-len(objects)))
            if token:
                args['ContinuationToken'] = token
            try:
                page = self.client.list_objects_v2(**args)
            except Exception as error:
                raise storage_failure(error) from None
            objects.extend(page.get('Contents', []))
            if not page.get('IsTruncated'):
                complete = True
                break
            token = page['NextContinuationToken']
        registrations = [o for o in objects if o['Key'].startswith(self.prefix+'registered/')]
        referenced, invalid = set(), []
        for item in registrations:
            try:
                raw = self.get(item['Key'])
                manifest = json.loads(raw) if raw is not None else None
                if manifest is None or self.registry_key(manifest['operation']) != item['Key']:
                    raise StoreFailure('integrity','committed_manifest_invalid')
                verified = self.resolve(manifest['operation'])
                if verified is None:
                    raise StoreFailure('integrity','registration_disappeared')
                referenced.update(i['key'] for i in verified['files'])
            except (ValueError, TypeError, KeyError, StoreFailure) as error:
                if isinstance(error, StoreFailure) and error.category != 'integrity':
                    raise
                invalid.append({'key':item['Key'], 'code':getattr(error,'code','committed_manifest_invalid')})
        attempts = [o for o in objects if o['Key'].startswith(self.prefix+'attempts/')]
        safe_to_classify = complete and not invalid
        orphan = [o for o in attempts if o['Key'] not in referenced] if safe_to_classify else []
        size = sum(o['Size'] for o in objects)
        return {'observed_at_unix':time.time(), 'complete':complete, 'snapshot':False,
                'listed_objects':len(objects), 'stored_bytes_lower_bound':size,
                'registration_count':len(registrations), 'invalid_registrations':invalid,
                'registered_artifact_count':len(referenced),
                'orphan_classification_complete':safe_to_classify,
                'orphan_objects':orphan if safe_to_classify else None,
                'orphan_bytes':sum(o['Size'] for o in orphan) if safe_to_classify else None,
                'capacity_bytes':capacity_bytes,
                'capacity_exceeded':(True if size > capacity_bytes else False if complete else None) if capacity_bytes is not None else None,
                'versions_included':False, 'retention_action':'none'}


if __name__ == '__main__':
    import argparse
    import os
    import boto3

    parser = argparse.ArgumentParser(description='Read-only bounded checkpoint inventory; never performs GC')
    parser.add_argument('--max-objects', type=int, default=10000)
    parser.add_argument('--capacity-bytes', type=int, required=True)
    args = parser.parse_args()
    store = Store(boto3.client('s3', endpoint_url=os.environ['OBJECT_ENDPOINT']),
                  os.environ['OBJECT_BUCKET'], os.environ['OBJECT_PREFIX'])
    report = store.inventory(args.max_objects, args.capacity_bytes)
    print(json.dumps(report, indent=2, default=str))
    if report['invalid_registrations'] or report['capacity_exceeded']:
        raise SystemExit(2)
    if not report['complete']:
        raise SystemExit(3)
