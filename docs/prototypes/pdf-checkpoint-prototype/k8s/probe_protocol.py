"""THROWAWAY protocol checks; --bucket runs real requests in an isolated prefix.

Default uses an in-memory CAS test double: proves Python protocol behavior only.
No parser, Temporal, Kubernetes or object-service semantics are proven by default.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import io
import json
import threading
import time
import uuid
from object_store import Store


class Error(Exception):
    def __init__(self, code):
        self.response = {'Error': {'Code': code}}


class MemoryS3:
    def __init__(self):
        self.objects, self.lock = {}, threading.Lock()

    def get_object(self, Bucket, Key):
        with self.lock:
            if Key not in self.objects:
                raise Error('NoSuchKey')
            return {'Body': io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, IfNoneMatch):
        assert IfNoneMatch == '*'
        with self.lock:
            if Key in self.objects:
                raise Error('PreconditionFailed')
            self.objects[Key] = Body


def crash(*args):
    raise RuntimeError('intentional persistence boundary interruption')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bucket')
    parser.add_argument('--endpoint-url')
    parser.add_argument('--prefix', default='PROTOTYPE-wipe-me')
    args = parser.parse_args()
    client = MemoryS3()
    if args.bucket:
        import boto3
        client = boto3.client('s3', endpoint_url=args.endpoint_url)
    prefix = args.prefix.rstrip('/') + '/' + str(uuid.uuid4())
    store = Store(client, args.bucket or 'memory', prefix)
    started = time.perf_counter()
    files = {'complete.json': b'{"completed":true}', 'checkpoints/page.json': b'page output'}
    try:
        store.publish('incomplete', files, after_upload=crash)
    except RuntimeError:
        pass
    assert store.resolve('incomplete') is None
    try:
        store.publish('lost-ack', files, after_register=crash)
    except RuntimeError:
        pass
    accepted = store.resolve('lost-ack')
    assert accepted and store.publish('lost-ack', files, after_upload=crash) == accepted
    barrier = threading.Barrier(8)
    def attempt(number):
        waited = False
        def rendezvous(key):
            nonlocal waited
            if not waited:
                waited = True
                barrier.wait(timeout=60)
        return store.publish('race', {'output': str(number).encode()}, after_upload=rendezvous)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert all(result == results[0] for result in results)
    assert store.resolve('race') == results[0]
    multipart_unpublished = None
    if args.bucket:
        key = prefix + '/multipart-unfinished'
        upload = client.create_multipart_upload(Bucket=args.bucket, Key=key)
        try:
            client.upload_part(Bucket=args.bucket, Key=key, UploadId=upload['UploadId'], PartNumber=1, Body=b'x'*(6*1024*1024))
            multipart_unpublished = store.get(key) is None
            assert multipart_unpublished
        finally:
            client.abort_multipart_upload(Bucket=args.bucket, Key=key, UploadId=upload['UploadId'])
    print(json.dumps({'mode': 'real-object-service' if args.bucket else 'in-memory-test-double',
        'checks': {'incomplete_not_registered': True, 'lost_ack_reconciled': True,
                   'eight_concurrent_attempts_one_accepted_manifest': True},
        'multipart_unpublished': multipart_unpublished,
        'seconds': time.perf_counter()-started, 'prefix': prefix,
        'limits': 'No Pod loss or parser integration in this probe; multipart is left uncompleted then aborted, not interrupted mid-request; objects retained.'}, indent=2))


if __name__ == '__main__':
    main()
